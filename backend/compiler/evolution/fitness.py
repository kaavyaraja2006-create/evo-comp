"""Transparent fitness function.

    fitness = W_DYN * (1 - dyn / dyn0)  +  W_SIZE * (1 - size / size0)

* ``dyn``   weighted dynamic cost: sum of per-opcode weights over the
            instructions the candidate *actually executed* in the Digital
            Twin's run (see ``COST_WEIGHTS``).
* ``size``  static instruction count (labels excluded).
* ``*0``    the same quantities measured on the original program.

So fitness is the relative improvement over the original: 0 means "no better
than the original", positive means cheaper. Correctness is a HARD constraint:
a candidate the Digital Twin rejects gets no fitness at all and can never be
selected as a parent, elite, or final result.
"""

from __future__ import annotations

from typing import Optional

from compiler.ir.instructions import COST_WEIGHTS

W_DYNAMIC = 0.7
W_SIZE = 0.3


def compute_fitness(dyn: int, size: int, dyn0: int, size0: int) -> float:
    r_dyn = 1.0 - dyn / dyn0 if dyn0 else 0.0
    r_size = 1.0 - size / size0 if size0 else 0.0
    return round(W_DYNAMIC * r_dyn + W_SIZE * r_size, 6)


def describe() -> dict:
    return {
        "formula": "fitness = 0.7 * (1 - dynamicCost/dynamicCost0) + 0.3 * (1 - size/size0)",
        "weights": {"dynamicCost": W_DYNAMIC, "size": W_SIZE},
        "hardConstraint": "Candidates rejected by the Digital Twin have no fitness and are never selected.",
        "tieBreak": "higher fitness, then smaller size, then shorter genome, then lower candidate id",
        "costWeights": COST_WEIGHTS,
        "interpretation": "0 = same cost as the original program; higher is better; negative = worse.",
    }
