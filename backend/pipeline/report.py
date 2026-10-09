"""Final compilation report, assembled only from real stage results."""

from __future__ import annotations

from typing import Optional

from .session import CompilationSession


def build_report(s: CompilationSession, validation: Optional[dict] = None) -> dict:
    g = lambda st: (s.stages[st].data or {})  # noqa: E731
    lex, par, ast, sem, ir, cfg, dna, evo, twin, cg, ex = (
        g("lexer"), g("parser"), g("ast"), g("semantic"), g("ir"), g("cfg"), g("dna"), g("evolution"),
        g("twin"), g("codegen"), g("execution"))
    val = validation or g("validation")
    lines = s.source.count("\n") + 1 if s.source else 0
    opt = twin.get("optimized", {})
    best = None
    if twin.get("selectedCandidateId"):
        best = next((c for c in evo.get("candidates", []) if c["id"] == twin["selectedCandidateId"]), None)
    run = ex.get("run", {})
    metrics = val.get("metrics", {}) if val else {}
    return {
        "source": {"lines": lines, "characters": len(s.source)},
        "lexicalAnalysis": {"tokens": (lex.get("statistics") or {}).get("totalTokens")},
        "parsing": {"astNodes": par.get("astNodes"), "tokensRead": par.get("tokensRead"),
                    "ruleInvocations": par.get("ruleInvocations")},
        "semanticAnalysis": {"symbols": (sem.get("statistics") or {}).get("symbolCount"),
                             "errors": sem.get("errorCount"), "warnings": sem.get("warningCount")},
        "ir": {"instructions": ir.get("instructionCount")},
        "cfg": {k: (cfg.get("statistics") or {}).get(k) for k in ("blocks", "edges", "branches", "loops")},
        "programDNA": {"programId": dna.get("programId"), "features": dna.get("features"),
                       "signatures": dna.get("signatures")},
        "evolution": {"seed": evo.get("seed"), "generations": (evo.get("statistics") or {}).get("generationsRun"),
                      "population": (evo.get("statistics") or {}).get("populationSize"),
                      "candidates": (evo.get("statistics") or {}).get("totalCandidates"),
                      "bestCandidate": best["id"] if best else None,
                      "bestGenome": best["genome"] if best else [],
                      "bestFitness": best["fitness"] if best else 0.0,
                      "termination": evo.get("termination")},
        "digitalTwin": {"validatedCandidates": (twin.get("statistics") or {}).get("valid"),
                        "rejectedCandidates": (twin.get("statistics") or {}).get("rejected"),
                        "finalistsCertified": (twin.get("statistics") or {}).get("finalistsCertified"),
                        "impact": twin.get("digitalTwinImpact")},
        "passUsage": evo.get("passUsage"),
        "optimization": {"originalInstructions": opt.get("originalSize"), "optimizedInstructions": opt.get("staticSize"),
                         "instructionReductionPercent": (metrics.get("irInstructions") or {}).get("reductionPercent"),
                         "originalDynamicCost": opt.get("originalDynamicCost"),
                         "optimizedDynamicCost": opt.get("dynamicCost"),
                         "dynamicCostReductionPercent": (metrics.get("irDynamicCost") or {}).get("reductionPercent")},
        "execution": {"status": run.get("status"), "output": run.get("output"),
                      "returnValue": run.get("returnValue"), "instructionsExecuted": run.get("executed"),
                      "wallTimeMs": run.get("elapsedMs")},
        "validation": {"equivalent": bool(val.get("equivalent")) if val else None,
                       "benchmark": val.get("benchmark") if val else None, "metrics": metrics},
    }
