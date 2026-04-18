# Eval Runs — Master Log

## Stage 3 — 5 strategies on N=10 v2 questions  (commit `0128510`, 2026-04-18)

**Host:** laptop (macOS, Python 3.13) · **Models:** all roles = `claude-sonnet-4-6` · **Concurrency:** 6
**Corpus:** 11 GitLab Handbook docs uniformly timestamped `2026-01-01T00:00:00Z` + 10 Slack-API-shape threads (`validated_by_hr=true`, timestamps 2026-04-08 to 2026-04-17)
**Question set:** N=10 in `data/test_questions_v2.json`
  - 4 `slack_contradicts` (recent Slack value differs from stale handbook value — tests consolidation)
  - 2 `slack_only` (info only in Slack, not in handbook)
  - 2 `needs_both` (handbook policy + current Slack detail)
  - 2 `portal_only` (handbook correct, no Slack touches — tests whether strategies over-index on Slack noise)
**Optimizer:** n_iter=2, train_n=4 (first 4 questions). NOTE: train ⊂ eval; no held-out split in Stage 3 (see generalizability section).
**Metric change:** `recency` dropped — all strategies hit 1.0 on Stage 2, so it's rolled into `quality` (judge penalizes stale-on-recency-sensitive to ≤0.5).

### Summary

| strategy | quality | f1 | EM | key_fact_recall | latency_s | prompt_tok | cost_usd |
|---|---|---|---|---|---|---|---|
| full_context            | **1.000** | 0.532 | 0.00 | 0.06 | 6.20 | 19,957 | 0.667 |
| meta_harness_optimized  | 0.895     | 0.455 | 0.00 | 0.00 | 7.72 | 11,863 | 0.432 |
| rag_embedding           | 0.925     | 0.464 | 0.00 | 0.025 | 6.78 | 2,161 | 0.143 |
| hierarchical            | 0.915     | 0.501 | 0.00 | 0.04 | 6.05 | **1,489** | **0.116** |
| **agent_managed**       | **0.995** | 0.537 | 0.00 | 0.02 | 9.66 | 7,738 | 0.318 |

### Per-question × strategy (quality)

```
qid        category           full_conte meta_harne rag_embedd hierarchic agent_mana
q-v2-001   slack_contradicts        1.00       1.00       1.00       1.00       1.00
q-v2-002   slack_contradicts        1.00       1.00       1.00       1.00       1.00
q-v2-003   slack_contradicts        1.00       1.00       1.00       1.00       1.00
q-v2-004   slack_contradicts        1.00       1.00       1.00       1.00       1.00
q-v2-005   slack_only               1.00       1.00       1.00       1.00       1.00
q-v2-006   slack_only               1.00       1.00       1.00       0.95       1.00
q-v2-007   needs_both               1.00       0.95       0.95       1.00       0.95
q-v2-008   needs_both               1.00       1.00       1.00       1.00       1.00
q-v2-009   portal_only              1.00       0.00       1.00       1.00       1.00
q-v2-010   portal_only              1.00       1.00       0.30       0.20       1.00
```

### What each strategy actually did

- **full_context** — concatenated every handbook doc (11) + every Slack-API thread (10) into every prompt. Static-first ordering, titled format. No selection.
- **meta_harness_optimized** — optimizer's final `CurationSpec` on this run set `include_static_ids` to a **subset** (excluded `us-benefits-overview`), `include_slack_ids` = all, `ordering=slack_first`, `doc_format=structured`, `max_chars_per_doc=6000`. That exclusion caused the 0.00 on q-v2-009 (the STD-benefits question).
- **rag_embedding** — chunked 21 docs into ~60 chunks (1200 chars, 200 overlap), embedded with local `BAAI/bge-small-en-v1.5` (384-d), built a FAISS `IndexFlatIP` over L2-normalized vectors (IP == cosine), retrieved **top-6 chunks** per question. No rerank.
- **hierarchical** — **does NOT use embedding retrieval.** Two LLM passes: (1) each of the 21 docs got a 1–2-sentence summary from a Haiku/Sonnet call (cached once per run); (2) per question, the router got a catalog `id | title | timestamp | summary` and returned `{"doc_ids": [...]}` with 2–5 picks; (3) the full text of those picks was sent to the answerer. When the router picked wrong (q-v2-010: military leave), quality collapsed to 0.20.
- **agent_managed** — tool-use loop (max 6 iterations) with 4 tools:
  1. `list_handbook()` → `[{id, title, timestamp}]` for all 11 handbook docs
  2. `get_handbook(doc_id)` → full markdown
  3. `list_slack()` → `[{id, title, timestamp, channel, user, relationship}]` for all 10 Slack threads
  4. `get_slack(thread_id)` → full thread text

  System prompt told it: "handbook is dated 2026-01-01 (potentially stale); Slack is HR-validated, recent. Prefer recent on disagreement. Cite titles." Observed behaviour per question: typical flow was `list_handbook` + `list_slack` on turn 1 → `get_handbook(X)` + `get_slack(Y)` across 2–3 additional turns → final answer on last turn. All tokens across every turn are summed into the reported `prompt_tokens` / `completion_tokens` / `cost_usd`.

### Failure modes (the useful part of this run)

- `meta_harness_optimized` → **q-v2-009 = 0.00** (STD benefits). Optimizer overfitted to the 4-question train set and excluded a doc that mattered for the (unseen) portal_only question. Architectural risk: proposer trades breadth for small wins; a single bad mutation can strand a future topic.
- `rag_embedding` → **q-v2-010 = 0.30** (military leave 90-day reinstatement). The relevant section of `parental-and-other-leave.md` wasn't in the top-6 because the query lexically looks like a travel/time-off question.
- `hierarchical` → **q-v2-010 = 0.20**. Router picked the wrong set because the summary for `parental-and-other-leave.md` didn't surface "military leave" as a keyword.
- `agent_managed` → only deviation was **q-v2-007 = 0.95** (needs_both: contractor onboarding). Inspection: agent fetched both sources but phrased the final answer less precisely than golden.

