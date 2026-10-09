"""The compilation pipeline: real stage execution with dependency enforcement.

Each stage consumes the actual object produced by its predecessor (kept in
``session.internal``) and stores its real result in the session.
"""

from __future__ import annotations

import statistics as stats
import time
import traceback
from typing import Callable, Dict, List, Optional, Tuple

from lexer.lexer import Lexer
from models.compilation import compute_statistics, LexerPerformance, LexicalErrorModel, TokenModel
from compiler.ast.builder import build_ast
from compiler.cfg.builder import build_cfg
from compiler.codegen.bytecode import ISA
from compiler.codegen.generator import generate_bytecode
from compiler.digital_twin.twin import DigitalTwin, TwinError
from compiler.dna.extractor import extract_dna
from compiler.evm.machine import EvoVM
from compiler.evm.verifier import verify
from compiler.evolution.baseline import run_baseline_comparison
from compiler.evolution.engine import EvolutionConfig, EvolutionEngine
from compiler.evolution.fitness import compute_fitness
from compiler.evolution.passes import PASSES, SOUND_PASSES, SPECULATIVE_PASSES, apply_genome, count_opportunities
from compiler.ir.generator import generate_ir
from compiler.parser.parser import parse_tokens
from compiler.runtime import format_value
from compiler.semantic.analyzer import analyze
from .report import build_report
from .session import DEPENDS, STAGE_META, STAGES, CompilationSession, StageBlocked, StageState

BENCH_RUNS = 30
BENCH_WARMUP = 3


class StageFailure(Exception):
    """A stage ran and produced a real negative result (not a compiler bug)."""

    def __init__(self, message: str, data: Optional[dict] = None):
        super().__init__(message)
        self.data = data


def _need(session: CompilationSession, key: str):
    return session.internal[key]


# ------------------------------------------------------------------ stages
def stage_lexer(s: CompilationSession):
    t0 = time.perf_counter()
    result = Lexer(s.source).tokenize()
    ms = (time.perf_counter() - t0) * 1000
    data = {
        "success": result.success, "tokens": [TokenModel(**t.to_dict()).model_dump() for t in result.tokens],
        "statistics": compute_statistics(result.tokens).model_dump(),
        "errors": [LexicalErrorModel(**e.to_dict()).model_dump() for e in result.errors],
        "performance": LexerPerformance(inputSizeCharacters=len(s.source),
                                        inputSizeLines=s.source.count("\n") + 1 if s.source else 0,
                                        tokensGenerated=len(result.tokens), lexingTimeMs=round(ms, 4)).model_dump(),
    }
    if not result.success:
        raise StageFailure(f"{len(result.errors)} lexical error(s)", data)
    s.internal["tokens"] = result.tokens
    return data, f"{len(result.tokens)} tokens"


def stage_parser(s: CompilationSession):
    r = parse_tokens(_need(s, "tokens"))
    data = r.to_dict()
    if not r.success:
        raise StageFailure(f"{len(r.errors)} syntax error(s)", data)
    s.internal["parse"] = r
    return data, f"{r.node_count} AST nodes from {r.tokens_consumed} tokens"


def stage_ast(s: CompilationSession):
    a = build_ast(_need(s, "parse").program)
    data = a.to_dict()
    if not all(i["passed"] for i in a.invariants):
        raise StageFailure("AST invariant violated", data)
    s.internal["ast"] = a
    return data, f"{a.node_count()} nodes, depth {data['statistics']['maxDepth']}"


def stage_semantic(s: CompilationSession):
    r = analyze(_need(s, "ast"))
    data = r.to_dict()
    if not r.success:
        raise StageFailure(f"{r.error_count} semantic error(s)", data)
    s.internal["sem"] = r
    return data, f"{len(r.symbols)} symbols, {r.error_count} errors, {r.warning_count} warnings"


def stage_ir(s: CompilationSession):
    ir, ms = generate_ir(_need(s, "ast"), _need(s, "sem"))
    s.internal["ir"] = ir
    data = ir.to_dict()
    data["text"] = ir.text()
    data["generateMs"] = round(ms, 4)
    data["statistics"] = {"instructions": ir.instr_count(), "functions": len(ir.functions),
                          "labels": sum(1 for _, i in ir.all_instrs() if i.op == "LABEL"),
                          "temporaries": len({(f.name, i.dest.name) for f, i in ir.all_instrs()
                                              if i.dest is not None and i.dest.kind == "temp"})}
    return data, f"{ir.instr_count()} instructions"


