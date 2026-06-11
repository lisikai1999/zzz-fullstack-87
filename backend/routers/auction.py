from fastapi import APIRouter
from pydantic import BaseModel
import numpy as np
import json
from typing import Optional

from database import get_db

router = APIRouter()


class Bidder(BaseModel):
    id: int
    name: str
    valuation: float


class AuctionConfig(BaseModel):
    auction_type: str  # english, dutch, sealed_first, sealed_second, vcg
    bidders: list[Bidder]
    reserve_price: float = 0
    increment: float = 1.0  # for English auction
    start_price: Optional[float] = None  # for Dutch auction


class AuctionCompareConfig(BaseModel):
    bidders: list[Bidder]
    reserve_price: float = 0
    num_simulations: int = 1000


def simulate_english_auction(bidders: list[Bidder], reserve_price: float, increment: float) -> dict:
    """English ascending auction - bidders drop out when price exceeds valuation."""
    sorted_bidders = sorted(bidders, key=lambda b: b.valuation, reverse=True)
    if len(sorted_bidders) < 2:
        return {"error": "Need at least 2 bidders"}

    price = reserve_price
    history = [{"price": price, "active_bidders": [b.name for b in sorted_bidders], "event": "开始"}]
    active = list(sorted_bidders)

    while len(active) > 1:
        price += increment
        new_active = [b for b in active if b.valuation >= price]
        dropped = [b for b in active if b.valuation < price]

        for b in dropped:
            history.append({
                "price": price,
                "active_bidders": [x.name for x in new_active],
                "event": f"{b.name} 退出 (估值 {b.valuation:.1f})",
            })

        if len(new_active) <= 1:
            break
        active = new_active

    if not active and sorted_bidders:
        winner = sorted_bidders[0]
        final_price = sorted_bidders[1].valuation if len(sorted_bidders) > 1 else reserve_price
    elif active:
        winner = active[0] if active else sorted_bidders[0]
        final_price = price - increment if price > reserve_price else reserve_price
        # In English auction, winner pays second-highest valuation (approximately)
        if len(sorted_bidders) > 1:
            final_price = max(sorted_bidders[1].valuation, reserve_price)
    else:
        return {"winner": None, "price": 0, "history": history, "revenue": 0}

    if final_price < reserve_price:
        return {"winner": None, "price": 0, "history": history, "revenue": 0}

    history.append({
        "price": final_price,
        "active_bidders": [winner.name],
        "event": f"{winner.name} 以 {final_price:.1f} 赢得拍卖",
    })

    return {
        "winner": winner.name,
        "winner_valuation": winner.valuation,
        "price": final_price,
        "surplus": winner.valuation - final_price,
        "revenue": final_price,
        "history": history,
    }


def simulate_dutch_auction(bidders: list[Bidder], start_price: float, reserve_price: float) -> dict:
    """Dutch descending auction - strategically equivalent to first-price sealed-bid.
    Optimal bid with n bidders, uniform values: bid = (n-1)/n * valuation."""
    if start_price is None:
        start_price = max(b.valuation for b in bidders) * 1.5

    n = len(bidders)
    # Each bidder's optimal stopping price (= their shaded bid)
    optimal_bids = {b.name: b.valuation * (n - 1) / n for b in bidders}

    price = start_price
    decrement = (start_price - reserve_price) / 100
    history = [{"price": round(price, 2), "event": "开始", "acceptor": None}]

    while price > reserve_price:
        price -= decrement
        price = max(price, reserve_price)

        # Check if any bidder would accept at this price (price <= their optimal bid)
        acceptors = [b for b in bidders if optimal_bids[b.name] >= price and optimal_bids[b.name] >= reserve_price]
        if acceptors:
            winner = max(acceptors, key=lambda b: optimal_bids[b.name])
            accept_price = optimal_bids[winner.name]
            history.append({"price": round(accept_price, 2), "event": f"{winner.name} 接受价格 (出价 {accept_price:.1f})", "acceptor": winner.name})
            return {
                "winner": winner.name,
                "winner_valuation": winner.valuation,
                "price": accept_price,
                "surplus": winner.valuation - accept_price,
                "revenue": accept_price,
                "history": history,
            }

        if len(history) % 10 == 0:
            history.append({"price": round(price, 2), "event": "价格下降中...", "acceptor": None})

    return {"winner": None, "price": 0, "revenue": 0, "surplus": 0, "history": history}


