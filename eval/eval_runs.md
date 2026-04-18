# Eval Runs — Master Log

## Stage 3 — 7 strategies on N=10 v2 questions  (commit pending, 2026-04-18)

**Host:** laptop (macOS, Python 3.13) · **Models:** all roles = `claude-sonnet-4-6` · **Concurrency:** 6 (phase 1), 2–3 (phases 2–3)
**Corpus:** 11 GitLab Handbook docs uniformly timestamped `2026-01-01T00:00:00Z` + 10 Slack-API-shape threads (`validated_by_hr=true`, timestamps 2026-04-08 to 2026-04-17)
**Question set:** N=10 in `data/test_questions_v2.json`
  - 4 `slack_contradicts` (recent Slack value differs from stale handbook value — tests consolidation)
  - 2 `slack_only` (info only in Slack, not in handbook)
  - 2 `needs_both` (handbook policy + current Slack detail)
  - 2 `portal_only` (handbook correct, no Slack touches)
**Optimizer:** n_iter=2, train_n=4 (first 4 questions; **train ⊂ eval** — no held-out split in Stage 3)
**SDK config:** `AsyncAnthropic(max_retries=6, timeout=120s)` — needed after a prior run caught 12 × 429s
**Phase order:** 5 base strategies concurrent → cascade_router (concurrency=2) → ensemble (concurrency=2)

### Summary

| strategy | quality | f1 | EM | key_fact_recall | latency_s | prompt_tok | cost_usd |
|---|---|---|---|---|---|---|---|
| full_context           | 0.995     | 0.534 | 0.00 | 0.08 | 6.59 | 19,957 | 0.670 |
| meta_harness_optimized | 0.890     | 0.467 | 0.00 | 0.00 | 7.46 | 11,863 | 0.431 |
| rag_embedding          | 0.925     | 0.455 | 0.00 | 0.025 | 6.75 | 2,161 | 0.141 |
| hierarchical           | 0.910     | 0.491 | 0.00 | 0.02 | 6.05 | **1,489** | **0.118** |
| agent_managed          | 0.990     | 0.524 | 0.00 | 0.02 | 8.95 | 7,739 | 0.320 |
| cascade_router         | 0.925     | 0.546 | 0.00 | 0.065 | 23.5 | 24,522 | 0.904 |
| **ensemble**           | **0.995** | 0.527 | 0.00 | 0.02 | 11.3 | 9,817 | 0.428 |

Oracle-router upper bound on this same data: **quality 1.000 at $0.138** (picks hierarchical 9/10, agent_managed 1/10 on q-v2-010 only).

### Per-question × strategy (quality)

```
qid        category            full_contex meta_harnes rag_embeddi hierarchica agent_manag cascade_rou    ensemble
q-v2-001   slack_contradicts          1.00       1.00       1.00       1.00       1.00       1.00       1.00
q-v2-002   slack_contradicts          1.00       1.00       1.00       1.00       1.00       1.00       1.00
q-v2-003   slack_contradicts          1.00       1.00       1.00       1.00       1.00       0.95       1.00
q-v2-004   slack_contradicts          1.00       1.00       1.00       1.00       1.00       1.00       1.00
q-v2-005   slack_only                 1.00       1.00       1.00       1.00       1.00       1.00       1.00
q-v2-006   slack_only                 1.00       1.00       1.00       1.00       1.00       1.00       1.00
q-v2-007   needs_both                 0.95       1.00       0.95       1.00       0.90       1.00       0.95
q-v2-008   needs_both                 1.00       1.00       1.00       1.00       1.00       1.00       1.00
q-v2-009   portal_only                1.00       0.00       1.00       1.00       1.00       1.00       1.00
q-v2-010   portal_only                1.00       0.90       0.30       0.10       1.00       0.30       1.00
```

### What each strategy actually did

