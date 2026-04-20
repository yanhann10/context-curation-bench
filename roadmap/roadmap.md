# xcbench Roadmap

Open work items from peer-review feedback. Each section groups related items; within a section, items are roughly ordered by leverage-per-effort (highest first).

Status legend:
- `[ ]` not started
- `[~]` partial / in progress
- `[x]` done (kept here until we reference it elsewhere)

Context: a single-seed N=108 run on AWS Bedrock (Sonnet 4.5) exists for `full_context`, `rag_embedding`, `meta_harness`, `agent_managed` (historical HR track). The current default suites are still N=10 per domain. The items below assume Pareto-frontier claims, cross-domain ranking claims, and strategy comparisons are all open questions until the statistical foundation is rebuilt.

---

## Statistical rigor

- [ ] Scale default suites to N≥200 per domain. Prefer 400+ if judge cost permits.
- [ ] Multi-seed runs (≥3 seeds). Report mean + variance per cell, not single-seed scalars.
- [ ] Bootstrap confidence intervals on per-strategy quality/cost/latency aggregates. Plot CIs on the Pareto scatter.
- [ ] Paired significance tests on strategy deltas (McNemar for binary correctness, permutation for continuous quality). Drop "ranking flip" claims that don't survive at p<0.05.
- [ ] Per-question × per-strategy variance and outlier diagnostics. Surface which questions drive aggregate differences.
- [ ] Prompt-variant robustness: re-run with ≥2 rephrasings of each question to quantify prompt sensitivity.

## Judge reliability

