"""Evolutionary search over optimisation-pass sequences.

Representation
    A candidate's *genome* is an ordered list of pass names. Its phenotype is
    the IR obtained by really applying those passes to a copy of the original
    IR, so every candidate corresponds to an actual transformed program.

Operators
    tournament selection, single-point crossover, mutation (insert / delete /
    replace / swap / duplicate), elitism, early stopping on stagnation.

Guidance
    Program DNA guides the search: pass proposal probabilities are weighted by
    how many sites each pass would actually change in this program.

Evaluation
    Every candidate is executed by the Digital Twin. Rejected candidates get
    no fitness (hard constraint).
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from compiler.digital_twin.twin import DigitalTwin
from compiler.ir.instructions import IRProgram
from .fitness import compute_fitness, describe
from .passes import PASSES, SOUND_PASSES, SPECULATIVE_PASSES, STANDARD_PIPELINE, apply_genome, count_opportunities


@dataclass
class EvolutionConfig:
    seed: int = 42
    population: int = 16
    generations: int = 14
    elite: int = 2
    tournament: int = 3
    crossover_rate: float = 0.6
    mutation_rate: float = 0.5
    max_genome: int = 18
    patience: int = 6
    correctness_gate: bool = True
    """When True (default/production behaviour) the Digital Twin's verdict is a
    hard constraint: a behaviourally-incorrect candidate can never be selected,
    whatever its fitness. When False, selection ranks every candidate purely by
    fitness and ignores the Digital Twin's verdict - this exists only so the
    engine can honestly measure what the Digital Twin is *for*, by running the
    identical search twice (same seed, same pass set) with the gate on and off
    and comparing the two real outcomes. It is never used for the default
    compile path."""

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class Candidate:
    id: str
    generation: int
    genome: List[str]
    parent_ids: List[str]
    origin: str
    ir_hash: str = ""
    size: int = 0
    dyn_cost: int = 0
    executed: int = 0
    status: str = "PENDING"       # VALID | REJECTED
    fitness: Optional[float] = None
    shadow_fitness: Optional[float] = None  # fitness computed regardless of correctness (see EvolutionConfig.correctness_gate)
    speculative: bool = False

    def sort_key(self, correctness_gate: bool = True):
        if correctness_gate:
            return (0 if self.status == "VALID" else 1, -(self.fitness if self.fitness is not None else -9e9),
                    self.size, len(self.genome), int(self.id[1:]))
        # ungated: rank by fitness alone, correctness is not consulted at all
        return (-(self.shadow_fitness if self.shadow_fitness is not None else -9e9),
                self.size, len(self.genome), int(self.id[1:]))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "generation": self.generation, "parentIds": self.parent_ids,
            "parent": self.parent_ids[0] if self.parent_ids else None, "origin": self.origin,
            "genome": self.genome, "genomeKey": ",".join(self.genome), "irHash": self.ir_hash,
            "staticSize": self.size, "dynamicCost": self.dyn_cost, "executed": self.executed,
            "fitness": self.fitness, "shadowFitness": self.shadow_fitness, "status": self.status,
            "correctness": "VALIDATED" if self.status == "VALID" else "REJECTED",
            "usesSpeculativePass": self.speculative,
        }


def dna_pass_weights(opportunities: Dict[str, int]) -> Dict[str, float]:
    w: Dict[str, float] = {}
    for name, info in PASSES.items():
        opp = opportunities.get(name, 0)
        if info.sound:
            w[name] = 1.0 + 0.5 * min(opp, 6)
        else:
            w[name] = 1.0 if opp > 0 else 0.4
    return w


class EvolutionEngine:
    def __init__(self, original: IRProgram, twin: DigitalTwin, config: EvolutionConfig,
                 opportunities: Optional[Dict[str, int]] = None):
        self.original = original
        self.twin = twin
        self.cfg = config
        self.rng = random.Random(config.seed)
        self.opportunities = opportunities if opportunities is not None else count_opportunities(original)
        self.weights = dna_pass_weights(self.opportunities)
        self.names = list(PASSES.keys())
        self.next_id = 0
        self.size0 = original.instr_count()
        self.dyn0 = twin.reference.cost
        self.by_genome: Dict[str, dict] = {}
        self.by_ir: Dict[str, dict] = {}
        self.ir_pool: Dict[str, dict] = {}
        self.twin_pool: Dict[str, dict] = {}
        self.history_pool: Dict[str, List[dict]] = {}
        self.cache_hits = 0
        self.evaluations = 0

    # ---- evaluation -----------------------------------------------------
    def _evaluate(self, genome: List[str]) -> dict:
        gkey = ",".join(genome)
        if gkey in self.by_genome:
            self.cache_hits += 1
            return self.by_genome[gkey]
        ir, history = apply_genome(self.original, genome)
        text = ir.text()
        h = hashlib.sha256(text.encode()).hexdigest()[:12]
        self.history_pool[gkey] = history
        if h in self.by_ir:
            self.cache_hits += 1
            res = self.by_ir[h]
        else:
            report = self.twin.validate(ir, "quick")
            self.evaluations += 1
            size = ir.instr_count()
            valid = report.valid
            # computed unconditionally - the Digital Twin's verdict (`valid`) and the
            # fitness formula are independent measurements, so both are always real
            shadow_fit = compute_fitness(report.candidate.cost, size, self.dyn0, self.size0)
            fit = shadow_fit if valid else None
            res = {"hash": h, "valid": valid, "size": size, "dyn": report.candidate.cost,
                   "executed": report.candidate.executed, "fitness": fit, "shadowFitness": shadow_fit}
            self.by_ir[h] = res
            self.ir_pool[h] = ir.compact()
            self.twin_pool[h] = report.to_dict()
        out = dict(res)
        out["speculative"] = any(not s["sound"] and s["changed"] for s in history)
        self.by_genome[gkey] = out
        return out

    def _make(self, generation: int, genome: List[str], parents: List[str], origin: str) -> Candidate:
        c = Candidate(f"C{self.next_id}", generation, list(genome), parents, origin)
        self.next_id += 1
        r = self._evaluate(c.genome)
        c.ir_hash, c.size, c.dyn_cost, c.executed = r["hash"], r["size"], r["dyn"], r["executed"]
        c.status = "VALID" if r["valid"] else "REJECTED"
        c.fitness = r["fitness"]
        c.shadow_fitness = r["shadowFitness"]
        c.speculative = r["speculative"]
        return c

    # ---- operators ------------------------------------------------------
    def _pick_pass(self) -> str:
        return self.rng.choices(self.names, weights=[self.weights[n] for n in self.names])[0]

    def _random_genome(self) -> List[str]:
        n = self.rng.randint(1, self.cfg.max_genome)
        return [self._pick_pass() for _ in range(n)]

    def _select(self, pool: List[Candidate]) -> Candidate:
        gate = self.cfg.correctness_gate
        valid = pool if not gate else ([c for c in pool if c.status == "VALID"] or pool)
        k = min(self.cfg.tournament, len(valid))
        contenders = self.rng.sample(valid, k)
        return min(contenders, key=lambda c: c.sort_key(gate))

    def _effective_fitness(self, c: Candidate) -> Optional[float]:
        """The fitness value this run's selection actually uses for `c` - gated
        runs only trust fitness once the Digital Twin has certified the
        candidate; an ungated run uses the same formula's output regardless of
        correctness, which is the entire point of running it (see
        EvolutionConfig.correctness_gate)."""
        return c.fitness if self.cfg.correctness_gate else c.shadow_fitness

    def _is_eligible_best(self, c: Candidate) -> bool:
        return (c.status == "VALID") if self.cfg.correctness_gate else (c.shadow_fitness is not None)

    def _crossover(self, a: List[str], b: List[str]) -> List[str]:
        ca = self.rng.randint(0, len(a)) if a else 0
        cb = self.rng.randint(0, len(b)) if b else 0
        return (a[:ca] + b[cb:])[: self.cfg.max_genome]

    def _mutate(self, g: List[str]) -> List[str]:
        g = list(g)
        op = self.rng.choice(["insert", "delete", "replace", "swap", "duplicate"])
        if op == "insert" or not g:
            g.insert(self.rng.randint(0, len(g)), self._pick_pass())
        elif op == "delete":
            g.pop(self.rng.randrange(len(g)))
        elif op == "replace":
            g[self.rng.randrange(len(g))] = self._pick_pass()
        elif op == "swap" and len(g) > 1:
            i, j = self.rng.sample(range(len(g)), 2)
            g[i], g[j] = g[j], g[i]
        elif op == "duplicate":
            g.insert(self.rng.randint(0, len(g)), g[self.rng.randrange(len(g))])
        return g[: self.cfg.max_genome]

    # ---- main loop --------------------------------------------------------
    def run(self) -> dict:
        t0 = time.perf_counter()
        cfg = self.cfg
        generations: List[List[Candidate]] = []
        stats: List[dict] = []
        all_cands: List[Candidate] = []

        pop: List[Candidate] = [self._make(0, [], [], "original (identity genome)")]
        while len(pop) < cfg.population:
            pop.append(self._make(0, self._random_genome(), [], "random"))
        best_seen = -1e9
        stagnant = 0
        termination = f"generation limit ({cfg.generations})"
        for g in range(cfg.generations):
            generations.append(pop)
            all_cands.extend(pop)
            valid = [c for c in pop if c.status == "VALID"]
            eligible = [c for c in pop if self._is_eligible_best(c)]
            best = min(pop, key=lambda c: c.sort_key(cfg.correctness_gate))
            fits = [self._effective_fitness(c) for c in eligible if self._effective_fitness(c) is not None]
            stats.append({
                "generation": g, "populationSize": len(pop), "validCandidates": len(valid),
                "invalidCandidates": len(pop) - len(valid),
                "bestFitness": self._effective_fitness(best) if self._is_eligible_best(best) else None,
                "averageFitness": round(sum(fits) / len(fits), 6) if fits else None,
                "bestCandidateId": best.id if self._is_eligible_best(best) else None,
                "uniquePrograms": len({c.ir_hash for c in pop}),
                "meanGenomeLength": round(sum(len(c.genome) for c in pop) / len(pop), 3),
                "candidateIds": [c.id for c in pop],
            })
            top = stats[-1]["bestFitness"]
            if top is not None and top > best_seen + 1e-12:
                best_seen, stagnant = top, 0
            else:
                stagnant += 1
            if g == cfg.generations - 1:
                break
            if stagnant >= cfg.patience:
                termination = f"converged: no improvement for {cfg.patience} generations (stopped after generation {g})"
                break
            ranked = sorted(pop, key=lambda c: c.sort_key(cfg.correctness_gate))
            nxt: List[Candidate] = []
            for e in ranked[: cfg.elite]:
                if self._is_eligible_best(e):
                    nxt.append(self._make(g + 1, e.genome, [e.id], "elite"))
            while len(nxt) < cfg.population:
                p1 = self._select(pop)
                origin = "mutation"
                parents = [p1.id]
                genome = list(p1.genome)
                if self.rng.random() < cfg.crossover_rate:
                    p2 = self._select(pop)
                    genome = self._crossover(p1.genome, p2.genome)
                    parents = [p1.id, p2.id]
                    origin = "crossover"
                if self.rng.random() < cfg.mutation_rate or genome == p1.genome:
                    genome = self._mutate(genome)
                    origin = origin + "+mutation" if origin == "crossover" else "mutation"
                nxt.append(self._make(g + 1, genome, parents, origin))
            pop = nxt

        # hall of fame: best eligible candidate per distinct program (gated runs
        # require Digital Twin certification to be eligible; an ungated run
        # accepts any candidate the formula ranks well, correctness aside)
        seen_hash = set()
        hof: List[Candidate] = []
        for c in sorted(all_cands, key=lambda c: c.sort_key(cfg.correctness_gate)):
            if self._is_eligible_best(c) and c.ir_hash not in seen_hash:
                seen_hash.add(c.ir_hash)
                hof.append(c)
            if len(hof) >= 10:
                break
        best = hof[0] if hof else None
        baseline = self._evaluate(list(STANDARD_PIPELINE))
        elapsed = (time.perf_counter() - t0) * 1000
        rejected = [c for c in all_cands if c.status == "REJECTED"]
        return {
            "seed": cfg.seed, "config": cfg.to_dict(),
            "reproducibility": ("All randomness comes from a single Python random.Random(seed); "
                                "selection uses no timing data, so the same seed on the same source "
                                "reproduces the same generations."),
            "original": {"staticSize": self.size0, "dynamicCost": self.dyn0, "executed": self.twin.reference.executed},
            "fitnessFunction": describe(),
            "dnaGuidance": {
                "opportunities": self.opportunities, "weights": self.weights,
                "passes": [{"name": n, "label": PASSES[n].label, "sound": PASSES[n].sound,
                            "description": PASSES[n].description, "opportunities": self.opportunities.get(n, 0),
                            "weight": self.weights[n]} for n in self.names],
            },
            "generations": stats,
            "candidates": [c.to_dict() for c in all_cands],
            "irPool": self.ir_pool, "twinPool": self.twin_pool, "historyPool": self.history_pool,
            "hallOfFame": [c.id for c in hof],
            "bestCandidateId": best.id if best else None,
            "baselinePipeline": {"genome": list(STANDARD_PIPELINE), **{k: baseline[k] for k in
                                 ("hash", "size", "dyn", "fitness", "valid")}},
            "termination": termination,
            "statistics": {
                "generationsRun": len(stats), "populationSize": cfg.population,
                "totalCandidates": len(all_cands), "programsValidated": self.evaluations,
                "cacheHits": self.cache_hits,
                "validCandidates": len(all_cands) - len(rejected), "rejectedCandidates": len(rejected),
                "speculativeCandidates": sum(1 for c in all_cands if c.speculative),
                "bestFitness": self._effective_fitness(best) if best else None,
                "bestActuallyCorrect": (best.status == "VALID") if best else None,
            },
            "elapsedMs": round(elapsed, 3),
        }