def stage_cfg(s: CompilationSession):
    c = build_cfg(_need(s, "ir"))
    s.internal["cfg"] = c
    data = c.to_dict()
    st = data["statistics"]
    return data, f"{st['blocks']} blocks, {st['edges']} edges, {st['loops']} loops"


def stage_dna(s: CompilationSession):
    ir = _need(s, "ir")
    opps = count_opportunities(ir)
    s.internal["opportunities"] = opps
    dna = extract_dna(s.source, _need(s, "ast"), _need(s, "sem"), ir, _need(s, "cfg"), opps)
    s.internal["dna"] = dna
    return dna, f"{len(dna['features'])} features, program {dna['programId']}"


def _pass_usage(candidates: list) -> dict:
    """Real aggregate counts over the actual candidates the search explored:
    how often each pass was proposed (appeared in a genome), and how often a
    genome containing it was ultimately rejected by the (quick) Digital
    Twin check — i.e. how much work each speculative pass actually made for
    the validator, not an estimate."""
    usage: Dict[str, dict] = {name: {"proposed": 0, "proposedValid": 0, "proposedRejected": 0}
                              for name in PASSES}
    for c in candidates:
        seen_in_genome = set(c["genome"])
        for name in seen_in_genome:
            u = usage[name]
            u["proposed"] += 1
            if c["status"] == "VALID":
                u["proposedValid"] += 1
            else:
                u["proposedRejected"] += 1
    return usage


def stage_evolution(s: CompilationSession):
    o = s.options
    try:
        twin = DigitalTwin(_need(s, "ir"), o.seed, o.step_limit)
    except TwinError as e:
        raise StageFailure(str(e))
    cfg = EvolutionConfig(seed=o.seed, population=o.population, generations=o.generations)
    result = EvolutionEngine(_need(s, "ir"), twin, cfg, s.internal.get("opportunities")).run()
    result["reference"] = twin.reference.summary()
    usage = _pass_usage(result["candidates"])
    for p in result["dnaGuidance"]["passes"]:
        p["timesProposed"] = usage[p["name"]]["proposed"]
        p["timesInRejectedCandidate"] = usage[p["name"]]["proposedRejected"]
    result["passUsage"] = usage
    s.internal["twin"] = twin
    s.internal["evolution"] = result
    st = result["statistics"]
    best = st["bestFitness"]
    return result, (f"{st['generationsRun']} generations, {st['totalCandidates']} candidates, "
                    f"best fitness {best if best is not None else 'n/a'}")


