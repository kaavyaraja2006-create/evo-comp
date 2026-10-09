"""One real compilation session: every stage result lives here."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STAGES = ["lexer", "parser", "ast", "semantic", "ir", "cfg", "dna", "evolution",
          "twin", "codegen", "evovm", "execution", "validation"]

DEPENDS: Dict[str, Optional[str]] = {
    "lexer": None, "parser": "lexer", "ast": "parser", "semantic": "ast", "ir": "semantic",
    "cfg": "ir", "dna": "cfg", "evolution": "dna", "twin": "evolution", "codegen": "twin",
    "evovm": "codegen", "execution": "evovm", "validation": "execution",
}

STAGE_META: Dict[str, dict] = {
    "lexer": {"label": "Lexer", "button": "LEX", "loading": ["Initializing lexer...", "Scanning source..."],
              "input": "Source text", "transformation": "Hand-written character-by-character scanner (maximal munch)",
              "output": "Token stream",
              "explanation": "The lexer groups characters into tokens (keywords, identifiers, literals, operators, "
                             "delimiters, comments) and records each token's exact position."},
    "parser": {"label": "Parser", "button": "PARSE", "loading": ["Initializing parser...", "Parsing token stream..."],
               "input": "Token stream (comments filtered)", "transformation": "Recursive-descent parser, one method per grammar production",
               "output": "Typed syntax tree + parse trace",
               "explanation": "The parser checks that the tokens form a sentence of the EvoLang grammar and builds "
                              "typed syntax-tree nodes while doing so. Errors are reported with the exact token that broke the grammar."},
    "ast": {"label": "AST", "button": "BUILD AST", "loading": ["Building AST...", "Assigning node ids and checking invariants..."],
            "input": "Parser output (typed tree)", "transformation": "AST finalisation: ids, parents, depth, invariant checks",
            "output": "Abstract syntax tree",
            "explanation": "The AST is the tree of program structure with grammar noise (parentheses, semicolons) removed. "
                           "Each node keeps its source location so later stages can point back at the source."},
    "semantic": {"label": "Semantic Analysis", "button": "ANALYZE", "loading": ["Analyzing symbols...", "Type checking..."],
                 "input": "AST", "transformation": "Scope resolution and type checking",
                 "output": "Symbol table + diagnostics + per-expression types",
                 "explanation": "Syntax alone cannot tell whether a program makes sense. This stage resolves every name "
                                "to a declaration, checks types, operators, calls and returns, and reports errors and warnings."},
    "ir": {"label": "IR", "button": "GENERATE IR", "loading": ["Generating IR..."],
           "input": "Semantically valid AST + types", "transformation": "Three-address-code generation with short-circuit control flow",
           "output": "Three-address IR",
           "explanation": "The IR is a simple, machine-independent instruction list (one operation per instruction). "
                          "It is the representation the optimiser rewrites and the code generator lowers."},
    "cfg": {"label": "CFG", "button": "BUILD CFG", "loading": ["Building CFG..."],
            "input": "IR", "transformation": "Leader identification, basic blocks, dominators, natural loops",
            "output": "Basic blocks and control-flow graph",
            "explanation": "The CFG groups straight-line instructions into basic blocks and connects them by possible "
                           "jumps. Loops are found as back edges to dominating blocks."},
    "dna": {"label": "Program DNA", "button": "EXTRACT DNA", "loading": ["Extracting Program DNA..."],
            "input": "AST + IR + CFG", "transformation": "Deterministic structural feature extraction and optimisation-opportunity detection",
            "output": "Program DNA",
            "explanation": "Program DNA is an explainable structural fingerprint of the program. Its optimisation-opportunity "
                           "counts are measured by dry-running each pass, and they weight the evolutionary search."},
    "evolution": {"label": "Evolution", "button": "EVOLVE", "loading": ["Generating optimization candidates...", "Evaluating candidates with the Digital Twin..."],
                  "input": "IR + CFG + Program DNA", "transformation": "Genetic search over optimisation-pass sequences",
                  "output": "Generations of candidates with fitness",
                  "explanation": "Each candidate is an ordered list of optimisation passes. It is turned into a real transformed IR, "
                                 "executed by the Digital Twin, and scored. Selection, crossover and mutation then breed the next generation."},
    "twin": {"label": "Digital Twin", "button": "VALIDATE", "loading": ["Running Digital Twin validation..."],
             "input": "Evolution finalists", "transformation": "Thorough differential execution against the original program",
             "output": "Validation matrix + certified optimised IR",
             "explanation": "The Digital Twin executes the original program and each finalist and compares observable behaviour. "
                            "Only a candidate whose behaviour matches can be selected; the best certified candidate wins."},
    "codegen": {"label": "Target Code", "button": "GENERATE CODE", "loading": ["Generating EvoVM bytecode..."],
                "input": "Certified optimised IR", "transformation": "Three-address code lowered to stack bytecode",
                "output": "EvoVM bytecode",
                "explanation": "Each IR instruction is lowered to a short sequence of stack-machine instructions. The original IR is "
                               "also compiled so the two programs can be compared."},
    "evovm": {"label": "EvoVM", "button": "LOAD EVOVM", "loading": ["Verifying bytecode..."],
              "input": "Bytecode", "transformation": "Static bytecode verification (jump targets, stack depth, call arity)",
              "output": "Verified program image",
              "explanation": "Before running, EvoVM statically verifies the bytecode: jumps stay inside functions, calls match "
                             "signatures, and the stack depth is consistent on every path."},
    "execution": {"label": "Execution", "button": "EXECUTE", "loading": ["Executing program..."],
                  "input": "Verified bytecode", "transformation": "Stack-machine interpretation with instruction tracing",
                  "output": "Program output, return value, trace",
                  "explanation": "EvoVM runs the optimised program. Output, executed-instruction count and wall time are measured, "
                                 "and every executed instruction is traced with the stack contents."},
    "validation": {"label": "Validation", "button": "FINAL VALIDATION", "loading": ["Comparing original and optimized execution..."],
                   "input": "Original and optimised executions", "transformation": "Equivalence check and benchmarking",
                   "output": "Final compilation report",
                   "explanation": "The optimised program's behaviour on EvoVM is compared with the original program's reference "
                                  "behaviour, and measured improvements are reported."},
}


@dataclass
class StageState:
    status: str = "not_started"   # not_started | completed | failed
    data: Optional[dict] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    summary: Optional[str] = None

    def to_dict(self, with_data: bool = False) -> dict:
        d = {"status": self.status, "summary": self.summary, "error": self.error,
             "durationMs": None if self.duration_ms is None else round(self.duration_ms, 3)}
        if with_data:
            d["data"] = self.data
        return d


@dataclass
class CompileOptions:
    seed: int = 42
    population: int = 16
    generations: int = 14
    step_limit: int = 200_000

    def validate(self) -> None:
        if not (1 <= self.population <= 64):
            raise ValueError("population must be between 1 and 64")
        if not (1 <= self.generations <= 60):
            raise ValueError("generations must be between 1 and 60")
        if not (1_000 <= self.step_limit <= 5_000_000):
            raise ValueError("step_limit must be between 1000 and 5000000")

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class StageBlocked(Exception):
    def __init__(self, stage: str, reason: str, blocked_by: Optional[str]):
        super().__init__(reason)
        self.stage, self.reason, self.blocked_by = stage, reason, blocked_by


class CompilationSession:
    def __init__(self, source: str, options: Optional[CompileOptions] = None):
        self.id = uuid.uuid4().hex[:12]
        self.source = source
        self.options = options or CompileOptions()
        self.options.validate()
        self.stages: Dict[str, StageState] = {s: StageState() for s in STAGES}
        self.internal: Dict[str, Any] = {}
        self.created = time.time()

    def reset_from(self, stage: str) -> None:
        idx = STAGES.index(stage)
        for s in STAGES[idx:]:
            self.stages[s] = StageState()
        for k in [k for k, (st, _) in _INTERNAL_OWNERS.items() if STAGES.index(st) >= idx]:
            self.internal.pop(k, None)

    def summary(self) -> dict:
        lines = self.source.count("\n") + 1 if self.source else 0
        return {
            "sessionId": self.id, "source": {"lines": lines, "characters": len(self.source)},
            "options": self.options.to_dict(), "order": STAGES,
            "stages": {s: self.stages[s].to_dict() for s in STAGES},
        }

    def full(self) -> dict:
        d = self.summary()
        d["results"] = {s: self.stages[s].data for s in STAGES if self.stages[s].data is not None}
        return d


# which stage produced which internal object (used by reset_from)
_INTERNAL_OWNERS = {
    "tokens": ("lexer", 0), "parse": ("parser", 0), "ast": ("ast", 0), "sem": ("semantic", 0),
    "ir": ("ir", 0), "cfg": ("cfg", 0), "opportunities": ("dna", 0), "dna": ("dna", 0),
    "twin": ("evolution", 0), "evolution": ("evolution", 0), "selected": ("twin", 0),
    "bc_opt": ("codegen", 0), "bc_orig": ("codegen", 0), "exec": ("execution", 0),
}
