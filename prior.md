# Prior Art + Routing/Ensemble Viability

---

## 1. Similar benchmarks in the wild

| Benchmark | Year | What it measures | Direct analog? |
|---|---|---|---|
| **Letta Context-Bench** | 2025-11 | Full-context vs static RAG vs dynamic memory vs agentic retrieval on QA over long docs/conversations | **Closest analog.** Same axes (quality × cost × strategy). Different domain (generic, not HR). |
| HELMET (Princeton) | 2024 | Holistic long-context eval across 7 task types; does long context work at all | Adjacent — tests capability, not curation strategy |
| LoCoMo | 2024 | Long conversational memory with retrieval-over-time | Adjacent — memory focus, not strategy comparison |
| LongMemEval | 2024 | Memory evaluation for long conversations | Adjacent |
| NoLiMa / RULER | 2024 | Needle-in-haystack, multi-needle variants | Tests position/recall, not curation |
| **Lost in the Middle** (Liu et al.) | 2023 | Position bias in long context — curation *matters* | Seminal paper, not a benchmark |
| MemGPT paper (Packer et al.) | 2023 | Memory hierarchy beats full-stuff on long conversations | Origin of Letta's pitch |

**Category ownership:** Letta has the mic on "context engineering benchmark" as of late 2025. Any public positioning needs to differentiate from them or collaborate.

---

## 2. How Stage 3 differs from Letta Context-Bench

| axis | Letta Context-Bench | This work |
|---|---|---|
| domain | generic doc/conversation QA | HR onboarding (GitLab Handbook + Slack) |
| **staleness / contradiction structure** | not emphasized | explicit — 40% of v2 questions are `slack_contradicts` with a stale handbook value and a recent HR-validated Slack value |
| strategies | full, RAG, dynamic memory, agentic | full, RAG, hierarchical (map-route-expand), agent-managed (tool-use), **+ meta-harness proposer** |
| meta-harness proposer axis | — | unique — LLM mutates a typed `CurationSpec` over failure traces |
| scale | hundreds of queries | **N=10** (toy; see eval/eval_runs.md benchmark-readiness section) |

**Defensible deltas:** (1) staleness/contradiction as first-class structure, (2) meta-harness proposer as a strategy axis, (3) HR-specific domain. **Indefensible as-is:** N=10, single model, synthetic Slack, no held-out split.

---

## 3. Is routing or ensembling viable?

**Short answer:** yes — oracle routing on Stage 3 data buys **100% quality at 21% the cost of full_context** (best single strategy) and 43% the cost of agent_managed. Realistic routing captures some fraction of that gap. Ensembling is cheaper to implement but more expensive to run.

### 3.1 Oracle router (upper bound from Stage 3 data)

Per-question: pick the cheapest strategy that ties for max quality. Computed from `output/results_stage3.csv`:

| approach | quality_mean | cost_total (N=10) | avg prompt_tok | avg latency_s |
|---|---|---|---|---|
| full_context (best single) | 1.000 | $0.667 | 19,957 | 6.20 |
| agent_managed | 0.995 | $0.318 | 7,738 | 9.66 |
| hierarchical (cheapest) | 0.915 | $0.116 | 1,489 | 6.05 |
| **oracle router** | **1.000** | **$0.138** | **2,175** | **6.53** |

Oracle picked hierarchical 8/10 times, `rag_embedding` once (q-v2-006), `agent_managed` once (q-v2-010). Specifically the two oracle upgrades from hier:
- q-v2-006 `slack_only`: hier 0.95 → rag 1.00 at +$0.004
- q-v2-010 `portal_only` military leave: hier 0.20 → agent 1.00 at +$0.021

### 3.2 Category-label router (degenerate on this N)

Routing by question `category` label (assuming you had one at serve time, which you don't) picks full_context for every category on this data because full_context is always max-quality. Collapses to the full_context row. Category is the wrong feature at this scale.

### 3.3 Practical routers worth prototyping

Ranked by implementation effort:

1. **Cheap-first cascade** (lowest effort, likely wins on this eval)
   - Always try hierarchical first ($0.012/q, ~91.5% quality)
   - If confidence signal fires — e.g. the router returned <2 doc_ids, or the answer doesn't cite a source, or an LLM-judge verifier gives <0.8 — escalate to agent_managed ($0.032/q)
   - If still weak → full_context ($0.067/q)
   - **Estimated:** ~0.98 quality at ~$0.20 total on Stage 3 (within 80% of oracle)

2. **LLM router** (medium effort)
   - Small Haiku call: `route(question, corpus_schema) -> strategy_id`
   - Training signal: historical per-question winners (need ≥100 labeled Qs first — a dependency on benchmark-scale work)
   - Adds ~$0.001 per question for the router call

3. **Confidence-calibrated ensemble** (higher effort, likely overkill)
   - Run 2 cheapest strategies in parallel, if they agree → return; if disagree → run expensive tiebreaker + judge
   - Bounded cost: disagreement rate × expensive-strategy cost + 2× cheap
   - Needs an agreement metric (embedding similarity or LLM-judge "equivalent?")

4. **Self-consistency / best-of-N** (budget blow-up risk)
   - Run one strategy N times at T>0, vote — not obviously better for non-reasoning QA tasks

### 3.4 Ensemble viability

Full ensembles (all 5 strategies → vote) cost **$1.68/10q = $0.168/q** for an expected ceiling of ~1.00 quality — worse economics than oracle routing because you always pay every strategy. Only justified if run-to-run variance is high enough that voting buys statistical robustness (not measured yet; needs the 3-seed multi-run from benchmark-readiness).

**Partial ensemble** (hier + agent_managed + LLM-judge picks better): $0.012 + $0.032 + ~$0.003 judge = $0.047/q = $0.47/10q — *worse* than full_context on cost, *similar* on quality. Not obviously better unless we credit variance reduction.

### 3.5 What a router demo would need

- ≥50 labeled questions with per-strategy quality scores (for training a real router)
- A confidence signal on each strategy (self-reported or verifier-based)
- An escalation threshold chosen on a dev split, not the eval set
- A cost ceiling argument (`--max-cost-usd`) so a misfiring router can't cascade to full_context for every question

### 3.6 Honest caveats

- All numbers above come from N=10 with no variance estimate — oracle/router quality of 1.000 reflects that ceiling is already saturated on this eval, not that routing is magical.
- At larger N with harder questions, the gap between hierarchical and agent_managed will widen; cascade cost will rise accordingly.
- Routing only matters if the failure modes are **recoverable** — i.e. some other strategy gets the right answer. On Stage 3 every failed cell had at least one 1.00 peer, so recoverable. Real-world evals may have questions that *no* strategy handles, which routing can't fix.

### 3.7 Recommended next experiment (post-scaling)

Once N ≥ 100 with 3-seed runs exists:
1. Implement the cheap-first cascade (router #1) as `src/strategies_router.py`
2. Run on the same eval as Stage 3 equivalent-at-scale
3. Report: quality_mean, cost_total, **AUC-like frontier** of (budget cap) → (quality achievable under that cap)
4. Compare to single-strategy baselines and to Letta Context-Bench's agentic retrieval (if public)