def stage_twin(s: CompilationSession):
    ir = _need(s, "ir")
    twin: DigitalTwin = _need(s, "twin")
    evo = _need(s, "evolution")
    cands = {c["id"]: c for c in evo["candidates"]}
    considered = []
    finalists = []
    selected_id = None
    for cid in evo["hallOfFame"]:
        c = cands[cid]
        genome = c["genome"]
        opt, _ = apply_genome(ir, genome)
        rep = twin.validate(opt, "thorough")
        entry = {"candidateId": cid, "fitness": c["fitness"], "verdict": rep.verdict,
                 "cases": rep.cases, "passed": rep.passed}
        considered.append(entry)
        finalists.append({"candidateId": cid, "genome": genome, "report": rep.to_dict()})
        if rep.valid and selected_id is None:
            selected_id = cid
            s.internal["selected"] = {"id": cid, "genome": genome, "ir": opt}
    fallback = selected_id is None
    if fallback:
        s.internal["selected"] = {"id": None, "genome": [], "ir": apply_genome(ir, [])[0]}
    sel = s.internal["selected"]
    opt_ir = sel["ir"]
    cert = {e["candidateId"]: e["verdict"] for e in considered}
    matrix = []
    for c in evo["candidates"]:
        rep = evo["twinPool"][c["irHash"]]
        matrix.append({
            "candidateId": c["id"], "generation": c["generation"], "fitness": c["fitness"],
            "outputMatch": rep["outputMatch"], "status": c["status"],
            "functionTests": f"{rep['functionTests']['passed']}/{rep['functionTests']['cases']}",
            "certification": cert.get(c["id"]), "irHash": c["irHash"], "genome": c["genome"],
            "usesSpeculativePass": c["usesSpeculativePass"], "selected": c["id"] == selected_id,
        })
    rejected = [m for m in matrix if m["status"] == "REJECTED"]
    seen, rej_examples = set(), []
    for m in rejected:
        if m["irHash"] in seen:
            continue
        seen.add(m["irHash"])
        rej_examples.append({"candidateId": m["candidateId"], "genome": m["genome"],
                             "report": evo["twinPool"][m["irHash"]]})
        if len(rej_examples) >= 6:
            break
    history = evo["historyPool"].get(",".join(sel["genome"]), [])
    ref = twin.reference
    from compiler.ir.interpreter import run_program
    opt_run = run_program(opt_ir, s.options.step_limit)
    data = {
        "reference": ref.summary(),
        "selectedCandidateId": selected_id,
        "fallbackToOriginal": fallback,
        "selectionRule": "Only candidates that pass thorough Digital Twin validation are eligible; among those, "
                         "the highest fitness wins (ties: smaller program, shorter genome).",
        "considered": considered, "finalists": finalists, "matrix": matrix,
        "rejectedExamples": rej_examples,
        "statistics": {"candidatesEvaluated": len(matrix), "valid": len(matrix) - len(rejected),
                       "rejected": len(rejected), "finalistsCertified": sum(1 for e in considered if e["verdict"] == "VALID"),
                       "finalistsRejected": sum(1 for e in considered if e["verdict"] == "REJECTED")},
        "optimized": {
            "genome": sel["genome"], "ir": opt_ir.to_dict(), "irText": opt_ir.text(), "history": history,
            "staticSize": opt_ir.instr_count(), "dynamicCost": opt_run.cost, "executed": opt_run.executed,
            "originalSize": ir.instr_count(), "originalDynamicCost": ref.cost, "originalExecuted": ref.executed,
        },
    }
    # ---- "what if there were no Digital Twin?" counterfactual --------------
    # Every candidate already has dynamicCost/staticSize recorded regardless
    # of whether the Digital Twin accepted it (only `fitness` is withheld for
    # a rejected candidate). So we can honestly answer "which candidate would
    # a fitness-only search have shipped?" by scoring every candidate with
    # the same public formula and ignoring correctness status entirely - no
    # re-running anything, just re-ranking data already produced by this run.
    dyn0, size0 = ref.cost, ir.instr_count()
    scored = []
    for c in evo["candidates"]:
        hf = compute_fitness(c["dynamicCost"], c["staticSize"], dyn0, size0)
        scored.append((hf, c["staticSize"], len(c["genome"]), int(c["id"][1:]), c))
    scored.sort(key=lambda t: (-t[0], t[1], t[2], t[3]))
    uncorrected_winner = scored[0][4] if scored else None
    uncorrected_would_differ = bool(uncorrected_winner) and uncorrected_winner["id"] != selected_id
    what_if = None
    if uncorrected_winner is not None:
        winner_hash = uncorrected_winner["irHash"]
        winner_report = evo["twinPool"][winner_hash]
        what_if = {
            "wouldSelect": uncorrected_winner["id"],
            "genome": uncorrected_winner["genome"],
            "hypotheticalFitness": scored[0][0],
            "actuallyCorrect": uncorrected_winner["status"] == "VALID",
            "differsFromActualSelection": uncorrected_would_differ,
            "wholeProgramDifferences": winner_report["wholeProgram"]["differences"],
            "functionTestResult": f"{winner_report['functionTests']['passed']}/{winner_report['functionTests']['cases']}",
            "explanation": (
                "Without the Digital Twin's correctness gate, a search that ranked candidates by fitness "
                "alone would have shipped this candidate instead of the one actually selected - and it is "
                "behaviorally INCORRECT (see the differences above)."
                if uncorrected_would_differ and uncorrected_winner["status"] != "VALID"
                else "Without the Digital Twin's correctness gate, the fitness-only winner happens to be the "
                     "same candidate the gated search actually selected, and it is correct - but this is "
                     "incidental to this particular program, not guaranteed."
                if not uncorrected_would_differ
                else "Without the Digital Twin's correctness gate, a fitness-only search would have shipped a "
                     "different candidate than the gated search selected, but that candidate happens to also "
                     "be correct on this program."
            ),
        }
    rejection_rate = round(len(rejected) / len(matrix), 4) if matrix else 0.0
    data["digitalTwinImpact"] = {
        "candidatesEvaluated": len(matrix), "rejectedCount": len(rejected), "rejectionRate": rejection_rate,
        "finalistsConsidered": len(considered),
        "finalistsCertified": sum(1 for e in considered if e["verdict"] == "VALID"),
        "finalistsRejected": sum(1 for e in considered if e["verdict"] == "REJECTED"),
        "whatIf": what_if,
        "headline": (
            f"{len(rejected)} of {len(matrix)} candidates explored ({rejection_rate * 100:.1f}%) were rejected "
            f"by the Digital Twin." + (
                " Without it, an incorrect candidate would have been selected as the final optimized program."
                if what_if and what_if["differsFromActualSelection"] and not what_if["actuallyCorrect"]
                else " On this run, the fitness-only winner happened to be correct anyway, but the Digital "
                     "Twin is what verified that rather than assumed it."
            )
        ),
    }

    label = f"selected {selected_id}" if selected_id else "no candidate beat the original; original kept"
    return data, f"{label} ({data['statistics']['valid']} valid, {data['statistics']['rejected']} rejected)"


