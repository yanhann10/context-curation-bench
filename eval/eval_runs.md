# Eval Runs — Master Log

Append-only record of every end-to-end run. One entry per `python main.py` invocation.
Entry template below. Add newest on top.

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
