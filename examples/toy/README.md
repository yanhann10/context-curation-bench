# toy-coffee-budget

A minimal 3-doc / 2-question suite. Useful for:

- eyeballing the JSONL + YAML schema before authoring a real corpus
- a fast smoke-test of the runner (~30s, small token spend)
- understanding what a `slack_contradicts` question looks like vs `portal_only`

## Corpus

| id | kind | timestamp | notes |
|---|---|---|---|
| `policy/coffee-budget` | static | 2026-01-01 | says $30/month — **stale** |
| `policy/snack-budget` | static | 2026-01-01 | says $50/month — still correct |
| `slack/coffee-update-2026-03` | fresh | 2026-03-15 | HR-validated bump to $45/month |

## Questions

- `toy-001` (`slack_contradicts`) — correct answer requires trusting the fresh Slack value over the stale handbook.
- `toy-002` (`portal_only`) — Slack is noise for this one; the handbook answer stands.

## Run

```bash
.venv/bin/python -m xcbench validate examples/toy/suite.yaml
.venv/bin/python -m xcbench run      examples/toy/suite.yaml
```

Artifacts land in `output/toy-coffee-budget_{matrix.csv,summary.json,frontier.json}`.