def stage_codegen(s: CompilationSession):
    sel = _need(s, "selected")
    bo, ms1 = generate_bytecode(sel["ir"], "optimized")
    bg, ms2 = generate_bytecode(_need(s, "ir"), "original")
    s.internal["bc_opt"], s.internal["bc_orig"] = bo, bg
    data = {"optimized": bo.to_dict(), "original": bg.to_dict(), "listing": bo.listing(),
            "originalListing": bg.listing(), "generateMs": round(ms1 + ms2, 4),
            "statistics": {"optimizedSize": len(bo.code), "originalSize": len(bg.code),
                           "functions": len(bo.functions)},
            "source": "Optimized IR" if sel["id"] else "Original IR (no candidate improved on it)"}
    return data, f"{len(bo.code)} bytecode instructions"


def stage_evovm(s: CompilationSession):
    vo, vg = verify(_need(s, "bc_opt")), verify(_need(s, "bc_orig"))
    data = {
        "isa": [{"op": op, "operand": v[0], "stackEffect": v[1], "description": v[2]} for op, v in ISA.items()],
        "verification": {"optimized": vo, "original": vg},
        "machine": {"model": "stack machine with per-call local slots and named globals",
                    "maxCallDepth": 200, "intWidth": 32,
                    "entry": "bootstrap stub: CALL __start; HALT"},
        "loaded": vo["ok"] and vg["ok"],
    }
    if not data["loaded"]:
        raise StageFailure("Bytecode verification failed", data)
    return data, "verified: stack depth, jump targets, call arity"


def stage_execution(s: CompilationSession):
    vm = EvoVM(_need(s, "bc_opt"), step_limit=max(s.options.step_limit * 10, 100_000))
    r = vm.run(trace=True)
    s.internal["exec"] = r
    data = {"run": r.summary(), "trace": r.trace, "traceTruncated": r.trace_truncated,
            "programFaulted": r.status == "RUNTIME_ERROR"}
    if r.status == "STEP_LIMIT":
        raise StageFailure("Execution exceeded the instruction limit", data)
    label = "HALTED" if r.status == "HALTED" else f"runtime error: {r.error_kind}"
    return data, f"{label}, {r.executed} instructions executed"


def _bench(prog) -> dict:
    vm = EvoVM(prog, step_limit=5_000_000)
    for _ in range(BENCH_WARMUP):
        vm.run()
    times = [vm.run().elapsed_ms for _ in range(BENCH_RUNS)]
    med = stats.median(times)
    spread = (max(times) - min(times)) / med if med > 0 else 0.0
    return {"runs": BENCH_RUNS, "medianMs": round(med, 5), "minMs": round(min(times), 5),
            "maxMs": round(max(times), 5), "relativeSpread": round(spread, 3)}


