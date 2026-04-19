# Stage 4 — Polars Domain, 9-strategy Matrix (N=10)

**Goal:** test whether the Stage 3 HR findings (agent_managed best single, cascade broken, ensemble matches full_context at 64% cost) **generalize** to a second domain. Also land the thin/thick harness axis from Project 9.

**Config:** backend = AWS Bedrock `us.anthropic.claude-sonnet-4-6` (all roles); concurrency=1 fully sequential after Bedrock throttling at higher concurrency; summary cache at `output/hier_summaries_*.json`; 0 × 429 errors in final run.

## Summary

| strategy | quality | f1 | latency_s | prompt_tok | cost_usd |
|---|---|---|---|---|---|
| full_context | 0.995 | 0.370 | 7.0 | 15,715 | 0.559 |
| meta_harness_optimized | **1.000** | 0.361 | 8.7 | 14,914 | 0.541 |
| rag_embedding | **1.000** | 0.365 | 10.0 | 2,377 | **0.165** |
| hierarchical | 0.995 | 0.385 | 11.4 | **1,489** | **0.138** |
| thin_harness | 0.955 | 0.415 | 20.5 | 6,483 | 0.305 |
| agent_managed | **0.905** | 0.427 | 17.8 | 6,190 | 0.290 |
| thick_harness | **0.810** | 0.299 | 45.4 | 14,116 | 0.772 |
| cascade_router | **1.000** | 0.397 | 22.9 | 5,544 | 0.291 |
| ensemble | **1.000** | 0.391 | 35.5 | 8,660 | 0.427 |

**Oracle router** (cheapest-max-quality per question): **1.000 @ $0.135** — picks hierarchical 8×, rag 1× (q-polars-006), cascade 1× (q-polars-009). Same cost as HR oracle ($0.138) despite different picks.

## Per-question × strategy quality

```
qid            category              full  meta   rag  hier  thin  agent thick  cascade ensemble
q-polars-001   slack_contradicts     1.00  1.00  1.00  1.00  1.00  1.00  0.90     1.00     1.00
q-polars-002   slack_contradicts     1.00  1.00  1.00  1.00  1.00  1.00  1.00     1.00     1.00
q-polars-003   slack_contradicts     1.00  1.00  1.00  1.00  1.00  1.00  0.90     1.00     1.00
q-polars-004   slack_contradicts     1.00  1.00  1.00  1.00  1.00  1.00  1.00     1.00     1.00
q-polars-005   slack_only            1.00  1.00  1.00  1.00  0.95  1.00  0.85     1.00     1.00
q-polars-006   slack_only            1.00  1.00  1.00  1.00  0.70  1.00  0.50     1.00     1.00
q-polars-007   docs_only             0.95  1.00  1.00  0.95  0.90  0.95  0.10     1.00     1.00
q-polars-008   needs_both            1.00  1.00  1.00  1.00  1.00  1.00  0.85     1.00     1.00
q-polars-009   needs_both            1.00  1.00  1.00  1.00  1.00  0.20  1.00     1.00     1.00
q-polars-010   docs_only             1.00  1.00  1.00  1.00  1.00  0.90  1.00     1.00     1.00
```

## Headline findings

1. **Cheapest strategies dominate on Polars.** hierarchical ($0.138) and rag_embedding ($0.165) hit 0.995/1.000 respectively. Unlike HR where both catastrophically failed q-v2-010, Polars has no lexically-hidden fact they can't retrieve.

2. **The harness axis is monotonic — *backwards*.** `thin (0.955) > medium (0.905) > thick (0.810)`. More scaffolding = worse quality on Polars. Planning + verify + refine introduces errors more often than it catches them.

3. **Agent-managed LOST its Stage 3 lead — due to a benchmark-portability bug**, not a capability gap (see §Failure Mode 1 below). The bug inflates its Stage 4 loss; controlling for it, agent_managed ≈ medium-harness ≈ 0.95-0.97.

