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

### 3.1 Oracle + real routers — actual Stage 3 numbers (updated after building cascade + ensemble)

Per-question oracle: pick the cheapest strategy that ties for max quality. Plus the two real routers we shipped.

| approach | quality_mean | cost_total (N=10) | avg prompt_tok | avg latency_s |
|---|---|---|---|---|
| full_context | 0.995 | $0.670 | 19,957 | 6.6 |
| agent_managed | 0.990 | $0.320 | 7,739 | 8.9 |
| hierarchical (cheapest) | 0.910 | $0.118 | 1,489 | 6.1 |
| **cascade_router** (real) | 0.925 | **$0.904** | 24,522 | 23.5 |
| **ensemble** (real) | **0.995** | $0.428 | 9,817 | 11.3 |
| **oracle router** (upper bound) | **1.000** | **$0.138** | 2,092 | 6.3 |

Oracle picks hierarchical 9/10, agent_managed 1/10 (on q-v2-010 only). Oracle is achievable only if the router perfectly classifies which question falls in the hier-wins-set vs the hier-fails-set.

### 3.1.1 Findings after actually building cascade and ensemble

**Cascade is worse than its own tier-2 strategy** — 0.925 vs agent_managed 0.990, at 3× the cost ($0.90 vs $0.32). Two reasons:
1. **Self-verifier is over-confident on wrong tier-1 outputs.** On q-v2-010 (military leave), hier returned a confidently-wrong answer. The self-verifier said `confident: 1`, cascade returned hier's answer → 0.30 quality. **This is a documented single-model self-confidence failure.**
2. **Self-verifier is over-eager elsewhere.** On 7–8 of 10 questions the verifier said `confident: 0` (on hedging, missing citations) even when hier's answer was actually fine — so cascade always paid tier-2 anyway.

**Ensemble works** — 0.995 quality at $0.43, matches full_context at 64% the cost. But still 3× the oracle. Judge-based A-vs-B selection is a better signal than self-verification.

**Implication for routing:** the highest-leverage next experiment is **replacing LLM self-verification with an orthogonal verifier** — a cross-model check (agent = Sonnet, verifier = Haiku), a retrieval-reranker confidence score, or a small fine-tuned classifier trained on labeled outputs.

### 3.2 Category-label router (degenerate on this N)

