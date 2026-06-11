from fastapi import APIRouter
from pydantic import BaseModel
import numpy as np
import json
from typing import Optional

from database import get_db

router = APIRouter()


class RepeatedGameConfig(BaseModel):
    rounds: int = 100
    strategies: list[str]  # e.g. ["tit_for_tat", "always_cooperate", "always_defect", "random"]
    payoff_matrix: Optional[list[list[float]]] = None  # default: prisoner's dilemma


STRATEGY_NAMES = {
    "tit_for_tat": "以牙还牙",
    "always_cooperate": "始终合作",
    "always_defect": "始终背叛",
    "random": "随机",
    "grudger": "冷酷触发",
    "tit_for_two_tats": "宽容以牙还牙",
}

DEFAULT_PD_PAYOFF = {
    ("C", "C"): (3, 3),
    ("C", "D"): (0, 5),
    ("D", "C"): (5, 0),
    ("D", "D"): (1, 1),
}


def get_action(strategy: str, history_self: list, history_opponent: list, round_num: int) -> str:
    if strategy == "always_cooperate":
        return "C"
    elif strategy == "always_defect":
        return "D"
    elif strategy == "tit_for_tat":
        if round_num == 0:
            return "C"
        return history_opponent[-1]
    elif strategy == "random":
        return np.random.choice(["C", "D"])
    elif strategy == "grudger":
        if "D" in history_opponent:
            return "D"
        return "C"
    elif strategy == "tit_for_two_tats":
        if round_num < 2:
            return "C"
        if history_opponent[-1] == "D" and history_opponent[-2] == "D":
            return "D"
        return "C"
    return "C"


def run_match(strategy1: str, strategy2: str, rounds: int, payoff: dict) -> dict:
    history1 = []
    history2 = []
    scores1 = []
    scores2 = []
    cumulative1 = 0
    cumulative2 = 0
    round_details = []

    for r in range(rounds):
        a1 = get_action(strategy1, history1, history2, r)
        a2 = get_action(strategy2, history2, history1, r)

        s1, s2 = payoff[(a1, a2)]
        cumulative1 += s1
        cumulative2 += s2

        history1.append(a1)
        history2.append(a2)
        scores1.append(cumulative1)
        scores2.append(cumulative2)

        round_details.append({
            "round": r + 1,
            "action1": a1,
            "action2": a2,
            "payoff1": s1,
            "payoff2": s2,
            "cumulative1": cumulative1,
            "cumulative2": cumulative2,
        })

    return {
        "strategy1": strategy1,
        "strategy2": strategy2,
        "total_score1": cumulative1,
        "total_score2": cumulative2,
        "round_details": round_details,
    }


@router.post("/simulate")
async def simulate_repeated_game(config: RepeatedGameConfig):
    payoff = DEFAULT_PD_PAYOFF
    if config.payoff_matrix:
        m = config.payoff_matrix
        payoff = {
            ("C", "C"): (m[0][0], m[0][0]),
            ("C", "D"): (m[0][1], m[1][0]),
            ("D", "C"): (m[1][0], m[0][1]),
            ("D", "D"): (m[1][1], m[1][1]),
        }

    strategies = config.strategies
    n = len(strategies)
    results = []

    # Round-robin tournament
    total_scores = {s: 0 for s in strategies}
    matches = []

    for i in range(n):
        for j in range(i + 1, n):
            match = run_match(strategies[i], strategies[j], config.rounds, payoff)
            matches.append(match)
            total_scores[strategies[i]] += match["total_score1"]
            total_scores[strategies[j]] += match["total_score2"]

    # Self-play
    for i in range(n):
        match = run_match(strategies[i], strategies[i], config.rounds, payoff)
        matches.append(match)
        total_scores[strategies[i]] += match["total_score1"]

    ranking = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)

    db = await get_db()
    await db.execute(
        "INSERT INTO game_sessions (game_type, config, result) VALUES (?, ?, ?)",
        ("repeated", json.dumps(config.model_dump()), json.dumps({"ranking": ranking}))
    )
    await db.commit()
    await db.close()

    return {
        "matches": matches,
        "total_scores": total_scores,
        "ranking": [{"strategy": s, "name": STRATEGY_NAMES.get(s, s), "score": sc} for s, sc in ranking],
    }


@router.post("/single-match")
async def single_match(strategy1: str, strategy2: str, rounds: int = 100):
    match = run_match(strategy1, strategy2, rounds, DEFAULT_PD_PAYOFF)
    return match


@router.get("/strategies")
async def get_strategies():
    return [
        {"id": "tit_for_tat", "name": "以牙还牙", "description": "第一轮合作，之后模仿对手上一轮的选择"},
        {"id": "always_cooperate", "name": "始终合作", "description": "每一轮都选择合作"},
        {"id": "always_defect", "name": "始终背叛", "description": "每一轮都选择背叛"},
        {"id": "random", "name": "随机", "description": "每轮随机选择合作或背叛（50/50）"},
        {"id": "grudger", "name": "冷酷触发", "description": "一开始合作，一旦对手背叛就永远背叛"},
        {"id": "tit_for_two_tats", "name": "宽容以牙还牙", "description": "对手连续背叛两次才还击"},
    ]
