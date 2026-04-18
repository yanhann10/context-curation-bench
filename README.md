# HR Living Docs — Context Curation Benchmark

Stage 1 experiment comparing **Full Context stuffing** vs **Meta-Harness-inspired optimized curation** on a New Hire Onboarding Agent. Corpus = public GitLab Handbook sections + synthetic Slack threads.

## Thesis

"Just stuff the full context window" is the default assumption as windows expand. When the corpus mixes static policy docs (GitLab Handbook) with noisy fresh chat answers (Slack), does that default still win? And can a Meta-Harness-style proposer auto-discover a better curation strategy?

## Stage 1 scope (what's built)

- **Strategy A — Full Context**: concatenate every handbook section and every Slack thread into the prompt. Baseline.
- **Strategy B — Meta-Harness Optimized**: an LLM proposer iteratively mutates a typed `CurationSpec` (which docs, ordering, format, max-chars, instructions) on a train set of questions and keeps the best-scoring spec.

## Honest simplification from faithful Meta-Harness

Faithful Meta-Harness ([Stanford IRIS Lab](https://yoonholee.com/meta-harness/), [artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact)) evolves **arbitrary Python harness code** using execution traces + filesystem. For a 2hr budget we:

- replace "mutate Python code" with "mutate a typed `CurationSpec` dataclass" — same loop (propose → execute → score → keep best), safer, interpretable
- use a single proposer LLM call per iteration instead of a population-based search
- train on a subset of the eval questions (no held-out split in MVP)

What we can legitimately claim: *"inspired by Meta-Harness; applies the propose/evaluate/keep loop to a structured curation spec rather than harness code."* Not a faithful reproduction. See `notes/meta_harness_analysis.md`.

## Repo layout

```
.
├── main.py                  # Stage 1 entry point
├── src/
│   ├── data_loader.py       # load handbook/*.md + slack.json + test_questions.json
│   ├── strategies.py        # full_context + meta_harness_optimized + CurationSpec
│   ├── evaluator.py         # agent call, LLM-as-judge, CSV logging
│   └── harness_optimizer.py # propose-mutate-score loop over CurationSpec
├── data/
│   ├── handbook/            # *.md extracted from handbook.gitlab.com
│   ├── slack.json           # synthetic Slack threads
│   └── test_questions.json  # 6 Qs w/ golden answers + category tags
├── output/                  # CSV + JSON artifacts from each run
├── eval/eval_runs.md        # append-only master log across runs
├── notes/
│   └── meta_harness_analysis.md
└── prd.md
```

## Setup

```bash
cd /Users/hanyan/git_repo/context-curation-benchmark
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # then edit ANTHROPIC_API_KEY
```

**LLM backend:** Claude (Anthropic SDK). Default models — agent = `claude-sonnet-4-6`, judge / proposer = `claude-opus-4-7`, summary / router = `claude-haiku-4-5`. Override via env.

**Embeddings:** local `BAAI/bge-small-en-v1.5` via `sentence-transformers` (Claude has no embedding endpoint). FAISS `IndexFlatIP` for retrieval.

## Run

```bash
# full pipeline: optimize spec on train qs, then eval both strategies on all qs
python3 main.py

# skip the proposer loop (use baseline spec for Strategy B)
python3 main.py --skip-optimize

# tune train size / iterations
python3 main.py --train 4 --iter 3
```

Artifacts in `output/`:
- `results_stage1.csv` — per-question × per-strategy row (quality, recency, tokens, latency, cost)
- `optimizer_history.json` — every proposed spec + rationale + score
- `final_spec.json` — the winning `CurationSpec`
- `summary.json` — per-strategy aggregate means

## Metrics

| Metric | Range | Definition |
|---|---|---|
| quality | 0–1 | LLM-judge vs golden answer (strict) |
| recency | 0/1 | Did the answer reflect the recent Slack fact when the golden was recency-sensitive? |
| latency_s | float | Wall-clock seconds per agent call |
| prompt_tokens / completion_tokens | int | From OpenAI usage |
| cost_usd | float | Approximate, gpt-4o-mini pricing |

## Question categories

- `portal_only` — answer purely in the handbook, Slack doesn't touch it
- `slack_contradicts` — handbook is stale, Slack is correct (tests recency handling)
- `slack_only` — info only in Slack, not in handbook
- `needs_both` — handbook gives policy, Slack gives a current detail

## Findings (to fill after first run)

_TBD after running Stage 1._

## Sources

- GitLab Handbook — https://handbook.gitlab.com/handbook/
- Meta-Harness concept — https://yoonholee.com/meta-harness/
- Meta-Harness artifact — https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact

## Stage 2 (built — runs all 4 strategies)

```bash
python3 main_stage2.py                 # reuses output/final_spec.json from Stage 1
python3 main_stage2.py --reoptimize    # re-run the meta-harness proposer first
python3 main_stage2.py --rag-k 6 --hier-ids 5
```

Strategies compared:
- `full_context` — stuff everything (baseline)
- `meta_harness_optimized` — Stage 1 optimized `CurationSpec`
- `rag_embedding` — top-k chunks over `text-embedding-3-small`
- `hierarchical` — map (1-sentence summary per doc) → route (LLM picks ids) → expand

Each strategy lives in its own module: `src/strategies.py`, `src/strategies_rag.py`, `src/strategies_hierarchical.py`. All calls run async via `AsyncOpenAI` + `asyncio.gather` under a concurrency semaphore (default 8).

## Stage 3 / 4 (not built yet, per PRD)

- Stage 3: generate synthetic Slack-API-shaped updates with validated-more-recent facts; set original doc timestamps to 2026-01-01; benchmark token+accuracy across strategies.
- Stage 4: `ai4research` + [open-harness](https://github.com/MaxGfeller/open-harness) to auto-generate curation strategies.