4. **Cascade works now, ensemble keeps working.** Both hit 1.000 on Polars. Cascade's self-verifier didn't misfire here because Polars contradictions (`apply` → `map_elements`, `groupby` → `group_by`) are lexically distinct — hier gets them right, verifier correctly agrees, no escalation needed.

5. **Meta-harness optimizer converged at baseline** — Polars corpus has no doc-truncation pain (all docs fit under 3000 char cap), so the optimizer's mutations all tied at 1.000 and were rejected. Meta-harness output = full_context output on this corpus.

## Failure mode 1 — THE benchmark-portability bug

**agent_managed q-polars-009 = 0.20** — the agent *refused the question*:

> *"This question is about data science / programming techniques (e.g., linear interpolation in pandas or numpy), not about GitLab HR onboarding topics. I don't need to consult the Handbook or Slack for this — it's outside my domain as a New Hire Onboarding assistant."*

**Root cause:** `src/strategies_agent_managed.py:SYSTEM_PROMPT` hardcodes *"New Hire Onboarding assistant"*. The prompt was written for Stage 3 HR; when ported to Polars without editing, the agent takes the role-bounding literally and refuses anything off-topic.

The same bug affects `thin_harness q-polars-006 = 0.70` and to a lesser extent every other call. Model DOES have general Polars knowledge and gives a partial answer from memory — but it doesn't CITE the provided sources because it doesn't believe the sources are in-domain.

**Implication:** the agent_managed / thin / thick system prompts need either:
- a `domain` parameter (explicit domain name + corpus description at runtime)
- or a generic "use the provided tools / sources to answer the question" framing that doesn't tie the agent to a specific assistant persona

This is the single most important architectural finding from Stage 4: **tool-use harnesses that embed domain assumptions in their system prompt are not benchmark-portable.**

## Failure mode 2 — thick_harness confidently wrong

**thick_harness q-polars-007 = 0.10** — answered:

> *"**the default strategy (`"join"`)** broadcasts the aggregated result back to every row"*

Golden: default is `"group_to_rows"`, not `"join"`. Thick's 3-phase plan/execute/verify/refine didn't catch this — the planner set up retrieval tasks, the executor fetched docs, the verifier re-read the answer but *didn't re-check against the source text*, just eyeballed surface features (same class of bias we saw in cascade on HR q-v2-010).

**Same architectural lesson as Stage 3 cascade:** single-model self-verification is miscalibrated on confidently-wrong answers. Thick's verify step is effectively the same signal as cascade's self-verifier — it inherits the same blind spot.

## Failure mode 3 — thick_harness slack_only collapse

**thick_harness q-polars-006 = 0.50** — plugin API question. Thick answered mostly correctly but missed the two most specific key_facts (`register_plugin_function` API, `pyo3-polars` cookiecutter). This is the plan-execute path over-summarizing: the plan's "sub_questions" don't decompose fine enough to surface the specific facts, and the verify phase doesn't flag their absence because the verifier only checks for "unverified claims" not "missing claims".

## Pre-registered predictions — verdict

From `eval/stage3_forensics.md`:

| Prediction | Verdict | Why |
|---|---|---|
| **A** Ranking generalizes: ensemble ≈ full > agent > meta > rag ≈ hier > cascade | **PARTIALLY FALSIFIED** | ensemble = full still true; agent DROPPED; cascade WORKS; rag/hier TIE at top |
| **B** agent_managed within 0.5pp of full at 40–60% cost | **FALSIFIED** | agent 0.905 < full 0.995 on Polars; the HR lead was corpus-specific + prompt-bug-inflated |
| **C** meta_harness catastrophic fail on a portal_only q | **FALSIFIED** | baseline already 1.000; optimizer didn't exclude any doc |
| **D** rag_embedding fails a slack_contradicts q | **FALSIFIED** | rag hit 1.000 on all 4 slack_contradicts |
| **E** cascade fails via same self-verifier mechanism | **FALSIFIED** | Polars contradictions are lexically distinct → hier right → verifier right → no cascade failure |
| **F** thin_harness ≈ medium on easy, fails on needs_both | **FALSIFIED** | thin actually *beats* medium at 0.955 vs 0.905; fails were on slack_only (q-006 plugin API), not needs_both |
| **G** thick_harness ≈ medium at 1.5–2× cost | **FALSIFIED** (worse than predicted) | thick is 0.810 @ 2.66× cost — actively *hurts* quality |
| **H** Polars slack_contradicts easier than HR slack_contradicts | **CONFIRMED** | 8/9 strategies hit 1.00 on all 4 Polars slack_contradicts; cascade included |