- **full_context** — concatenated every handbook doc (11) + every Slack-API thread (10) into every prompt.
- **meta_harness_optimized** — optimizer's final `CurationSpec`: `ordering=slack_first`, `doc_format=structured`, `max_chars_per_doc=6000`, with an excluded static doc that caused the 0.00 on q-v2-009 (classic train-set overfit).
- **rag_embedding** — 21 docs → ~60 chunks (1200 chars, 200 overlap), embedded with local `BAAI/bge-small-en-v1.5`, FAISS `IndexFlatIP`, top-6 chunks per question.
- **hierarchical** — **no embedding retrieval.** Map (1-sentence summary per doc, cached) + Route (LLM picks 2–5 doc_ids from catalog) + Expand (full text of picks). Dropped to 0.10 on q-v2-010 when the router missed `parental-and-other-leave.md` for "military leave".
- **agent_managed** — tool-use loop (max 6 turns) with `list_handbook` / `get_handbook` / `list_slack` / `get_slack`. Typical flow: `list_*` both → `get_*` 2–3 docs → answer. Tokens summed across all turns.
- **cascade_router** (NEW) — Tier 1 hierarchical → self-verifier LLM call (`{"confident": 0|1}`) → if 0, Tier 2 agent_managed → verifier again → if 0, Tier 3 full_context. Reuses the same Sonnet for verify + answer.
- **ensemble** (NEW) — Runs hierarchical and agent_managed **in parallel** per question, then a judge-LLM picks A or B by correctness + specificity. Tokens additive.

### Failure modes (the useful part)

- `meta_harness_optimized` → **q-v2-009 = 0.00**, same as before. The optimizer's doc-exclusion mutation is a recurrent risk.
- `rag_embedding` / `hierarchical` → **q-v2-010** collapses (0.30 / 0.10). Same blind spot as prior run: retrieval/routing can't find `parental-and-other-leave.md` for "military leave".
- **`cascade_router` → q-v2-010 = 0.30. New failure mode:** tier-1 hierarchical returned a confidently wrong answer; the self-verifier said `confident: 1`; cascade never escalated. LLM self-verification is **over-confident on confidently-wrong outputs** — classic bias that makes cascade routing brittle in practice.
- `cascade_router` → **23.5s mean latency, $0.90 total cost**: the verifier says `confident: 0` most of the time for other reasons (hedging, no citations), so cascade pays for all 3 tiers on ~8/10 questions. Worse economics than agent_managed alone.
- `ensemble` → **q-v2-007 = 0.95**: judge picked hierarchical's answer when agent_managed's was also ~0.95. Not a failure; both were acceptable.

### Headline

**Ensemble matches full_context quality (0.995) at 64% the cost ($0.43 vs $0.67)** — the best demonstrated strategy at this model class.
**Cascade routing is worse than its tier-2 strategy alone** on this eval: self-verifier confident-but-wrong failures + always-escalating overhead.
**Oracle router is still 3× cheaper than ensemble** ($0.14 vs $0.43, same 1.000 quality) — room for a real router to close that gap if it can detect tier-1 wrong-answers better than LLM self-verification.

### Artifacts

- `output/results_stage3.csv` — all 70 rows (10 q × 7 strategies)
- `output/summary_stage3.json` — per-strategy means
- `output/final_spec_stage3.json`, `output/optimizer_history_stage3.json`
- `output/chart_stage3.png` — quality bar + cost-vs-tokens scatter (log-x)
- `output/chart_stage3_heatmap.png` — 7×10 quality grid

---

## Generalizability of these results

**What we believe generalizes** (with caveats):
- **Relative ordering on policy-Q&A-with-mixed-sources.** Ensemble ≈ full_context > agent_managed > rag ≈ hierarchical > meta-harness-small-train is an architecture story, not corpus-specific.
- **Cascade's self-verification failure.** LLM-self-confidence is miscalibrated on confidently-wrong outputs. This is documented in literature and our q-v2-010 reproduces it. **Any single-model cascade router inherits this bias.**
- **Token-efficiency ratios.** hier ~1.5k, RAG ~2k, agent ~8k, full ~20k, ensemble ~10k are model-independent.

