from fastapi import APIRouter
from pydantic import BaseModel
import numpy as np
from scipy.optimize import linprog
from typing import Optional
import json

from database import get_db

router = APIRouter()


class PayoffMatrix(BaseModel):
    player1_matrix: list[list[float]]
    player2_matrix: list[list[float]]
    player1_strategies: Optional[list[str]] = None
    player2_strategies: Optional[list[str]] = None


class NashEquilibriumResult(BaseModel):
    pure_nash: list[dict]
    mixed_nash: Optional[dict] = None
    best_response_data: Optional[dict] = None


def find_pure_nash(p1_matrix: np.ndarray, p2_matrix: np.ndarray) -> list[dict]:
    """Find all pure strategy Nash equilibria."""
    rows, cols = p1_matrix.shape
    equilibria = []

    for i in range(rows):
        for j in range(cols):
            is_br_p1 = p1_matrix[i, j] == np.max(p1_matrix[:, j])
            is_br_p2 = p2_matrix[i, j] == np.max(p2_matrix[i, :])
            if is_br_p1 and is_br_p2:
                equilibria.append({
                    "player1_strategy": i,
                    "player2_strategy": j,
                    "player1_payoff": float(p1_matrix[i, j]),
                    "player2_payoff": float(p2_matrix[i, j]),
                })
    return equilibria


def find_mixed_nash_2x2(p1_matrix: np.ndarray, p2_matrix: np.ndarray) -> Optional[dict]:
    """Find mixed strategy Nash equilibrium for 2x2 games using indifference conditions."""
    if p1_matrix.shape != (2, 2):
        return find_mixed_nash_general(p1_matrix, p2_matrix)

    a, b = p1_matrix[0, 0], p1_matrix[0, 1]
    c, d = p1_matrix[1, 0], p1_matrix[1, 1]

    denom_q = (a - b - c + d)
    if abs(denom_q) < 1e-10:
        q = None
    else:
        q = (d - b) / denom_q
        if q < 0 or q > 1:
            q = None

    e, f = p2_matrix[0, 0], p2_matrix[0, 1]
    g, h = p2_matrix[1, 0], p2_matrix[1, 1]

    denom_p = (e - f - g + h)
    if abs(denom_p) < 1e-10:
        p = None
    else:
        p = (h - f) / denom_p
        if p < 0 or p > 1:
            p = None

    if p is None or q is None:
        return None

    exp_p1 = p * (q * a + (1 - q) * b) + (1 - p) * (q * c + (1 - q) * d)
    exp_p2 = q * (p * e + (1 - p) * g) + (1 - q) * (p * f + (1 - p) * h)

    return {
        "player1_probs": [float(p), float(1 - p)],
        "player2_probs": [float(q), float(1 - q)],
        "player1_expected_payoff": float(exp_p1),
        "player2_expected_payoff": float(exp_p2),
    }


def find_mixed_nash_general(p1_matrix: np.ndarray, p2_matrix: np.ndarray) -> Optional[dict]:
    """Find mixed strategy Nash equilibrium for general games using support enumeration."""
    rows, cols = p1_matrix.shape

    for support_size_1 in range(2, rows + 1):
        for support_size_2 in range(2, cols + 1):
            from itertools import combinations
            for s1 in combinations(range(rows), support_size_1):
                for s2 in combinations(range(cols), support_size_2):
                    result = solve_support(p1_matrix, p2_matrix, list(s1), list(s2))
                    if result is not None:
                        return result
    return None