def _same(a_status, a_out, a_ret, a_err, b_status, b_out, b_ret, b_err) -> Tuple[bool, List[dict]]:
    diffs = []
    # canonicalise status vocabulary: the IR interpreter reports "OK" and EvoVM
    # reports "HALTED" for the same successful-completion outcome.
    ok_status = lambda st: "ERROR" if st == "RUNTIME_ERROR" else "SUCCESS" if st in ("OK", "HALTED") else st  # noqa: E731
    if ok_status(a_status) != ok_status(b_status):
        diffs.append({"field": "status", "a": a_status, "b": b_status})
    if a_out != b_out:
        diffs.append({"field": "output", "a": a_out, "b": b_out})
    if a_ret != b_ret:
        diffs.append({"field": "returnValue", "a": a_ret, "b": b_ret})
    if a_err != b_err:
        diffs.append({"field": "error", "a": a_err, "b": b_err})
    return not diffs, diffs


def stage_validation(s: CompilationSession):
    twin: DigitalTwin = _need(s, "twin")
    ref = twin.reference
    opt = _need(s, "exec")
    orig_run = EvoVM(_need(s, "bc_orig"), step_limit=max(s.options.step_limit * 10, 100_000)).run()
    ref_ret = None if ref.return_value is None else format_value(ref.return_value)
    opt_ret = format_value(opt.return_value) if opt.has_return else None
    orig_ret = format_value(orig_run.return_value) if orig_run.has_return else None
    eq_ref, d1 = _same(ref.status, ref.output, ref_ret, ref.error_kind, opt.status, opt.output, opt_ret, opt.error_kind)
    eq_bc, d2 = _same(orig_run.status, orig_run.output, orig_ret, orig_run.error_kind,
                      opt.status, opt.output, opt_ret, opt.error_kind)
    equivalent = eq_ref and eq_bc
    sel = _need(s, "selected")
    bench_o, bench_p = _bench(_need(s, "bc_orig")), _bench(_need(s, "bc_opt"))
    ir = _need(s, "ir")

    def pct(a, b):
        return round((a - b) / a * 100, 2) if a else 0.0

    noisy = max(bench_o["relativeSpread"], bench_p["relativeSpread"]) > 0.5
    data = {
        "equivalent": equivalent,
        "comparisons": {
            "referenceVsOptimizedBytecode": {"equivalent": eq_ref, "differences": d1,
                "reference": {"engine": "IR interpreter (original IR)", **ref.summary()},
                "candidate": {"engine": "EvoVM (optimized bytecode)", **opt.summary()}},
            "originalBytecodeVsOptimizedBytecode": {"equivalent": eq_bc, "differences": d2,
                "reference": {"engine": "EvoVM (original bytecode)", **orig_run.summary()},
                "candidate": {"engine": "EvoVM (optimized bytecode)", **opt.summary()}},
        },
        "metrics": {
            "irInstructions": {"original": ir.instr_count(), "optimized": sel["ir"].instr_count(),
                               "reductionPercent": pct(ir.instr_count(), sel["ir"].instr_count())},
            "bytecodeSize": {"original": len(_need(s, "bc_orig").code), "optimized": len(_need(s, "bc_opt").code),
                             "reductionPercent": pct(len(_need(s, "bc_orig").code), len(_need(s, "bc_opt").code))},
            "executedInstructions": {"original": orig_run.executed, "optimized": opt.executed,
                                     "reductionPercent": pct(orig_run.executed, opt.executed)},
        },
        "benchmark": {"original": bench_o, "optimized": bench_p,
                      "speedup": round(bench_o["medianMs"] / bench_p["medianMs"], 3) if bench_p["medianMs"] else None,
                      "noisy": noisy,
                      "note": ("Wall-clock time on a tiny program is dominated by measurement noise; treat it as "
                               "indicative only. Executed-instruction counts are exact and deterministic."
                               + (" Spread between runs exceeded 50%, so the timing comparison is unreliable."
                                  if noisy else ""))},
    }
    # dynamic IR cost of the selected program comes from the optimised IR run in the twin stage
    twin_data = s.stages["twin"].data or {}
    data["metrics"]["irDynamicCost"] = {
        "original": ref.cost, "optimized": (twin_data.get("optimized") or {}).get("dynamicCost"),
        "reductionPercent": pct(ref.cost, (twin_data.get("optimized") or {}).get("dynamicCost", ref.cost)),
    }
    s.stages["validation"].data = data  # visible to the report builder
    data["report"] = build_report(s, data)
    if not equivalent:
        raise StageFailure("Optimized program is NOT equivalent to the original", data)
    return data, "Equivalent: YES"