def simulate_sealed_first_price(bidders: list[Bidder], reserve_price: float) -> dict:
    """First-price sealed-bid auction. Optimal bid shading: bid = (n-1)/n * valuation."""
    n = len(bidders)
    bids = []
    for b in bidders:
        # Optimal bid for uniform distribution
        optimal_bid = b.valuation * (n - 1) / n
        bid = max(optimal_bid, reserve_price) if optimal_bid >= reserve_price else 0
        bids.append({"bidder": b.name, "valuation": b.valuation, "bid": bid})

    valid_bids = [bid for bid in bids if bid["bid"] >= reserve_price]
    if not valid_bids:
        return {"winner": None, "price": 0, "bids": bids, "revenue": 0}

    winner_bid = max(valid_bids, key=lambda x: x["bid"])
    winner = next(b for b in bidders if b.name == winner_bid["bidder"])

    return {
        "winner": winner.name,
        "winner_valuation": winner.valuation,
        "price": winner_bid["bid"],
        "surplus": winner.valuation - winner_bid["bid"],
        "revenue": winner_bid["bid"],
        "bids": bids,
    }


def simulate_sealed_second_price(bidders: list[Bidder], reserve_price: float) -> dict:
    """Second-price sealed-bid (Vickrey) auction. Dominant strategy: bid true valuation."""
    bids = []
    for b in bidders:
        bid = b.valuation  # Truthful bidding is dominant strategy
        bids.append({"bidder": b.name, "valuation": b.valuation, "bid": bid})

    valid_bids = [bid for bid in bids if bid["bid"] >= reserve_price]
    if not valid_bids:
        return {"winner": None, "price": 0, "bids": bids, "revenue": 0}

    sorted_bids = sorted(valid_bids, key=lambda x: x["bid"], reverse=True)
    winner_bid = sorted_bids[0]
    second_price = sorted_bids[1]["bid"] if len(sorted_bids) > 1 else reserve_price

    winner = next(b for b in bidders if b.name == winner_bid["bidder"])
    price = max(second_price, reserve_price)

    return {
        "winner": winner.name,
        "winner_valuation": winner.valuation,
        "price": price,
        "surplus": winner.valuation - price,
        "revenue": price,
        "bids": bids,
    }


def simulate_vcg_auction(bidders: list[Bidder], reserve_price: float) -> dict:
    """VCG (Vickrey-Clarke-Groves) mechanism for single item - equivalent to second-price."""
    bids = [{"bidder": b.name, "valuation": b.valuation, "bid": b.valuation} for b in bidders]
    valid_bids = [bid for bid in bids if bid["bid"] >= reserve_price]

    if not valid_bids:
        return {"winner": None, "price": 0, "bids": bids, "revenue": 0, "vcg_payments": []}

    sorted_bids = sorted(valid_bids, key=lambda x: x["bid"], reverse=True)

    # VCG payment = externality imposed on others
    # For single item: winner pays = max value among others = second highest bid
    winner_bid = sorted_bids[0]
    winner = next(b for b in bidders if b.name == winner_bid["bidder"])

    # Social welfare without winner
    welfare_without_winner = sorted_bids[1]["bid"] if len(sorted_bids) > 1 else 0
    # Social welfare of others with winner present
    welfare_others_with_winner = 0

    vcg_payment = welfare_without_winner - welfare_others_with_winner
    vcg_payment = max(vcg_payment, reserve_price)

    vcg_payments = []
    for b in bidders:
        if b.name == winner.name:
            vcg_payments.append({"bidder": b.name, "payment": vcg_payment, "utility": b.valuation - vcg_payment})
        else:
            vcg_payments.append({"bidder": b.name, "payment": 0, "utility": 0})

    return {
        "winner": winner.name,
        "winner_valuation": winner.valuation,
        "price": vcg_payment,
        "surplus": winner.valuation - vcg_payment,
        "revenue": vcg_payment,
        "bids": bids,
        "vcg_payments": vcg_payments,
    }


@router.post("/simulate")
async def simulate_auction(config: AuctionConfig):
    bidders = config.bidders

    if config.auction_type == "english":
        result = simulate_english_auction(bidders, config.reserve_price, config.increment)
    elif config.auction_type == "dutch":
        start = config.start_price or max(b.valuation for b in bidders) * 1.5
        result = simulate_dutch_auction(bidders, start, config.reserve_price)
    elif config.auction_type == "sealed_first":
        result = simulate_sealed_first_price(bidders, config.reserve_price)
    elif config.auction_type == "sealed_second":
        result = simulate_sealed_second_price(bidders, config.reserve_price)
    elif config.auction_type == "vcg":
        result = simulate_vcg_auction(bidders, config.reserve_price)
    else:
        return {"error": f"Unknown auction type: {config.auction_type}"}

    result["auction_type"] = config.auction_type

    db = await get_db()
    await db.execute(
        "INSERT INTO game_sessions (game_type, config, result) VALUES (?, ?, ?)",
        ("auction", json.dumps(config.model_dump()), json.dumps(result, default=str))
    )
    await db.commit()
    await db.close()

    return result


