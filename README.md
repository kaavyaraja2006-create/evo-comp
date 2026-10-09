<div align="center">

# EVO-COMP

### Adaptive Evolutionary Compiler with Program-DNA-Guided Optimization and Digital-Twin Validation

**Phase 2+ — Full Pipeline: Parser through Final Validation**

[![Phase](https://img.shields.io/badge/Phase-2%2B%20(13%20stages)-4caf7d?style=flat-square)](#roadmap)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](#tech-stack)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-61DAFB?style=flat-square&logo=react&logoColor=white)](#tech-stack)
[![Tests](https://img.shields.io/badge/tests-108%20passing-4caf7d?style=flat-square)](#testing)
[![License](https://img.shields.io/badge/status-academic%20project-lightgrey?style=flat-square)](#)

*A real, working compiler — not a mockup. Every token, AST node, symbol, IR
instruction, optimization decision, and validation verdict shown in the UI is
produced by actually running that stage's code, not by hardcoded or simulated
output.*

</div>

---

## Table of Contents

- [What is EVO-COMP?](#what-is-evo-comp)
- [What This Repository Actually Does](#what-this-repository-actually-does)
- [Architecture](#architecture)
- [The 13 Stages](#the-13-stages)
- [What Makes This Not a Mockup](#what-makes-this-not-a-mockup)
- [Tech Stack](#tech-stack)
- [EvoLang Language Reference](#evolang-language-reference)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Worked Example](#worked-example)
- [Design Principles](#design-principles)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## What is EVO-COMP?

EVO-COMP is a research compiler for a small language called **EvoLang**. It
combines a conventional compiler pipeline (lex → parse → semantic analysis →
IR → codegen → execution) with two less-conventional stages:

- **Program DNA** — a deterministic structural fingerprint of a program
  (operator mix, loop/branch shape, call graph, instruction-category
  histogram, Halstead metrics, ...) that is used to *guide* optimization
  rather than just describe the program after the fact.
- **Evolutionary optimization validated by a Digital Twin** — instead of a
  fixed sequence of optimization passes, EVO-COMP runs a genetic search over
  *orderings* of optimization passes. Every candidate this search proposes is
  executed — never just statically reasoned about — by a **Digital Twin**: a
  reference engine that runs the original program and the candidate side by
  side and rejects the candidate the moment their observable behavior
  diverges. Two of the ten available passes are *deliberately unsound*
  (they encode real compiler-optimization folklore that is subtly wrong), so
  the Digital Twin has genuine, non-trivial work to do — this is
  demonstrated, not asserted (see [Worked Example](#worked-example)).

## What This Repository Actually Does

```
Source → Lexer → Parser → AST → Semantic Analysis → IR → CFG →
Program DNA → Evolutionary Optimization → Digital Twin → Target Code (EvoVM
bytecode) → EvoVM Execution → Final Validation
```

**All 13 stages are implemented as real code**, run end-to-end, and covered
by 108 automated tests (see [Testing](#testing)). Nothing downstream of the
lexer is mocked, hardcoded, or simulated:

- The parser is a genuine recursive-descent parser over the real token
  stream, with panic-mode error recovery that reports *every* syntax error
  in a program in one pass, not just the first.
- The semantic analyzer does real scope resolution and type checking, with
  16 error codes and 4 warning codes, each backed by a test that triggers it.
- The optimizer's 10 passes are real dataflow/CFG-based transformations
  (constant folding and propagation, copy propagation, algebraic
  simplification, strength reduction, redundant-computation elimination,
  temp forwarding, dead-code elimination, branch simplification) plus two
  intentionally unsound speculative passes.
- The Digital Twin really executes every candidate program — the whole
  program once, and every parameterized function individually against
  seeded argument vectors (boundary values, then a deterministic random
  fill) — and compares actual output, return values, runtime-error kind,
  and final global state.
- The target machine, EvoVM, is a real stack-based bytecode interpreter with
  a static bytecode verifier (jump targets, stack-depth consistency, call
  arity, slot bounds) that runs before any bytecode is executed.
- Final validation re-executes both the original and optimized programs and
  reports an honest **NOT EQUIVALENT** if they ever actually disagree — the
  pipeline does not paper over discrepancies it detects.

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────────────┐
│   Frontend   │     │                      Backend (FastAPI)               │
│  React + TS  │◄───►│  /api/lex        (Phase 1, stateless)                │
│   + Monaco   │     │  /api/session    (create a compilation session)      │
│              │     │  /api/session/{id}/run/{stage}  (run one stage)      │
│              │     │  /api/compile    (one-shot: run all 13 stages)       │
└─────────────┘     │  /api/stages     (stage metadata for the UI)         │
                     └──────────────────────────────────────────────────────┘
                                          │
                     ┌────────────────────┴────────────────────────────────┐
                     │              CompilationSession                     │
                     │  13 stages, each consuming the previous stage's     │
                     │  REAL in-memory object (tokens → AST → IR → ...)    │
                     │  A dependency graph blocks a stage from running     │
                     │  before its prerequisite has completed, and         │
                     │  re-running an earlier stage invalidates every      │
                     │  stage downstream of it.                            │
                     └──────────────────────────────────────────────────────┘
```

Two ways to drive the pipeline, both exercising the same stage code:

1. **Stage-by-stage** (the UI's default): each stage is a button; the UI
   shows real input → transformation → output for that stage before letting
   you move to the next one. This matches the "research lab" structure of
   the Phase 1 lexer lab, extended to all 13 stages.
2. **One-shot** (`POST /api/compile`): run everything and get the full
   report back in one call — used by the pytest end-to-end suite and
   available as a "Compile" button in the UI.

## The 13 Stages

| # | Stage | Input | Real transformation | Output |
|---|-------|-------|----------------------|--------|
| 1 | Lexer | source text | hand-written character scanner | token stream |
| 2 | Parser | tokens | recursive-descent parsing, panic-mode recovery | typed syntax tree + parse trace |
| 3 | AST | parse tree | id/parent/depth assignment, invariant checks | finalized AST |
| 4 | Semantic Analysis | AST | scope resolution, type checking | symbol table + diagnostics + typed expressions |
| 5 | IR | AST + types | three-address code generation, real short-circuit control flow | IR (three-address code) |
| 6 | CFG | IR | leader-based basic blocks, dominators, natural loops | control-flow graph |
| 7 | Program DNA | AST + IR + CFG | deterministic structural feature extraction | explainable fingerprint + optimization-opportunity counts |
| 8 | Evolution | IR + DNA | genetic search over pass-sequence genomes | generations of candidates with fitness |
| 9 | Digital Twin | evolution finalists | thorough differential execution vs. the original | certified optimized IR |
| 10 | Target Code | certified IR | three-address code → stack bytecode | EvoVM bytecode |
| 11 | EvoVM | bytecode | static verification (jumps, stack depth, call arity) | verified program image |
| 12 | Execution | verified bytecode | stack-machine interpretation with tracing | output, return value, trace |
| 13 | Validation | original + optimized executions | equivalence check + benchmark | final compilation report |

Each stage's metadata (button label, loading messages, and a plain-English
input/transformation/output description) is served by `GET /api/stages` and
comes from `backend/pipeline/session.py::STAGE_META` — the same object the
pipeline itself uses to decide stage order and dependencies, so the UI's
description of a stage can't drift from what the stage actually does.

## What Makes This Not a Mockup

A few concrete, checkable claims, each backed by a test:

- **Multiple errors in one pass.** `int x = ;\nint y = ;\nint z = ;` produces
  *three* syntax errors, not one truncated run
  (`tests/test_parser.py::test_multiple_errors_recovered_in_one_pass`).
- **Runtime semantics are shared, not duplicated.** `compiler/runtime.py`
  (32-bit wraparound, truncating division, sign of `%`) is imported by the
  IR interpreter, the constant folder, *and* EvoVM — so "the optimized
  program behaves like the original" is a checkable property, not an
  assumption written three different ways in three different places.
- **The optimizer's unsound passes really are unsound, and are really
  caught.** `spec_div_to_shift` assumes `x / 2^k == x >> k`, which is false
  for negative `x` under truncating division. Given `x = -9`, `x / 4` is
  `-2` but `x >> 2` is `-3`. The Digital Twin's function-level differential
  test catches this on a boundary-swept negative input and rejects the
  candidate — verified in
  `tests/test_digital_twin.py::test_unsound_div_to_shift_rejected_on_negative_input`.
- **Correctness is a hard gate on fitness, not a tiebreaker.** In a program
  where every "improving" transformation is unsound (dropping a call whose
  only purpose is its `print` side effect), best fitness stays exactly
  `0.0` across the whole search —
  `tests/test_evolution.py::test_correctness_dominates_fitness_when_all_improvements_unsound`.
- **The search is reproducible.** Two `EvolutionEngine` runs with the same
  seed on the same program produce byte-identical candidate sequences
  (`tests/test_evolution.py::test_deterministic_given_same_seed`).
- **Final validation actually re-executes both programs.** It isn't a
  metadata comparison — it runs the original IR on the reference
  interpreter, the original bytecode on EvoVM, and the optimized bytecode on
  EvoVM, and cross-checks all three
  (`pipeline/pipeline.py::stage_validation`).

## Tech Stack

**Backend:** Python 3.12, FastAPI, Pydantic, pytest.
**Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4, Monaco Editor.

No compiler-construction libraries (no PLY, no Lark, no LLVM bindings) are
used anywhere in the pipeline — the lexer, parser, semantic analyzer, IR,
CFG builder, optimizer, Digital Twin, code generator, and virtual machine are
all hand-written.

## EvoLang Language Reference

EvoLang is a small, C-like, statically-typed imperative language. Full
grammar: [`docs/GRAMMAR.md`](docs/GRAMMAR.md). Diagnostic codes:
[`docs/DIAGNOSTICS.md`](docs/DIAGNOSTICS.md).

```c
function add(int a, int b) {
    return a + b;
}

int main() {
    int total = 0;
    for (int i = 0; i < 10; i++) {
        total = total + add(i, 8);
    }
    print(total);
}
```

Types: `int` (32-bit, wraps on overflow), `float`, `string`, `bool`.
Control flow: `if`/`else`, `while`, `for`. Functions may be declared with an
explicit return type (`int f(...)`) or with `function f(...)`, in which case
the return type is inferred from the function's own `return` statements
(self-recursive `function`s must use the explicit form — see diagnostic
E015). Arrays, structs, pointers, and bitwise operators are not part of the
language (see [`docs/GRAMMAR.md`](docs/GRAMMAR.md) for the full list of
what's deliberately excluded, and why the parser gives a specific message
for a few of them).

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL. The dev server proxies `/api/*` to
`localhost:8000` (see `frontend/vite.config.ts`).

## API Reference

All endpoints are under `/api`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/lex` | Phase 1 standalone lexer (stateless; unchanged from Phase 1) |
| `GET` | `/stages` | Stage metadata: order, dependencies, labels, descriptions |
| `POST` | `/session` | Create a compilation session: `{source, options?}` -> `{sessionId, ...}` |
| `GET` | `/session/{id}` | Session summary (stage statuses, no bulk data) |
| `DELETE` | `/session/{id}` | Discard a session |
| `POST` | `/session/{id}/run/{stage}` | Run one stage (`409` if its dependency hasn't completed) |
| `GET` | `/session/{id}/stage/{stage}` | Get one stage's last result |
| `POST` | `/session/{id}/run-all` | Run every stage from the start, stopping at the first failure |
| `GET` | `/session/{id}/report` | The final compilation report (available once Validation has run) |
| `POST` | `/compile` | One-shot: create a session, run all 13 stages, return everything |

`options` (all optional, with bounds enforced server-side):
`seed` (int), `population` (1-64), `generations` (1-60),
`step_limit` (1,000-5,000,000).

A stage's failure is distinguished from a compiler bug: a real syntax/type/
equivalence failure comes back as `status: "failed"` with a specific
`error` message and whatever partial data the stage produced; an unexpected
exception is reported as `"Internal compiler error in <Stage>: ..."` so the
two are never confused in the UI.

## Testing

```bash
cd backend
pytest tests -q
```

**108 tests, organized by stage** (`backend/tests/`):
`test_lexer.py` (Phase 1, 18 tests), `test_parser.py`, `test_ast.py`,
`test_semantic.py`, `test_ir.py`, `test_cfg.py`, `test_dna.py`,
`test_evolution.py`, `test_digital_twin.py`, `test_codegen.py` (covers
codegen + EvoVM + the static verifier), `test_pipeline_e2e.py` (all 13
stages on the 4 required test programs — arithmetic, conditions, loops,
functions — plus one function+loop combination), `test_api.py` /
`test_pipeline_api.py` (HTTP layer via FastAPI's `TestClient`).

Every diagnostic code, every optimization pass (sound and speculative), and
every documented "not a mockup" claim above has a corresponding test that
would fail if the claim stopped being true.

## Project Structure

```
backend/
  lexer/                  Phase 1 lexer (unchanged)
  compiler/
    ast/                   node types (nodes.py) + finalization (builder.py)
    parser/                recursive-descent parser
    semantic/               scope/type analyzer
    ir/                     IR model, generator, reference interpreter
    cfg/                    basic-block + dominator + loop construction
    dna/                    Program DNA extractor
    evolution/              optimization passes, fitness, genetic engine
    digital_twin/           behavioral validation
    codegen/                IR -> EvoVM bytecode
    evm/                    EvoVM interpreter + static verifier
    runtime.py              shared 32-bit/truncating-division semantics
  pipeline/
    session.py              CompilationSession, stage metadata & dependencies
    pipeline.py              the 13 real stage-runner functions
    report.py                final report assembly (reads only real stage data)
    store.py                 in-memory session store for the dev API
  api/
    routes.py                Phase 1 /api/lex (unchanged)
    pipeline_routes.py        Phase 2+ session/compile routes
  tests/                    108 tests, one file per stage (+ API, + e2e)
frontend/
  src/
    components/compiler/     Phase 1 lexer lab UI (unchanged) + shared sidebar
    components/pipeline/      Phase 2+ per-stage views (Parser, AST, Semantic,
                              IR, CFG, DNA, Evolution, Digital Twin, Codegen,
                              EvoVM, Execution, Validation) + shared primitives
    hooks/useCompilation.ts   Phase 1 lexer-lab state (unchanged)
    hooks/usePipeline.ts       Phase 2+ session/stage state
    services/compilerApi.ts   Phase 1 API client (unchanged)
    services/pipelineApi.ts   Phase 2+ API client
    types/pipeline.ts         Phase 2+ TypeScript types
docs/
  GRAMMAR.md                 EvoLang EBNF grammar (exactly what the parser implements)
  DIAGNOSTICS.md              semantic diagnostic code reference
```

## Worked Example

Compiling:

```c
function add(int a, int b) { return a + b; }
int main() {
    int t = 0;
    for (int i = 0; i < 10; i++) {
        t = t + add(i, 2 * 4);
    }
    print(t);
}
```

with the default options (`seed=42, population=16, generations=14`) produces,
among the certified candidates, a genome including `strength_reduction`
(rewriting power-of-two multiplications into shifts), `constant_folding`,
`constant_propagation`, `temp_forwarding`, and `dead_code_elimination` — and
also proposes, and then **rejects**, candidates using the two speculative
passes once their unsoundness shows up on a swept input. The certified
result: **16 -> 14 IR instructions (-12.5%)**, **dynamic cost 254 -> 214
(-15.75%)**, output unchanged (`125`), and Validation reports
**EQUIVALENT** across all three cross-checked executions (reference
interpreter, original bytecode on EvoVM, optimized bytecode on EvoVM).

## Design Principles

- **Lexer isolation.** Later stages are added as siblings to the Phase 1
  lexer, never patches to it — `lexer/` is untouched since Phase 1.
- **One source of truth per stage.** Each stage's result is a single typed
  object (`ParseResult`, `ASTResult`, `SemanticResult`, `IRProgram`, ...)
  that both the API and the tests consume identically.
- **Honest UI.** A stage that hasn't run says "not started," not a
  plausible-looking placeholder. A stage that fails shows the specific,
  real error, distinguished from an unexpected internal exception.
- **Correctness before speed.** The fitness function has 70% weight on
  measured dynamic cost and 30% on static size, but neither matters at all
  for a candidate the Digital Twin rejects — rejected candidates have no
  fitness and can never be selected, elite, or the final result.
- **Traceability.** Every IR instruction records the AST node it came from;
  every optimized instruction records the original (pre-optimization)
  instruction id(s) it descends from; every bytecode instruction records
  the IR instruction it was lowered from.

## Known Limitations

- Sessions are held in server process memory (`pipeline/store.py`), capped
  at 50 concurrent sessions with oldest-first eviction — restarting the
  backend clears all sessions. This is a development-server design choice,
  not a stage-correctness limitation.
- The wall-clock benchmark in the Validation stage is measured over 30 runs
  with 3 warmup runs, but on very small programs is still dominated by
  measurement noise; the pipeline detects and flags this (`noisy: true`)
  rather than reporting a misleadingly precise speedup number. Executed
  instruction counts (exact and deterministic) are the more reliable metric
  and are reported alongside the timing.
- The evolutionary search explores pass *orderings and repetitions*, not
  arbitrary program rewrites — it cannot discover an optimization outside
  the 10 implemented passes.
- EvoLang intentionally excludes arrays, structs, and pointers (see
  `docs/GRAMMAR.md`); this is a language-design boundary, not an
  unimplemented feature.

## Roadmap

Phase 2+ (this repository) completes the full 13-stage pipeline described in
the original design. Possible future directions: persistent session storage,
arrays/structs in EvoLang (would require corresponding IR/CFG/DNA/Digital
Twin extensions throughout), additional optimization passes, and a
side-by-side "before/after" diff view for the optimizer's transformation
history in the UI.