def solve_support(p1_matrix: np.ndarray, p2_matrix: np.ndarray,
                  support1: list, support2: list) -> Optional[dict]:
    """Solve for mixed strategy given supports."""
    rows, cols = p1_matrix.shape
    s1_size = len(support1)
    s2_size = len(support2)

    # Player 2's mixed strategy must make player 1 indifferent over support1
    # p2_matrix rows in support1 must give equal expected payoff
    A_eq_q = []
    b_eq_q = []
    for i in range(s1_size - 1):
        row = np.zeros(s2_size)
        for j_idx, j in enumerate(support2):
            row[j_idx] = p1_matrix[support1[i], j] - p1_matrix[support1[i + 1], j]
        A_eq_q.append(row)
        b_eq_q.append(0.0)
    A_eq_q.append(np.ones(s2_size))
    b_eq_q.append(1.0)

    A_eq_q = np.array(A_eq_q)
    b_eq_q = np.array(b_eq_q)

    try:
        if A_eq_q.shape[0] != A_eq_q.shape[1]:
            return None
        q_support = np.linalg.solve(A_eq_q, b_eq_q)
        if np.any(q_support < -1e-10):
            return None
        q_support = np.maximum(q_support, 0)
    except np.linalg.LinAlgError:
        return None

    # Player 1's mixed strategy must make player 2 indifferent over support2
    A_eq_p = []
    b_eq_p = []
    for j in range(s2_size - 1):
        row = np.zeros(s1_size)
        for i_idx, i in enumerate(support1):
            row[i_idx] = p2_matrix[i, support2[j]] - p2_matrix[i, support2[j + 1]]
        A_eq_p.append(row)
        b_eq_p.append(0.0)
    A_eq_p.append(np.ones(s1_size))
    b_eq_p.append(1.0)

    A_eq_p = np.array(A_eq_p)
    b_eq_p = np.array(b_eq_p)

    try:
        if A_eq_p.shape[0] != A_eq_p.shape[1]:
            return None
        p_support = np.linalg.solve(A_eq_p, b_eq_p)
        if np.any(p_support < -1e-10):
            return None
        p_support = np.maximum(p_support, 0)
    except np.linalg.LinAlgError:
        return None

    # Check that strategies outside support don't have higher payoff
    p_full = np.zeros(rows)
    for i_idx, i in enumerate(support1):
        p_full[i] = p_support[i_idx]

    q_full = np.zeros(cols)
    for j_idx, j in enumerate(support2):
        q_full[j] = q_support[j_idx]

    support_payoff_1 = float(p1_matrix[support1[0], :] @ q_full)
    for i in range(rows):
        if i not in support1:
            if float(p1_matrix[i, :] @ q_full) > support_payoff_1 + 1e-10:
                return None

    support_payoff_2 = float(p_full @ p2_matrix[:, support2[0]])
    for j in range(cols):
        if j not in support2:
            if float(p_full @ p2_matrix[:, j]) > support_payoff_2 + 1e-10:
                return None

    exp_p1 = float(p_full @ p1_matrix @ q_full)
    exp_p2 = float(p_full @ p2_matrix @ q_full)

    return {
        "player1_probs": p_full.tolist(),
        "player2_probs": q_full.tolist(),
        "player1_expected_payoff": exp_p1,
        "player2_expected_payoff": exp_p2,
    }


def compute_best_response_data(p1_matrix: np.ndarray, p2_matrix: np.ndarray) -> dict:
    """Compute best response function data for visualization (2x2 games)."""
    if p1_matrix.shape != (2, 2):
        return compute_best_response_general(p1_matrix, p2_matrix)

    points = 101
    p_values = np.linspace(0, 1, points)
    q_values = np.linspace(0, 1, points)

    # Best response of player 1 given player 2's q
    br1_p_given_q = []
    for q in q_values:
        payoff_s0 = q * p1_matrix[0, 0] + (1 - q) * p1_matrix[0, 1]
        payoff_s1 = q * p1_matrix[1, 0] + (1 - q) * p1_matrix[1, 1]
        if abs(payoff_s0 - payoff_s1) < 1e-10:
            br1_p_given_q.append({"q": float(q), "p": 0.5, "type": "indifferent"})
        elif payoff_s0 > payoff_s1:
            br1_p_given_q.append({"q": float(q), "p": 1.0, "type": "pure"})
        else:
            br1_p_given_q.append({"q": float(q), "p": 0.0, "type": "pure"})

    # Best response of player 2 given player 1's p
    br2_q_given_p = []
    for p in p_values:
        payoff_s0 = p * p2_matrix[0, 0] + (1 - p) * p2_matrix[1, 0]
        payoff_s1 = p * p2_matrix[0, 1] + (1 - p) * p2_matrix[1, 1]
        if abs(payoff_s0 - payoff_s1) < 1e-10:
            br2_q_given_p.append({"p": float(p), "q": 0.5, "type": "indifferent"})
        elif payoff_s0 > payoff_s1:
            br2_q_given_p.append({"p": float(p), "q": 1.0, "type": "pure"})
        else:
            br2_q_given_p.append({"p": float(p), "q": 0.0, "type": "pure"})

    return {
        "br1_p_given_q": br1_p_given_q,
        "br2_q_given_p": br2_q_given_p,
    }