RUNNERS: Dict[str, Callable] = {
    "lexer": stage_lexer, "parser": stage_parser, "ast": stage_ast, "semantic": stage_semantic,
    "ir": stage_ir, "cfg": stage_cfg, "dna": stage_dna, "evolution": stage_evolution, "twin": stage_twin,
    "codegen": stage_codegen, "evovm": stage_evovm, "execution": stage_execution, "validation": stage_validation,
}

FRIENDLY = {s: STAGE_META[s]["label"] for s in STAGES}


def explain_block(session: CompilationSession, stage: str) -> Tuple[str, Optional[str]]:
    dep = DEPENDS[stage]
    while dep is not None:
        st = session.stages[dep]
        if st.status != "completed":
            if st.status == "failed":
                why = f"{FRIENDLY[dep]} failed ({st.error})"
            else:
                why = f"{FRIENDLY[dep]} has not been run yet"
            return f"Cannot run {FRIENDLY[stage]}: {why}.", dep
        dep = DEPENDS[dep]
    return "", None


def run_stage(session: CompilationSession, stage: str) -> StageState:
    if stage not in RUNNERS:
        raise KeyError(stage)
    dep = DEPENDS[stage]
    if dep is not None and session.stages[dep].status != "completed":
        reason, by = explain_block(session, stage)
        raise StageBlocked(stage, reason, by)
    session.reset_from(stage)
    st = session.stages[stage]
    t0 = time.perf_counter()
    try:
        data, summary = RUNNERS[stage](session)
        st.status, st.data, st.summary = "completed", data, summary
    except StageFailure as f:
        st.status, st.error, st.data = "failed", str(f), f.data
        st.summary = str(f)
    except Exception as e:  # a genuine compiler bug: report it honestly
        st.status = "failed"
        st.error = f"Internal compiler error in {FRIENDLY[stage]}: {type(e).__name__}: {e}"
        st.summary = st.error
        session.internal["_trace_" + stage] = traceback.format_exc()
    st.duration_ms = (time.perf_counter() - t0) * 1000
    return st


def run_all(session: CompilationSession) -> Optional[str]:
    """Run every stage in order; stop at the first failure. Returns the
    failing stage name, if any."""
    for stage in STAGES:
        st = run_stage(session, stage)
        if st.status != "completed":
            return stage
    return None


class BaselineUnavailable(Exception):
    """The evolution stage hasn't run yet, so there's nothing to compare against."""


def run_baseline_comparison_for_session(session: CompilationSession) -> dict:
    """On-demand, non-blocking comparison of the gated search against the same
    search with the Digital Twin's correctness gate turned off. This runs a
    full second evolutionary search (same seed, same population/generations,
    same Digital Twin instance), so it is materially more expensive than a
    normal compile - that's why it isn't part of ``run_all``/the staged
    pipeline, and is only triggered when a caller explicitly asks for it.
    Cached on the session so repeated requests don't redo the work."""
    if session.internal.get("twin") is None or session.internal.get("ir") is None:
        raise BaselineUnavailable("Run the pipeline through the Evolution stage first.")
    if "baselineComparison" not in session.internal:
        o = session.options
        cfg = EvolutionConfig(seed=o.seed, population=o.population, generations=o.generations)
        session.internal["baselineComparison"] = run_baseline_comparison(
            session.internal["ir"], session.internal["twin"], cfg, session.internal.get("opportunities"))
    return session.internal["baselineComparison"]