@router.post("/compare")
async def compare_auctions(config: AuctionCompareConfig):
    """Run Monte Carlo simulations under symmetric IPV to verify revenue equivalence.
    All bidders draw from the same uniform [0, V_max] distribution."""
    bidders_template = config.bidders
    n_bidders = len(bidders_template)
    v_max = max(b.valuation for b in bidders_template) * 2

    results = {
        "english": {"revenues": [], "surpluses": []},
        "dutch": {"revenues": [], "surpluses": []},
        "sealed_first": {"revenues": [], "surpluses": []},
        "sealed_second": {"revenues": [], "surpluses": []},
        "vcg": {"revenues": [], "surpluses": []},
    }

    for _ in range(config.num_simulations):
        # Symmetric IPV: all bidders draw from same uniform [0, V_max]
        valuations = np.random.uniform(0, v_max, size=n_bidders)
        sim_bidders = [
            Bidder(id=i+1, name=bidders_template[i].name, valuation=float(valuations[i]))
            for i in range(n_bidders)
        ]

        sorted_vals = sorted(valuations, reverse=True)
        v1 = sorted_vals[0]  # highest valuation
        v2 = sorted_vals[1] if n_bidders > 1 else 0  # second-highest

        reserve = config.reserve_price

        # English auction: winner = highest bidder, pays second-highest valuation
        if v1 >= reserve:
            price_eng = max(v2, reserve)
            results["english"]["revenues"].append(price_eng)
            results["english"]["surpluses"].append(v1 - price_eng)
        else:
            results["english"]["revenues"].append(0)
            results["english"]["surpluses"].append(0)

        # Dutch auction: strategically equivalent to first-price sealed-bid
        # Optimal bid = (n-1)/n * v, winner = highest bidder
        if v1 >= reserve:
            bid_dutch = v1 * (n_bidders - 1) / n_bidders
            price_dutch = max(bid_dutch, reserve)
            results["dutch"]["revenues"].append(price_dutch)
            results["dutch"]["surpluses"].append(v1 - price_dutch)
        else:
            results["dutch"]["revenues"].append(0)
            results["dutch"]["surpluses"].append(0)

        # First-price sealed-bid: same as Dutch
        if v1 >= reserve:
            bid_fp = v1 * (n_bidders - 1) / n_bidders
            price_fp = max(bid_fp, reserve)
            results["sealed_first"]["revenues"].append(price_fp)
            results["sealed_first"]["surpluses"].append(v1 - price_fp)
        else:
            results["sealed_first"]["revenues"].append(0)
            results["sealed_first"]["surpluses"].append(0)

        # Second-price sealed-bid (Vickrey): bid truthfully, pay second-highest
        if v1 >= reserve:
            price_sp = max(v2, reserve)
            results["sealed_second"]["revenues"].append(price_sp)
            results["sealed_second"]["surpluses"].append(v1 - price_sp)
        else:
            results["sealed_second"]["revenues"].append(0)
            results["sealed_second"]["surpluses"].append(0)

        # VCG: for single item, identical to second-price
        if v1 >= reserve:
            price_vcg = max(v2, reserve)
            results["vcg"]["revenues"].append(price_vcg)
            results["vcg"]["surpluses"].append(v1 - price_vcg)
        else:
            results["vcg"]["revenues"].append(0)
            results["vcg"]["surpluses"].append(0)

    comparison = {}
    convergence = {}
    for atype, data in results.items():
        revs = np.array(data["revenues"])
        comparison[atype] = {
            "avg_revenue": float(np.mean(revs)),
            "avg_surplus": float(np.mean(data["surpluses"])),
            "std_revenue": float(np.std(revs)),
            "revenue_distribution": np.histogram(revs, bins=20)[0].tolist(),
            "revenue_bins": np.histogram(revs, bins=20)[1].tolist(),
        }
        # Cumulative moving average for convergence visualization
        step = max(1, len(data["revenues"]) // 100)
        cumavg = [float(np.mean(revs[:i+1])) for i in range(0, len(revs), step)]
        convergence[atype] = cumavg

    return {
        "comparison": comparison,
        "convergence": convergence,
        "num_simulations": config.num_simulations,
        "num_bidders": n_bidders,
    }


AUCTION_TYPE_NAMES = {
    "english": "英式拍卖（升价）",
    "dutch": "荷兰式拍卖（降价）",
    "sealed_first": "第一价格密封拍卖",
    "sealed_second": "第二价格密封拍卖（维克里）",
    "vcg": "VCG 机制",
}


@router.get("/types")
async def get_auction_types():
    return [
        {"id": k, "name": v, "description": desc}
        for k, v, desc in [
            ("english", "英式拍卖（升价）", "价格从低到高，最后留下的出价者赢得拍卖，支付其出价"),
            ("dutch", "荷兰式拍卖（降价）", "价格从高到低，第一个接受价格的人赢得拍卖"),
            ("sealed_first", "第一价格密封拍卖", "所有人同时密封出价，最高出价者赢得并支付自己的出价"),
            ("sealed_second", "第二价格密封拍卖（维克里）", "最高出价者赢得，但只需支付第二高的出价"),
            ("vcg", "VCG 机制", "赢家支付其对其他参与者造成的外部性成本"),
        ]
    ]
