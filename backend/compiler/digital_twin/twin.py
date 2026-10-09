"""Digital Twin: behavioural validation of optimisation candidates.

The twin holds the *reference* behaviour of the original program (obtained by
really executing its IR) and, for every candidate, really executes the
candidate and compares observable behaviour:

* whole-program run: status, printed output, return value, runtime-error kind
  and final global state;
* function-level differential tests: each parameterised function is executed
  with seeded, boundary-heavy argument vectors on both the original and the
  candidate IR (this is what exposes bugs that a single whole-program run
  cannot, e.g. ``x / 2`` vs ``x >> 1`` on negative inputs).

Nothing is labelled correct without having been executed and compared.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from compiler.ir.instructions import IRProgram
from compiler.ir.interpreter import RunResult, run_function, run_program
from compiler.runtime import format_value

INT_POOL = [0, 1, -1, 2, -2, 3, -3, 7, -7, 10, 100, -100, 2147483647, -2147483648]
FLOAT_POOL = [0.0, 1.0, -1.0, 2.5, -2.5, 100.0]
STRING_POOL = ["", "a", "abc", "hello world"]
BOOL_POOL = [False, True]
POOLS = {"int": INT_POOL, "float": FLOAT_POOL, "string": STRING_POOL, "bool": BOOL_POOL}
QUICK_CASES = 8
THOROUGH_CASES = 60
FN_STEP_LIMIT = 20_000


class TwinError(Exception):
    pass


def _diff(ref: dict, cand: dict) -> List[dict]:
    out = []
    for k in ("status", "output", "returnValue", "error", "globals"):
        if ref[k] != cand[k]:
            out.append({"field": k, "reference": ref[k], "candidate": cand[k]})
    return out


def _safe_run(fn, *a, **k) -> RunResult:
    try:
        return fn(*a, **k)
    except Exception as e:  # a malformed candidate must be rejected, not crash the search
        return RunResult("RUNTIME_ERROR", [], None, None, "InvalidProgram",
                         f"{type(e).__name__}: {e}")


@dataclass
class TwinReport:
    level: str
    verdict: str
    output_match: bool
    reference: RunResult
    candidate: RunResult
    differences: List[dict]
    function_tests: List[dict]
    cases: int
    passed: int

    @property
    def valid(self) -> bool:
        return self.verdict == "VALID"

    def to_dict(self) -> dict:
        return {
            "level": self.level, "verdict": self.verdict, "outputMatch": self.output_match,
            "behavior": "MATCHED" if self.valid else "MISMATCH",
            "correctness": "VALID" if self.valid else "REJECTED",
            "wholeProgram": {"reference": self.reference.summary(), "candidate": self.candidate.summary(),
                             "match": not self.differences, "differences": self.differences},
            "functionTests": {"cases": self.cases, "passed": self.passed, "functions": self.function_tests},
        }


class DigitalTwin:
    def __init__(self, original: IRProgram, seed: int = 42, step_limit: int = 200_000):
        self.original = original
        self.seed = seed
        self.step_limit = step_limit
        self.reference = run_program(original, step_limit)
        if self.reference.status == "STEP_LIMIT":
            raise TwinError(f"The original program did not terminate within {step_limit} executed "
                            f"instructions, so no reference behaviour exists to validate against.")
        self._ref_behavior = self.reference.behavior()
        self._vector_cache: Dict[Tuple[str, str], List[List[Any]]] = {}
        self._ref_fn_cache: Dict[Tuple[str, str], dict] = {}
        self.functions = [f for f in original.functions if f.params and not f.synthetic]

    def vectors(self, fname: str, level: str) -> List[List[Any]]:
        key = (fname, level)
        if key in self._vector_cache:
            return self._vector_cache[key]
        fn = self.original.fn(fname)
        want = QUICK_CASES if level == "quick" else THOROUGH_CASES
        rng = random.Random(f"evo-comp:{self.seed}:{level}:{fname}")
        pools = [POOLS[p.type] for p in fn.params]
        total = 1
        for p in pools:
            total *= len(p)
        want = min(want, total)
        seen, vecs = set(), []
        first = [p[0] for p in pools]
        seen.add(repr(first))
        vecs.append(first)
        # deterministic boundary sweep: vary one parameter at a time
        for i, pool in enumerate(pools):
            for v in pool[1:]:
                vec = list(first)
                vec[i] = v
                if repr(vec) not in seen and len(vecs) < want:
                    seen.add(repr(vec))
                    vecs.append(vec)
        guard = 0
        while len(vecs) < want and guard < want * 50:
            guard += 1
            vec = [rng.choice(p) for p in pools]
            if repr(vec) not in seen:
                seen.add(repr(vec))
                vecs.append(vec)
        self._vector_cache[key] = vecs
        return vecs

    def _ref_fn(self, fname: str, args: List[Any]) -> dict:
        key = (fname, repr(args))
        if key not in self._ref_fn_cache:
            self._ref_fn_cache[key] = run_function(self.original, fname, args, FN_STEP_LIMIT).behavior()
        return self._ref_fn_cache[key]

    def validate(self, candidate: IRProgram, level: str = "quick") -> TwinReport:
        limit = max(2000, self.reference.executed * 4)
        cand = _safe_run(run_program, candidate, min(limit, self.step_limit))
        diffs = _diff(self._ref_behavior, cand.behavior())
        fn_reports: List[dict] = []
        cases = passed = 0
        cand_names = {f.name for f in candidate.functions}
        for f in self.functions:
            vecs = self.vectors(f.name, level)
            fr = {"name": f.name, "cases": len(vecs), "passed": 0, "failures": []}
            for args in vecs:
                cases += 1
                ref = self._ref_fn(f.name, args)
                if f.name not in cand_names:
                    d = [{"field": "function", "reference": "present", "candidate": "missing"}]
                    got = None
                else:
                    got = _safe_run(run_function, candidate, f.name, args, FN_STEP_LIMIT).behavior()
                    d = _diff(ref, got)
                if not d:
                    passed += 1
                    fr["passed"] += 1
                elif len(fr["failures"]) < 3:
                    fr["failures"].append({"args": [format_value(a) if not isinstance(a, str) else a for a in args],
                                           "reference": ref, "candidate": got, "differences": d})
            fn_reports.append(fr)
        ok = not diffs and passed == cases
        return TwinReport(level, "VALID" if ok else "REJECTED", not diffs, self.reference, cand,
                          diffs, fn_reports, cases, passed)
