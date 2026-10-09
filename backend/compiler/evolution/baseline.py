"""Baseline comparison: what does the Digital Twin's correctness gate actually
buy you?

This runs the *identical* evolutionary search twice, from the same seed, on
the same program, against the same Digital Twin - once with the gate on
(the production configuration: a behaviourally-incorrect candidate can never
be selected) and once with it off (candidates are ranked by fitness alone,
and correctness is only recorded, never enforced). Both runs really execute
every candidate through the Digital Twin, so "is the ungated winner actually
correct?" is a real, measured fact in both cases - never assumed.

This is strictly more expensive than a normal compile (it runs the search
twice), so it is never part of the default pipeline; it is an on-demand,
separate measurement a caller opts into.
"""

from __future__ import annotations

from typing import Optional

from compiler.digital_twin.twin import DigitalTwin
from compiler.ir.instructions import IRProgram

from .engine import EvolutionConfig, EvolutionEngine


def run_baseline_comparison(ir: IRProgram, twin: DigitalTwin, base_cfg: EvolutionConfig,
                             opportunities: Optional[dict] = None) -> dict:
    gated_cfg = EvolutionConfig(**{**base_cfg.to_dict(), "correctness_gate": True})
    ungated_cfg = EvolutionConfig(**{**base_cfg.to_dict(), "correctness_gate": False})

    gated = EvolutionEngine(ir, twin, gated_cfg, opportunities).run()
    ungated = EvolutionEngine(ir, twin, ungated_cfg, opportunities).run()

    def _winner(result: dict) -> Optional[dict]:
        bid = result["bestCandidateId"]
        if bid is None:
            return None
        return next(c for c in result["candidates"] if c["id"] == bid)

    gated_winner = _winner(gated)
    ungated_winner = _winner(ungated)
    dyn0, size0 = twin.reference.cost, ir.instr_count()

    def _summarize(label: str, w: Optional[dict]) -> dict:
        if w is None:
            return {"label": label, "found": False}
        dyn_reduction = round((1 - w["dynamicCost"] / dyn0) * 100, 2) if dyn0 else 0.0
        size_reduction = round((1 - w["staticSize"] / size0) * 100, 2) if size0 else 0.0
        return {
            "label": label, "found": True, "candidateId": w["id"], "genome": w["genome"],
            "fitness": w["fitness"] if w["fitness"] is not None else w["shadowFitness"],
            "staticSize": w["staticSize"], "dynamicCost": w["dynamicCost"],
            "dynamicCostReductionPercent": dyn_reduction, "staticSizeReductionPercent": size_reduction,
            "actuallyCorrect": w["status"] == "VALID",
        }

    gated_summary = _summarize("gated (Digital Twin enforced)", gated_winner)
    ungated_summary = _summarize("ungated (fitness-only, no correctness gate)", ungated_winner)

    incorrect_shipped = ungated_summary["found"] and not ungated_summary["actuallyCorrect"]
    both_found = gated_summary["found"] and ungated_summary["found"]
    speed_gap = (round(ungated_summary["dynamicCostReductionPercent"] - gated_summary["dynamicCostReductionPercent"], 2)
                 if both_found else None)

    if incorrect_shipped:
        headline = (
            f"Without the Digital Twin, the fitness-only search would have shipped an INCORRECT program "
            f"(candidate {ungated_summary['candidateId']}, {ungated_summary['dynamicCostReductionPercent']}% faster "
            f"but behaviourally wrong). The gated search shipped a correct program instead "
            f"({gated_summary['dynamicCostReductionPercent']}% faster, verified). "
            f"That is the Digital Twin's measured value on this run: "
            f"{'a ' + str(speed_gap) + ' percentage-point speed gap for correctness' if speed_gap else 'a safety margin'}."
        )
    elif both_found and ungated_summary["candidateId"] != gated_summary["candidateId"]:
        headline = (
            "Without the Digital Twin, the fitness-only search would have shipped a different candidate than the "
            "gated search, but that candidate happens to also be correct on this program - so this run doesn't "
            "demonstrate a regression, though the gate is still what verified that rather than assuming it."
        )
    elif both_found:
        headline = (
            "On this run, the fitness-only winner and the Digital-Twin-gated winner are the same candidate, and it "
            "is correct - the unsound passes didn't happen to win the search this time. Try a different seed or "
            "program to see a case where they diverge."
        )
    else:
        headline = "No improving candidate was found by either search on this program."

    return {
        "seed": base_cfg.seed, "population": base_cfg.population, "generations": base_cfg.generations,
        "original": {"staticSize": size0, "dynamicCost": dyn0},
        "gated": gated_summary, "ungated": ungated_summary,
        "gatedStatistics": gated["statistics"], "ungatedStatistics": ungated["statistics"],
        "incorrectCandidateWouldShip": incorrect_shipped,
        "speedGapPercentagePoints": speed_gap,
        "headline": headline,
        "methodology": (
            "Both searches use the identical evolutionary algorithm, the same random seed, the same population and "
            "generation counts, and validate every candidate through the same Digital Twin instance. The only "
            "difference is whether a candidate's correctness verdict can veto its selection. Every number above "
            "comes from actually running both searches to completion - nothing here is estimated."
        ),
    }