### Headline

**Agent-managed matches full-context quality (0.995 vs 1.000) at 48% the cost ($0.318 vs $0.667).** Cheapest cell (hierarchical $0.12) buys 91.5% quality with 1 catastrophic failure. "Just stuff the window" is correct but 2× overpriced on this eval.

### Artifacts

- `output/results_stage3.csv` — all 50 rows (10 q × 5 strategies)
- `output/summary_stage3.json` — per-strategy means
- `output/final_spec_stage3.json`, `output/optimizer_history_stage3.json`
- `output/chart_stage3.png` — quality bar + cost-vs-tokens scatter (log-x)
- `output/chart_stage3_heatmap.png` — 5×10 quality grid, RdYlGn

---

## Generalizability of these results

**What we believe generalizes** (with caveats):
- **Relative ordering of strategies on policy-Q&A-with-mixed-sources.** Agent-managed > full_context > rag ≈ hierarchical > meta-harness-with-small-train is a story about architecture, not this specific corpus.
- **Token-efficiency numbers.** RAG/hierarchical at ~2k prompt tokens and agent-managed at ~8k are model-independent (tokens are properties of what you put in context).
- **Failure classes.**
  - Retrieval-only strategies (RAG, hierarchical) have zero-shot blind spots on portal_only questions whose keywords don't match the relevant doc. Architectural.
  - Proposer-based optimization overfits when train set is small. Architectural.

**What does NOT generalize**:
- **Absolute quality numbers (0.90–1.00).** N=10 gives no statistical power; with 5 strategies × 10 cells the resolution is 0.1. Rerun with different seed or paraphrased questions could shift each cell by ±0.05–0.10.
- **Cost/latency ratios.** Sonnet 4.6 specific. Different models have different $/token and different speeds.
- **Judge verdicts.** Sonnet judging Sonnet has known self-preference bias. No human calibration.
- **"All strategies get slack_contradicts right."** Only 4 such questions; real workplace query distribution may expose weaker consolidation in RAG/hierarchical.
- **The specific 0.00 on q-v2-009 and 0.20 on q-v2-010.** These are real failure modes but anecdotal — they'd need to reproduce across many question paraphrasings to be called a property of the strategy.

**Run-to-run variance not measured.** Temperature=0 reduces but doesn't eliminate it; the proposer's mutations are sampled at temperature=0.4. A 3-run minimum is needed before any cell-level claim.

**Train/eval contamination.** The optimizer trained on `questions[:4]` and was evaluated on all 10 — so 4 of the 10 reported cells are in-sample for the meta-harness strategy. The meta-harness "quality" row is inflated relative to a true held-out score.

---

## From Stage 3 to a real benchmark

What would be needed to upgrade this demo into something a paper or a leaderboard could cite:

### Statistical
1. **N ≥ 200 questions**, preferably 500+. Current N=10 gives cell-resolution of 0.10 at best; a 2pp difference between two strategies is indistinguishable from noise.
2. **3-seed minimum per cell**, reporting mean ± std. Essential for any claim of "strategy A beats B".
3. **Bootstrap confidence intervals** on per-strategy quality (e.g. 95% CI).
4. **Paired significance tests** (McNemar, permutation) on per-question strategy differences.

### Splits
5. **Held-out test set.** Optimizer sees only train, Pareto-frontier selection done on dev, numbers reported on test. Current build trains on `questions[:4]` and evals on all 10.
6. **Per-category breakdowns** large enough to be meaningful (≥30 per category).

### Corpus
7. **Real-world data, not synthetic.** Either a design-partner company's Slack + handbook, or public (GitLab handbook git history + public community Slack archives with timestamps).
8. **Realistic query distribution.** Current set is 40% `slack_contradicts` — intentionally stressful. Real distribution is probably 5–15%. Need both.
9. **Multiple domains.** HR + customer support + legal + code docs. Current findings are "policy Q&A with staleness" — portability beyond that is untested.
10. **Real version history.** Instead of uniformly dating handbook at 2026-01-01, use actual git history so staleness varies per section.
11. **Out-of-distribution questions.** 10–20% with no relevant source — tests whether agents correctly refuse instead of hallucinating.

### Models
12. **≥ 3 agent models.** Haiku, Sonnet, Opus. Plus at least one non-Anthropic (GPT-4o-mini, GPT-4o). Current single-model results don't tell us whether agent-managed's win holds at Haiku.
13. **Separate judge model from agent model.** Preferably 2 different judges, plus 50-question human calibration.
14. **Judge variance.** Report inter-judge agreement (Cohen's κ) — if two competent judges disagree on 20% of cells, the benchmark is noisy.

### Infrastructure
15. **One-click reproduction.** Clone + install + `.env` + `python main.py` → identical numbers. Current stage is close but untested on a fresh machine.
16. **Deterministic corpus snapshot.** Pin exact file hashes; don't re-fetch handbook on each run.
17. **Cost budget protection.** A run should surface `--max-cost-usd` and abort before overrunning.
18. **Public leaderboard.** Shared eval harness so new curation strategies can be submitted and ranked under identical conditions. Like SWE-bench Verified or τ-bench.

### Scope creep to watch
- More metrics (BLEU, ROUGE, BERTScore) add columns, not insight. LLM-judge + F1 + EM is already enough.
- Per-question dashboards sound useful but are noise at N=10. Scale N first.
- A Stage 5 / Stage 6 of more strategies without fixing (1)–(6) would make the benchmark noisier, not clearer.

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