def compute_best_response_general(p1_matrix: np.ndarray, p2_matrix: np.ndarray) -> dict:
    """For non-2x2 games, compute best response heatmap data."""
    rows, cols = p1_matrix.shape

    # For player 1: given each pure strategy of player 2, what is player 1's best response?
    br1_table = []
    for j in range(cols):
        best_i = int(np.argmax(p1_matrix[:, j]))
        br1_table.append({
            "opponent_strategy": j,
            "best_response": best_i,
            "payoff": float(p1_matrix[best_i, j]),
            "all_payoffs": p1_matrix[:, j].tolist(),
        })

    # For player 2: given each pure strategy of player 1, what is player 2's best response?
    br2_table = []
    for i in range(rows):
        best_j = int(np.argmax(p2_matrix[i, :]))
        br2_table.append({
            "opponent_strategy": i,
            "best_response": best_j,
            "payoff": float(p2_matrix[i, best_j]),
            "all_payoffs": p2_matrix[i, :].tolist(),
        })

    # Payoff heatmap data: for each cell (i,j), mark if it's a BR for player 1 and/or player 2
    heatmap = []
    for i in range(rows):
        for j in range(cols):
            is_br1 = (p1_matrix[i, j] == np.max(p1_matrix[:, j]))
            is_br2 = (p2_matrix[i, j] == np.max(p2_matrix[i, :]))
            heatmap.append({
                "row": i, "col": j,
                "p1_payoff": float(p1_matrix[i, j]),
                "p2_payoff": float(p2_matrix[i, j]),
                "is_br1": bool(is_br1),
                "is_br2": bool(is_br2),
                "is_nash": bool(is_br1 and is_br2),
            })

    return {"br1_table": br1_table, "br2_table": br2_table, "heatmap": heatmap, "type": "general"}


@router.post("/solve", response_model=NashEquilibriumResult)
async def solve_nash_equilibrium(matrix: PayoffMatrix):
    p1 = np.array(matrix.player1_matrix)
    p2 = np.array(matrix.player2_matrix)

    pure_nash = find_pure_nash(p1, p2)
    mixed_nash = find_mixed_nash_2x2(p1, p2)
    best_response = compute_best_response_data(p1, p2)

    db = await get_db()
    await db.execute(
        "INSERT INTO game_sessions (game_type, config, result) VALUES (?, ?, ?)",
        ("static", json.dumps(matrix.model_dump()), json.dumps({
            "pure_nash": pure_nash,
            "mixed_nash": mixed_nash,
        }))
    )
    await db.commit()
    await db.close()

    return NashEquilibriumResult(
        pure_nash=pure_nash,
        mixed_nash=mixed_nash,
        best_response_data=best_response,
    )


@router.get("/presets")
async def get_presets():
    return [
        {
            "name": "囚徒困境",
            "player1_matrix": [[-1, -3], [0, -2]],
            "player2_matrix": [[-1, 0], [-3, -2]],
            "player1_strategies": ["合作", "背叛"],
            "player2_strategies": ["合作", "背叛"],
        },
        {
            "name": "性别之战",
            "player1_matrix": [[3, 0], [0, 2]],
            "player2_matrix": [[2, 0], [0, 3]],
            "player1_strategies": ["足球", "歌剧"],
            "player2_strategies": ["足球", "歌剧"],
        },
        {
            "name": "猎鹿博弈",
            "player1_matrix": [[4, 0], [3, 3]],
            "player2_matrix": [[4, 3], [0, 3]],
            "player1_strategies": ["猎鹿", "猎兔"],
            "player2_strategies": ["猎鹿", "猎兔"],
        },
        {
            "name": "石头剪刀布",
            "player1_matrix": [[0, -1, 1], [1, 0, -1], [-1, 1, 0]],
            "player2_matrix": [[0, 1, -1], [-1, 0, 1], [1, -1, 0]],
            "player1_strategies": ["石头", "剪刀", "布"],
            "player2_strategies": ["石头", "剪刀", "布"],
        },
    ]
