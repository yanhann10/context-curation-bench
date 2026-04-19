"""Parse a suite YAML into typed dataclasses.

Novelty vs letta-evals:
  - `strategies:` is a list (matrix eval).
  - `corpus:` is a first-class field separate from `dataset:`.
  - `frontier:` replaces `gate:` with Pareto-frontier reporting.
  - `optimize:` is a built-in phase.

YAML shape:

    name: sample-data-hr-policy
    corpus:
      loader: jsonl
      path: data/corpus.jsonl
    dataset:
      path: data/questions.jsonl
    strategies:
      - name: full_context
      - name: rag_embedding
        params: {k: 6}
      - name: meta_harness
        params: {train_size: 4, iterations: 3}
    grader:
      kind: llm_judge
      model: claude-opus-4-7
    frontier:
      axes: [quality, cost_usd, tokens]
      direction: [max, min, min]
    optimize:
      strategy: meta_harness
      train_size: 4
      iterations: 3
    models:
      agent: claude-sonnet-4-6
      judge: claude-opus-4-7
      proposer: claude-opus-4-7
    concurrency: 8
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CorpusCfg:
    loader: str = "jsonl"
    path: str = "data/corpus.jsonl"


@dataclass
class DatasetCfg:
    path: str = "data/questions.jsonl"


@dataclass
class StrategyCfg:
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class GraderCfg:
    kind: str = "llm_judge"
    model: str = "claude-opus-4-7"


@dataclass
class FrontierCfg:
    axes: list[str] = field(default_factory=lambda: ["quality", "cost_usd", "total_tokens"])
    direction: list[str] = field(default_factory=lambda: ["max", "min", "min"])


@dataclass
class OptimizeCfg:
    strategy: str | None = None
    train_size: int = 4
    dev_size: int = 3
    iterations: int = 3


@dataclass
class ModelsCfg:
    agent: str = "claude-sonnet-4-6"
    judge: str = "claude-opus-4-7"
    proposer: str = "claude-opus-4-7"


@dataclass
class SuiteSpec:
    name: str
    corpus: CorpusCfg
    dataset: DatasetCfg
    strategies: list[StrategyCfg]
    grader: GraderCfg
    frontier: FrontierCfg
    models: ModelsCfg
    optimize: OptimizeCfg | None = None
    concurrency: int = 8
    raw: dict = field(default_factory=dict)


def load_suite(path: str | Path) -> SuiteSpec:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return SuiteSpec(
        name=data.get("name", Path(path).stem),
        corpus=CorpusCfg(**(data.get("corpus") or {})),
        dataset=DatasetCfg(**(data.get("dataset") or {})),
        strategies=[StrategyCfg(**s) for s in (data.get("strategies") or [])],
        grader=GraderCfg(**(data.get("grader") or {})),
        frontier=FrontierCfg(**(data.get("frontier") or {})),
        optimize=OptimizeCfg(**data["optimize"]) if data.get("optimize") else None,
        models=ModelsCfg(**(data.get("models") or {})),
        concurrency=int(data.get("concurrency", 8)),
        raw=data,
    )


def validate(spec: SuiteSpec) -> list[str]:
    from .registry import STRATEGIES, CORPUS_LOADERS
    errs: list[str] = []
    if not spec.strategies:
        errs.append("suite has no strategies")
    for s in spec.strategies:
        if s.name not in STRATEGIES:
            errs.append(f"unknown strategy '{s.name}' — registered: {sorted(STRATEGIES)}")
    if spec.corpus.loader not in CORPUS_LOADERS:
        errs.append(f"unknown corpus loader '{spec.corpus.loader}'")
    if not Path(spec.corpus.path).exists():
        errs.append(f"corpus path missing: {spec.corpus.path}")
    if not Path(spec.dataset.path).exists():
        errs.append(f"dataset path missing: {spec.dataset.path}")
    if spec.optimize and spec.optimize.strategy not in STRATEGIES:
        errs.append(f"optimize.strategy '{spec.optimize.strategy}' not registered")
    # Warnings (non-blocking, printed to stderr)
    import sys
    if spec.models.agent == spec.models.judge:
        print(f"⚠️  models.agent == models.judge ({spec.models.agent}). "
              "Self-preference bias likely — use a different judge model.",
              file=sys.stderr)
    if spec.optimize:
        total = spec.optimize.train_size + spec.optimize.dev_size
        if spec.optimize.dev_size == 0:
            print("⚠️  optimize.dev_size=0 — no held-out dev split. "
                  "Optimizer may overfit to the train set.", file=sys.stderr)
    return errs