- [ ] Human calibration on a stratified subset (~50–100 Q×strategy cells). Report judge–human agreement (Cohen's κ, Pearson on 0–1).
- [ ] Multi-judge ensemble (different provider family + a cheap model) with inter-judge agreement reporting.
- [ ] Faithfulness / grounding metrics: citation precision/recall, evidence coverage against `key_facts` and source spans.
- [ ] Sanity-check that `key_facts` don't encode category/Slack-origin signal (audit after the judge-prompt leak fix).
- [ ] Replace or rehabilitate `key_facts_recall` (substring match) and token F1 — both currently non-discriminative.
- [ ] Out-of-distribution / unanswerable questions to measure refusal vs hallucination per strategy.

## Measurement methodology

- [ ] System-spec reporting block in every run artifact: hardware, region, concurrency, batch size, cache state (cold/warm), SDK versions, model revisions.
- [ ] Separate TTFT and TPOT in latency reporting, not just end-to-end wall-clock.
- [ ] Amortized vs non-amortized cost modes. Amortized includes embedding, FAISS index build, hierarchical-summary cache, proposer calls; non-amortized is per-query marginal.
- [ ] Strip judge cost from strategy cost ratios (judge is a fixed floor that dilutes curation savings). Report both "with judge" and "agent-only" cost columns.
- [ ] Budgeted comparisons: max-quality-under-$X/query and max-quality-under-Y-seconds/query Pareto fronts.

## Retrieval diagnostics

- [ ] recall@k, α-nDCG, and redundancy metrics for retrieval-grounded strategies (`rag_embedding`, `hierarchical`, `cascade_router` tier 1).
- [ ] CRUX-style sub-question / coverage metrics to separate retrieval failure from generation failure.
- [ ] Context sufficiency diagnostic: does the retrieved bundle contain every `key_fact` needed to answer?
- [ ] Failure-mode attribution table per question: retrieval-miss vs routing-miss vs generation-miss vs judge-miss.

## Baselines to add

- [ ] Hybrid sparse+dense retrieval (BM25 + dense, optional host/authority boost).
- [ ] Cross-encoder reranker (monoT5 or similar) on top of `rag_embedding` and `hierarchical`.
- [ ] CRUX long-form diagnostic — adopt as a coverage metric on our corpora.
- [ ] RAGPerf-style end-to-end measurement harness alignment (index choices, hardware counters, reporting granularity).
- [ ] Structured / hierarchical retrieval baselines: Halo, LATTICE, FABLE. At least one of these as a comparator to test whether our ranking-flip claim holds with stronger structured methods.
- [ ] CirrusBench-style progression-rate + efficiency index for `agent_managed` and `cascade_router` (multi-turn / tool-use reliability).
- [ ] QAMR-style version-aware retrieval on staleness/contradiction subsets.
- [ ] Public-health-policy style cross-encoder-reranked RAG as an additional baseline.

## Ablations & sensitivity

- [ ] Chunk size × top-k sweep for `rag_embedding`. Report sensitivity curves.
- [ ] Reranker on/off ablation — quantify how much of the baseline RAG underperformance is "no reranker" vs architectural.
- [ ] Agent loop-limit sensitivity (max_turns) for `agent_managed` and `thick_harness`.
- [ ] Corpus factor ablations: doc length, staleness density, contradiction severity, contradiction count per question.
- [ ] Rerun Polars after the prompt-portability fix is confirmed across all 4 flagged strategies, with CIs, and report delta vs current reported numbers.
- [ ] Sensitivity to category distribution: re-weight questions to a realistic 5–15% staleness mix and re-compute rankings.

## Adaptive / advanced strategies

- [ ] Mixed-strategy controller that picks a strategy per query (ARC-style adaptive configuration). Test whether it dominates every single strategy on the Pareto front.
- [ ] Cross-model self-verifier for `cascade_router` (current implementation uses the same model as generator — known blind-spot). Quantify the gap.
- [ ] Cross-strategy disagreement as an escalation signal (cheaper than self-verification, closer to oracle behavior per the ccbench routing analysis).
- [ ] Evidence-scored verification for cascade/ensemble — block on missing evidence, not on hedging.
- [ ] Version-aware retrieval primitive for stale/contradictory corpora (dual-chunking, RankRAG-style).

## Corpus / data quality

- [ ] Document sourcing + validation procedure for all synthetic artifacts (Slack threads, Polars "maintainer discussions", HR overlays). Include provenance, author, validator, contradiction design.
- [ ] Release licensing clearance on each corpus before public drop.
- [ ] Add at least one corpus that is NOT clean binary-flip contradictions — ambiguous policies, partial overlaps, multi-step reasoning chains.
- [ ] Multi-release / document-versioning corpus to exercise staleness behavior under realistic update cadence.
- [ ] Distribution-shift / update-cadence evaluation: how fast does each strategy adapt when fresh updates conflict with static canon? Rollback risk?

## Reproducibility & release

- [ ] Publish judge prompts, pricing assumptions, and all seeds with every run artifact.
- [ ] License + step-by-step replication instructions specifically for latency/cost measurements (hardware, region, concurrency).
- [ ] CI matrix that runs the cross-domain suite, not just a single-suite smoke test.
- [ ] Interop adapter so xcbench results can be consumed by existing frameworks (e.g. RAGPerf).
- [ ] Strategy-implementation spec doc (hierarchical, cascade_router, ensemble, meta_harness) with enough detail to reproduce without reading code.

## Presentation / framing

- [ ] Stop mixing N=10 HR-policy numbers with N=108 Bedrock numbers in the same README table. Pick one canonical results table per section.
- [ ] Explicitly label the oracle router as "theoretical upper bound, non-deployable" wherever it appears.
- [ ] Define "cell resolution 0.10" precisely — is it rounded reporting, judge discretization, or N-imposed granularity? Currently documented as "N=10 → ±0.05 per cell" in eval docs; promote that into the README.
- [ ] Clearly separate historical Sonnet-4.5 Bedrock numbers from current-default Sonnet-4.6 numbers wherever they coexist.

## Known fixes blocking a clean rerun

- [~] Prompt-portability bug — partially fixed per commit `50aac77`, but the self-review flagged 4 strategies still hardcode HR persona. Full audit + rerun needed before any agent_managed / thick_harness / meta_harness Polars number is trustworthy.
- [ ] Verify category leakage fix (commit `48ec5ea`) propagated to all judge call sites and historical runs are re-scored under the clean prompt.
- [ ] Confirm train/dev/held-out split (commit `428440b`) is actually wired in every suite YAML, not just HR.
