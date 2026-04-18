# Eval Runs — Master Log

Append-only record of every end-to-end run. One entry per `python main.py` invocation.
Entry template below. Add newest on top.

---

### 2026-04-18T22:58Z — 51a44de — stage 2 (all 4 strategies)

- host: aws-micro (Ubuntu 24.04, 1 CPU, 3.7GB RAM)
- models: all roles = claude-sonnet-4-6
- strategies: full_context, meta_harness_optimized, rag_embedding, hierarchical
- questions: N=6 (2 portal_only, 2 slack_contradicts, 1 slack_only, 1 needs_both)
- optimizer: reused output/final_spec.json from stage 1 (no re-optimize)
- final spec: static=11, slack=6, ordering=slack_first, format=structured, max_chars/doc=6000
- summary:
  | strategy | quality | recency | f1 | latency_s | prompt_tok | cost_usd |
  |---|---|---|---|---|---|---|
  | full_context | 0.950 | 1.00 | 0.396 | 7.5 | 18,583 | 0.384 |
  | meta_harness_optimized | 0.975 | 1.00 | 0.404 | 9.7 | 17,869 | 0.378 |
  | rag_embedding | 0.942 | 1.00 | 0.444 | 6.3 | 1,957 | 0.080 |
  | hierarchical | 0.925 | 1.00 | 0.448 | 6.3 | 1,622 | 0.074 |
- artifacts: output/results_stage2.csv, output/summary_stage2.json
- notes: RAG hits 97% of full-context quality at 1/5 the cost — dominant tradeoff. Meta-harness best on quality (+3.5% over full) but marginal token savings. All strategies recency=1.0 — Sonnet 4.6 handles staleness when recent source is in context. Hierarchical failed q-002 (slack_contradicts → 0.80) because router dropped the Slack thread; real failure mode for summarize-route-expand. Meta-harness won only the needs_both case outright (q-004: 0.95 vs 0.80 for full/RAG).

### 2026-04-18T22:49Z — fbdc654 — stage 1 (full vs meta-harness)

- host: laptop (macOS, Python 3.13)
- models: all roles = claude-sonnet-4-6
- strategies: full_context, meta_harness_optimized
- questions: N=6
- optimizer: n_iter=3, train_n=4, kept_improvements=2
- optimizer trajectory: baseline 0.662 → iter1 0.950 (KEEP: max_chars 3000→6000) → iter2 1.000 (KEEP: ordering=slack_first, format=structured) → iter3 1.000 (reject)
- summary:
  | strategy | quality | recency | f1 | latency_s | prompt_tok | cost_usd |
  |---|---|---|---|---|---|---|
  | full_context | 0.942 | 1.00 | 0.408 | 7.8 | 18,583 | 0.386 |
  | meta_harness_optimized | 0.975 | 1.00 | 0.417 | 10.1 | 17,869 | 0.379 |
- artifacts: output/results_stage1.csv, output/final_spec.json, output/optimizer_history.json, output/summary.json
- notes: first successful Claude run after two SDK compat fixes (system=None rejected; assistant prefill rejected by Sonnet 4.6). Optimizer converged fast on this small eval; train score jumped 0.662→0.950 after raising max_chars_per_doc to fit us-benefits-overview in full. Meta-harness edge on eval (0.975 vs 0.942) is real but small.

---

## Template

```
### <UTC timestamp>  —  <git sha>  —  <stage>

- host: <laptop|aws-micro>
- models: agent=<model>, judge=<model>, proposer=<model>
- strategies: <list>
- questions: N=<n>, by_category=<breakdown>
- optimizer: iter=<n>, train_n=<n>, kept_improvements=<n>
- summary:
  | strategy | quality | recency | latency_s | prompt_tok | cost_usd |
  |---|---|---|---|---|---|
  | ... | ... | ... | ... | ... | ... |
- artifacts: output/results_stage1.csv, output/final_spec.json, output/optimizer_history.json
- notes: <one-paragraph human-readable observation>
```

---
