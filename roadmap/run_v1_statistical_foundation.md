# Run v1 — Statistical Foundation (no human judge labels)

**Scheduled:** next available overnight on the existing AWS EC2 Bedrock host
**Goal:** produce the first xcbench result where strategy-vs-strategy deltas survive a multi-seed, multi-judge, bootstrap-CI treatment. Pareto-front claims become defensible at this level.
**Out of scope:** human judge calibration, new baselines (Halo/LATTICE/FABLE/CRUX), retrieval diagnostics (recall@k/α-nDCG/coverage). Those stay on `roadmap.md`.

---

## Scope (budget-capped)

| Dimension | Value | Why this, not more |
|---|---|---|
| Domains | HR policy only | Most mature suite, portability bug already fixed, lowest risk of wasting spend on a bad suite |
| N (questions) | 100 (expand 10 → 100) | Shrinks per-cell resolution from 0.10 to 0.01. The one number that most kills the reviewer's #1 objection |
| Strategies | all 9 | No reason to drop any — marginal cost is small vs judge cost |
| Agent seeds | 3 (temp=0.3, seed ∈ {1,2,3}) | Minimum for meaningful variance estimate; fourth seed doesn't pay for itself |
| Judges | 3, cross-family (Opus 4.7 + Haiku 4.5 + Sonnet 4.6) | Gives inter-judge κ without humans. Sonnet 4.6 as agent-judge is forbidden by self-preference; use Sonnet-4.5-Bedrock for third judge if cross-family rule requires |
| Backend | AWS EC2 + Bedrock (same host as N=108 run) | Proven; `qmd://h_wiki/reference_aws_vm` |

**Deliberate omissions (to cap cost):**
- Polars and Flask domains — defer to v2 after v1's method is validated on HR.
- Corpus-factor ablations — those belong in a separate ablation run, not the statistical-foundation run.
- Category rebalancing — keep the current 40% `slack_contradicts` mix to preserve comparability with prior N=10 and N=108 results.

## Compute & cost budget

- Cells: 9 strategies × 100 questions × 3 seeds = **2,700 agent calls**
- Judge calls: 2,700 × 3 judges = **8,100 judge calls**
- Prior N=108 × 4-strategy × 1-seed × 1-judge cost $17 on this host per `ccbench-n108-bedrock-2026-04-18.md` (864 calls ≈ $0.02/call)
- Projected spend: **~$150–$300** depending on Opus share in the judge mix
- Wall-clock: prior run was 90 min for 756 cells at concurrency 6. This is ~14× → ~**8–10 h at concurrency 12**. One overnight.

**Hard cost cap: $400**, enforced by `src/cost_cap.py`. Abort and ship what's collected if exceeded.

## Prereq code work (must land before kickoff)

These are small-to-medium changes; each one is a standalone commit.

1. **Multi-seed support in runner.** `SuiteSpec` gains `seeds: int = 1`. Runner loops outer over seed index, passes a per-seed sampling param and increments the agent temperature from 0 to `seed_temperature` (default 0.3) when seeds > 1. Records `seed` in `CellResult`.
2. **Multi-judge mode in grader.** `GraderCfg` gains `judges: list[str]` (model ids) overriding `model`. Runner fans out each cell to all judges, emits `quality_by_judge: dict[str, float]`, `quality_mean`, `quality_disagreement_std`.
3. **Stats post-processing script.** `scripts/stats_pass.py` reads `{suite}_matrix.csv` and emits `{suite}_stats.json`: per-strategy mean + 95% bootstrap CI, pairwise permutation-test p-values, inter-judge Cohen's κ per pair, judge-level mean deltas.
4. **Question expansion.** Run `xcbench.expand_questions` seed=10 → 100 on HR. Manually review a 20-question sample for (a) category balance, (b) no duplicates of seed phrasing, (c) relevance to corpus. Commit expanded `data/questions_v1.jsonl`.

Prereq 4 (expansion) is a ~$5 one-off API call plus a human review pass. Prereqs 1–3 are code-only, no API cost.

## Run script (after prereqs land)

```bash
# on AWS EC2 Bedrock host
cd ~/git_repo/context-curation-bench
git pull
.venv/bin/python -m xcbench expand-questions \
  --seed data/questions.jsonl --n 90 --out data/questions_v1.jsonl

# human-review step: eyeball 20 sampled questions, reject any with leaked golden

.venv/bin/python -m xcbench run suites/sample_data_hr_policy_v1.yaml \
  --seeds 3 \
  --judges claude-opus-4-7,claude-haiku-4-5,anthropic.claude-sonnet-4-5-bedrock \
  --output output/run_v1_hr

.venv/bin/python scripts/stats_pass.py output/run_v1_hr/sample_data_hr_policy_matrix.csv
```

`suites/sample_data_hr_policy_v1.yaml` points at `data/questions_v1.jsonl` and sets `seeds: 3`, otherwise identical to the legacy suite.

## Artifacts produced

- `output/run_v1_hr/sample_data_hr_policy_matrix.csv` — 2,700 rows with per-seed + per-judge detail
- `output/run_v1_hr/sample_data_hr_policy_summary.json` — per-strategy aggregate with seed variance
- `output/run_v1_hr/sample_data_hr_policy_frontier.json` — Pareto front with CI bands
- `output/run_v1_hr/sample_data_hr_policy_stats.json` — bootstrap CIs, pairwise p-values, inter-judge κ
- `output/run_v1_hr/sample_data_hr_policy_runmeta.json` — system spec, git sha, models, seeds, backend (already wired)

## What v1 settles

- **Whether current rankings are noise.** At N=100 × 3 seeds, the ensemble-vs-full_context delta (0.005 at N=10) either becomes significant or collapses. Either result is valuable.
- **Whether judges agree.** Cross-family κ < 0.6 means the LLM-judge metric is a weak oracle and every xcbench claim gets an asterisk until humans are in the loop. κ > 0.8 means the judge is reliable enough to ship numbers on.
- **Whether the oracle-router gap is real.** At scale, the oracle-vs-best-real gap either compresses (showing the router idea is low-leverage) or holds (showing it's the biggest practical lever).
- **A reproducible template.** v2 reruns the same protocol on Polars + Flask with no extra design work.

## What v1 still doesn't settle (stays in `roadmap.md`)

- Judge-vs-human calibration (requires humans).
- Faithfulness / grounding / citation metrics.
- Retrieval-level diagnostics (recall@k, α-nDCG, CRUX coverage).
- Comparison to Halo / LATTICE / FABLE / CRUX / RAGPerf / QAMR / CirrusBench.
- Amortized vs non-amortized cost accounting.
- TTFT / TPOT separation.

## Kill criteria (abort the run)

- Cost cap trip ($400 spent).
- Inter-judge κ on the first 30 completed questions falls below 0.4 — the 3-judge design is broken; stop and rework judge prompts before burning the remaining budget.
- Any seed produces a whole-strategy zero (e.g., `agent_managed = 0.0` on every HR question in seed 2) — portability regression, stop and fix.

## After the run

- Update README "Findings" with CI-banded numbers, replacing the current single-seed N=10 table.
- Promote the stats pipeline into the default `xcbench run` output (no separate script).
- If κ > 0.8, close the judge-reliability roadmap item as "good enough for ranking claims; still needs human calibration for absolute-quality claims." If κ < 0.6, keep it open and flag publicly that xcbench numbers are directional only.
- Write v2 plan for Polars + Flask using the same protocol.