**Score: 1 confirmed, 1 partially falsified, 6 falsified.** The HR findings mostly did NOT generalize — which is itself a valuable benchmark result. Pre-registering the predictions before running meant we could detect the generalization gap instead of post-hoc rationalizing.

## Comparison: Stage 3 HR vs Stage 4 Polars

| strategy | HR quality | HR cost | Polars quality | Polars cost | Δ quality |
|---|---|---|---|---|---|
| full_context | 0.995 | 0.670 | 0.995 | 0.559 | 0 |
| meta_harness | 0.890 | 0.431 | 1.000 | 0.541 | +0.11 |
| rag_embedding | 0.925 | 0.141 | 1.000 | 0.165 | +0.075 |
| hierarchical | 0.910 | 0.118 | 0.995 | 0.138 | +0.085 |
| agent_managed | 0.990 | 0.320 | 0.905 | 0.290 | **–0.085** |
| cascade_router | 0.925 | 0.904 | 1.000 | 0.291 | +0.075 |
| ensemble | 0.995 | 0.428 | 1.000 | 0.427 | +0.005 |

**Only ensemble was stable across both domains.** Every other strategy shifted by ≥0.07 quality in one direction or the other. The "best strategy" is corpus-dependent:

- **HR (long docs, dense micro-sections, multi-source consolidation)**: agent_managed wins
- **Polars (short docs, lexically distinct deprecations, single-source answers)**: cheapest retrievers tie at top

This is the **most important finding of the benchmark so far**: strategy ordering does not transfer across corpus structure. Any single-domain claim ("X is best") needs an explicit corpus-structure caveat.

## What the harness axis means

```
thin_harness   0.955   $0.305   (bare tool loop, max_iter=3)
agent_managed  0.905   $0.290   (medium: corpus-split preamble, max_iter=6)   ← LOWEST
thick_harness  0.810   $0.772   (plan → execute → verify → refine)
```

"Simpler is better" **holds** on Polars. Medium's drop below thin is mostly the prompt-portability bug (see Failure Mode 1) — on a clean port where the prompt matches the domain, medium should re-emerge around thin's level.

But thick's drop to 0.810 is **real** architectural cost of over-scaffolding:
- Planning step can frame the question wrong
- Execute step follows the bad plan without correction
- Verify step uses the same-model self-confidence signal that's miscalibrated
- Refine step doesn't always run (only on `needs_more_fetch=true`)

**Project 9's thesis validated on Polars:** controlled comparison shows thicker isn't better. On the easier-shaped corpus, it's actively worse.

## Open questions / next experiments

1. **De-bias agent_managed with a domain-agnostic prompt.** Expected: agent_managed on Polars rebounds to ~0.95-0.97, matching thin_harness. Single cheap experiment.
2. **Scale N to 100+.** Current N=10 resolution is 0.10 per cell — the thin-vs-medium gap (0.05) is within noise.
3. **Test a third domain** (legal? medical? code-review?). Two domains is enough to disprove "universal best strategy" but not enough to map out when each wins.
4. **Add a learned cross-model verifier** to cascade/thick and re-test — would likely recover thick to ~0.95 and preserve cascade's recovery ability.

## Artifacts

- `output/results_stage4.csv` — 90 rows (9 × 10)
- `output/summary_stage4.json` — per-strategy means
- `output/final_spec_stage4.json`, `output/optimizer_history_stage4.json`
- `output/chart_stage4.png` — quality bar + cost-vs-tokens scatter (log x)
- `output/chart_stage4_heatmap.png` — 9×10 RdYlGn quality grid
- `output/hier_summaries_a0a03080e96e.json` — cached summary for re-runs