**What does NOT generalize**:
- Absolute quality numbers (0.89–1.00) — N=10 resolution is 0.1; ±0.05 per cell is noise.
- Cost/latency — Sonnet 4.6 specific.
- Judge verdicts — self-preference bias, no human calibration.
- **Cascade's loss of 0.07 vs tier-2 alone** — specific to q-v2-010; may be less severe on a different eval.

**Train/eval contamination.** Meta-harness trained on questions[:4] then eval'd on all 10 — 4/10 cells are in-sample for it.

**Run-to-run variance not measured.** Temperature=0 on answers but 0.4 on proposer and 0 on judges/verifiers. A 3-seed run would likely shift cascade and ensemble cells by ±0.05.

---

## From Stage 3 to a real benchmark

What would be needed to upgrade this demo into a paper- or leaderboard-citable artifact:

### Statistical
1. **N ≥ 200** questions, preferably 500+. Cell resolution must be < 2pp.
2. **≥3-seed runs** per cell, report mean ± std.
3. Bootstrap confidence intervals on per-strategy quality.
4. Paired significance tests (McNemar, permutation) on per-question strategy differences.

### Splits
5. **Held-out test set.** Optimizer on train, Pareto-select on dev, report on test.
6. Per-category breakdowns ≥30 per category.

### Corpus
7. **Real-world data** — not synthetic. Design-partner or public (GitLab handbook git history + public community Slack).
8. **Realistic query distribution.** Current set is 40% `slack_contradicts`; real ops queries are 5–15% staleness.
9. **Multiple domains.** HR + customer support + legal + code docs.
10. Real version history for staleness (not uniformly 2026-01-01).
11. **Out-of-distribution questions** — 10–20% with no relevant source; tests whether agents refuse.

### Models
12. ≥3 agent models (Haiku / Sonnet / Opus; plus GPT-4o-mini and GPT-4o for cross-provider).
13. Separate judge model from agent model; 2 different judges + 50-Q human calibration.
14. Report inter-judge agreement (Cohen's κ).

### Routing-specific (new after cascade findings)
15. **Replace LLM self-verification with orthogonal verifier.** Options: a small fine-tuned classifier, retrieval-reranker scoring, or cross-model verification (agent = Sonnet, verifier = Haiku on a different prompt). Cascade's failure on q-v2-010 is specifically the single-model self-confidence trap.
16. **Learned router** (log-regression or small classifier) trained on ≥100 per-question winner labels. Compare to oracle as a ceiling.
17. **Cost-capped routing variants** (`--max-cost-usd`) so a misfiring cascade can't burn through full_context on every question.

### Infrastructure
18. One-click reproduction on a fresh machine (install + `.env` + `python main.py` → identical numbers).
19. Deterministic corpus snapshot (pin file hashes; no re-fetch on each run).
20. **Cost budget + rate-limit hygiene** — strategy phases, exponential backoff, and cost ceilings so a large run doesn't silently degrade (we hit 12 × 429 on the first rerun before staggering phases).
21. Public leaderboard + submission harness. Like SWE-bench Verified or τ-bench.

### Anti-patterns to resist
- Adding more metrics (BLEU, ROUGE, BERTScore) — adds columns, not insight. LLM-judge + F1 + EM is enough.
- A Stage 5 / Stage 6 of more strategies before fixing #1–#6 just adds noise cells.

---

## Template for future runs

```
### <UTC timestamp>  —  <git sha>  —  <stage>

- host: <laptop|aws-micro>
- models: agent=<model>, judge=<model>, proposer=<model>
- strategies: <list>
- questions: N=<n>, by_category=<breakdown>
- optimizer: iter=<n>, train_n=<n>, kept_improvements=<n>
- summary:
  | strategy | quality | f1 | latency_s | prompt_tok | cost_usd |
  |---|---|---|---|---|---|
  | ... | ... | ... | ... | ... | ... |
- artifacts: output/results_stageX.csv, output/final_spec_stageX.json, ...
- notes: <one-paragraph human-readable observation>
```