Routing by question `category` label (assuming you had one at serve time, which you don't) picks full_context for every category on this data because full_context is always max-quality. Collapses to the full_context row. Category is the wrong feature at this scale.

### 3.3 Practical routers — what we built vs what's left

1. **Cheap-first cascade** (BUILT, underperformed)
   - Tier 1 hier → self-verify → Tier 2 agent → self-verify → Tier 3 full. Actual: 0.925 at $0.904. Verifier bias killed it.
   - Fixable by: cross-model verifier (Haiku verifies Sonnet), or retrieval-score confidence, or learned confidence classifier.

2. **Ensemble with judge-pick** (BUILT, best real result)
   - Run hier + agent in parallel, judge picks A/B. Actual: 0.995 at $0.428. Matches full_context quality, 64% the cost.
   - Room to cheapen: use Haiku as the picker instead of Sonnet.

3. **Learned router** (NOT built — needs scale)
   - Small classifier: `route(question, corpus_schema) -> strategy_id`
   - Training signal: historical per-question winners. Needs ≥100 labeled Qs first — blocked on benchmark-scale work.

4. **Confidence-calibrated ensemble** (NOT built)
   - Run 2 cheapest in parallel, agree → return, disagree → expensive tiebreaker. Bounded cost. Needs an agreement metric.

5. **Self-consistency / best-of-N** (NOT built, low priority)
   - Budget blow-up risk, marginal benefit on deterministic QA.

### 3.4 Ensemble viability — actual numbers

Partial ensemble (hier + agent_managed + judge-pick) ACTUAL: **0.995 quality at $0.428** — matches full_context (0.995 at $0.670) at 64% the cost. Not as cheap as oracle, not as cheap as agent_managed alone ($0.320), but higher quality than either.

Full 7-way ensemble would cost ~$2.9/10q (sum of all strategies) for the same ceiling — strictly worse than the 2-way build. Not worth it.

**Only cheaper ensemble worth trying:** swap the judge-picker from Sonnet to Haiku. Expected cost: ~$0.35/10q, quality should hold. Blocked only on writing a small helper.

### 3.4.1 How ensemble is optimization — the combination it actually is

The Stage 3 ensemble isn't a generic "run N strategies and vote." It's a **specific combination of two qualitatively different curation regimes picked because their failure modes are disjoint:**

| component | what it is | what it's good at | what it fails on |
|---|---|---|---|
| `hierarchical` (= optimized curator) | map-summarize-route-expand: LLM chooses 2–5 docs based on titles + summaries | cheap, fast, right 91% of the time on this corpus | routes to wrong doc when the question's keywords don't match the relevant doc's summary (q-v2-010 military leave) |
| `agent_managed` (= self-managed curator) | tool-use loop: model calls `list_*` + `get_*` itself, runs up to 6 turns | 99% quality because the model sees titles *and* reasons about which to fetch, with retries | slower, ~5× the tokens of hierarchical; can still miss nuance on needs_both questions |
| **judge-LLM picker** | sees both answers + the question, picks A or B on correctness + specificity | selects the right answer when one of the two is wrong, catches staleness/hedging mismatches | tied on quality-ceiling — if both are wrong, picker can't fix it |

**Why it beats "simple agent" (agent_managed alone) by only 0.5pp while adding 34% cost:**
- agent_managed alone covers ~9/10 of the failure space already. The marginal question where hier catches something agent misses is rare.
- The judge-pick is essentially **insurance**, not a quality lift. At this N it's within noise; at higher N with harder questions the gap should widen.

**Why it beats "simple context" (full_context) at 64% the cost with the same quality:**
- full_context pays for every doc on every question — the model has to do its own in-context retrieval, and those tokens are charged.
- Ensemble pays for (cheap curator's fetch of 2–5 docs) + (smart curator's tool-use of 2–3 more) + (tiny judge-pick call). Total tokens ~10k vs full_context's 20k.
- Same quality ceiling because, between hier and agent_managed, one of them almost always has the right answer.

**Framing: ensemble is a learned(-in-context) *selection function* over two curators.**
- Hierarchical answers a "short-horizon retrieval" view. Agent-managed answers a "long-horizon reasoning" view. They're complementary by design.
- The judge-LLM is a single-shot classifier that reads both answers and picks. It's NOT running its own retrieval — it's arbitrating between two pre-computed candidates.
- This is exactly what a hand-crafted router would do if you didn't have training data — ensemble *is* the training-data-free router for this pair.

**What ensemble is NOT:**
- Not self-consistency (not running one strategy N times).
- Not majority voting (only 2 votes; judge-LLM breaks ties, not majority).
- Not a quality boost over the SOTA single strategy (agent_managed) — it's a *variance reduction* over the SOTA single strategy.

**Why cascade failed and ensemble worked despite using the SAME two strategies under the hood:**
- Cascade asks the model "are you confident?" about its own answer — single-view, self-referential, notoriously miscalibrated.
- Ensemble asks the model "A or B?" about two independently-produced answers — two-view, comparative, much better calibrated. Judge-pick is the same architectural trick that makes RLHF-style reward models work: comparing beats scoring-in-isolation.

**The implication for the meta-meta-harness direction:** the optimization target isn't just "pick a strategy," it's **"pick a PAIR of complementary strategies + a selector."** The search space is (strategy_A × strategy_B × selector_model × selector_prompt). At N=10 the Pareto frontier is thin; at N=100+ it becomes a real search problem.

### 3.5 What a router demo would need

- ≥50 labeled questions with per-strategy quality scores (for training a real router)
- A confidence signal on each strategy (self-reported or verifier-based)
- An escalation threshold chosen on a dev split, not the eval set
- A cost ceiling argument (`--max-cost-usd`) so a misfiring router can't cascade to full_context for every question

### 3.6 Honest caveats

- All numbers above come from N=10 with no variance estimate — oracle/router quality of 1.000 reflects that ceiling is already saturated on this eval, not that routing is magical.
- At larger N with harder questions, the gap between hierarchical and agent_managed will widen; cascade cost will rise accordingly.
- Routing only matters if the failure modes are **recoverable** — i.e. some other strategy gets the right answer. On Stage 3 every failed cell had at least one 1.00 peer, so recoverable. Real-world evals may have questions that *no* strategy handles, which routing can't fix.

### 3.7 Recommended next experiments

Given cascade's self-verification failure and ensemble's 3× oracle-gap, the highest-leverage next work, in order:

1. **Cross-model verifier for cascade.** Replace Sonnet-verifies-Sonnet with Haiku-verifies-Sonnet (or vice versa). Cheap, probably fixes q-v2-010. `src/strategies_cascade.py` already modular — swap the verifier model.
2. **Haiku-judge ensemble.** Drop ensemble cost from $0.43 → ~$0.35 with minor quality risk. One-line change.
3. **Scale to N ≥ 100** (benchmark-readiness checklist). Every router/ensemble claim at N=10 is anecdotal.
4. **Learned router.** After (3), train a logistic or small-BERT classifier on per-question winners. Compare to oracle as ceiling.
5. **Cost-capped routing** — `--max-cost-usd`, `--max-latency-s` — so a misfiring cascade can't burn through tier-3 on every question.
6. **Meta-meta-harness** — once (1–5) are solid, multi-objective-optimize (quality, cost, latency) over the full routing space (strategy set, verifier choices, thresholds). Pareto frontier report.
