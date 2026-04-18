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
- `results_stage1.csv` — per-question × per-strategy row (quality, f1, EM, tokens, latency, cost)
- `optimizer_history.json` — every proposed spec + rationale + score
- `final_spec.json` — the winning `CurationSpec`
- `summary.json` — per-strategy aggregate means

## Metrics

| Metric | Range | Definition |
|---|---|---|
| quality | 0–1 | LLM-judge vs golden answer (recency-sensitive goldens penalized if agent returns stale handbook value) |
| f1 | 0–1 | SQuAD-style token F1 vs golden |
| exact_match | 0/1 | Normalized EM vs golden |
| key_fact_recall | 0–1 | Fraction of key_facts whose normalized form appears in answer |
| latency_s | float | Wall-clock seconds per agent call |
| prompt_tokens / completion_tokens | int | From Anthropic usage |
| cost_usd | float | Per-model priced, sum of agent + judge calls |

**Note:** a separate `recency` metric was tracked in Stage 1/2 but dropped in Stage 3 — all strategies hit `recency=1.0` at Sonnet 4.6 level, so it was table stakes. Recency handling is now rolled into `quality`: the judge penalizes stale answers on recency-sensitive questions.

## Question categories

- `portal_only` — answer purely in the handbook, Slack doesn't touch it
- `slack_contradicts` — handbook is stale, Slack is correct (tests recency handling)
- `slack_only` — info only in Slack, not in handbook
- `needs_both` — handbook gives policy, Slack gives a current detail

## Findings (Stage 3, 5 strategies, Claude Sonnet 4.6 throughout)

N=10 v2 HR onboarding questions (4 slack_contradicts, 2 slack_only, 2 needs_both, 2 portal_only). Corpus: 11 handbook docs (timestamped 2026-01-01) + 10 Slack-API-shape threads (HR-validated, recent). Full eval log in `eval/eval_runs.md`.

| strategy | quality | f1 | latency_s | prompt_tok | cost_usd |
|---|---|---|---|---|---|
| full_context | **1.000** | 0.532 | 6.2 | 19,957 | 0.667 |
| meta_harness_optimized | 0.895 | 0.455 | 7.7 | 11,863 | 0.432 |
| rag_embedding | 0.925 | 0.464 | 6.8 | 2,161 | **0.143** |
| hierarchical | 0.915 | 0.501 | 6.1 | **1,489** | **0.116** |
| **agent_managed** | **0.995** | 0.537 | 9.7 | 7,738 | 0.318 |

**Headline:** **agent_managed matches full-context quality at half the cost** — best point on the quality/cost frontier on the harder v2 eval.

Charts: `output/chart_stage3.png`, `output/chart_stage3_heatmap.png`.

### Per-strategy failure modes

- **full_context**: 1.000 — no failures. Costs 2× agent-managed.
- **meta_harness_optimized**: drops q-v2-009 (portal_only STD benefits → **0.00**). The optimizer's spec excluded `us-benefits-overview` — classic overfit to the train subset.
- **rag_embedding / hierarchical**: both fail q-v2-010 (portal_only military leave reinstatement: RAG 0.30, hier 0.20). Neither retrieved the `parental-and-other-leave` doc. Shallow retrieval/summarization doesn't know what it doesn't know.
- **agent_managed**: 0.995, single 0.95 on q-v2-007 (needs_both contractor onboarding). Tool-use loop is a clean win.

### When to pick what

- **Max quality, no tuning budget** → `full_context` (still 1.0 at Sonnet 4.6 level)
- **Best quality/cost** → `agent_managed` (tool-use, 99.5% quality at 48% the cost)
- **Cheapest acceptable** → `hierarchical` or `rag_embedding` (91-93% quality at 17-22% the cost), but expect 1-2 catastrophic failures on portal-only questions
- **Avoid**: `meta_harness_optimized` on a small eval — the optimizer's doc-inclusion mutations can strand a doc that matters for a future question

Recency-handling: all 5 strategies correctly prefer the recent Slack value on `slack_contradicts` questions. Recency is table stakes at Sonnet 4.6 and was dropped as a separate metric.

**Detail:**
- **Meta-harness wins on quality by +3.5%**, but marginal on tokens. The proposer's keeper mutations: `max_chars_per_doc 3000→6000` (ensures full us-benefits policy fits), `ordering=slack_first`, `format=structured`.
- **Hardest question: q-004 (needs_both).** Meta-harness holds 0.95; full_context and RAG drop to 0.80. The explicit policy+recent-detail combination rewards curation that keeps BOTH sources.
- **Hierarchical failure mode on q-002:** the router dropped the contradicting Slack thread, answer went stale (quality 0.80). Summarize-route-expand loses recency when summaries undersell time-sensitive threads.
- **F1 is higher for RAG/hierarchical** (0.44) than full_context (0.40) — shorter retrieved chunks keep the answer closer to the terse golden.

**When to pick what:**
- Cost-sensitive, policy-heavy domain → **RAG** (1,957 avg tokens vs 18,583)
- Max quality, 6-12 question budget to optimize → **meta_harness_optimized**
- Default without engineering effort → **full_context** still fine at Sonnet 4.6 level

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
- `full_context` — stuff all handbook + Slack into every prompt. No selection.
- `meta_harness_optimized` — apply a typed `CurationSpec` (which ids to include, ordering, format, max-chars, instructions) that an LLM proposer iteratively mutated against failure traces on a train subset.
- `rag_embedding` — chunk docs (~1200 chars, 200 overlap), embed via local `BAAI/bge-small-en-v1.5`, index in FAISS (`IndexFlatIP` on L2-normalized vectors = cosine), retrieve top-k per question. Classic RAG.
- `hierarchical` — **no embedding retrieval.** Two LLM passes: (1) *map* — summarize each doc to 1–2 sentences once, cache; (2) *route* — LLM sees question + catalog of `(id, title, timestamp, summary)` and returns JSON `{"doc_ids": [...]}` with 2–5 picks; (3) *expand* — the full text of the selected docs goes to the answerer. Trades retrieval speed for LLM reasoning over summaries.
- `agent_managed` — tool-use loop. The model is handed four tools (`list_handbook`, `get_handbook(doc_id)`, `list_slack`, `get_slack(thread_id)`) and a system prompt describing the corpus split (stale handbook dated 2026-01-01 vs recent HR-validated Slack). It runs up to 6 turns: typically `list_handbook` + `list_slack` first (sees titles + timestamps), then 1–3 `get_*` calls for the docs it judged relevant, then emits a final answer. Token usage is summed across **all** turns, so the reported cost reflects full loop spend.

Each strategy lives in its own module: `src/strategies.py` (full + meta-harness), `src/strategies_rag.py`, `src/strategies_hierarchical.py`, `src/strategies_agent_managed.py`. All calls run async via `AsyncAnthropic` + `asyncio.gather` under a concurrency semaphore (default 6).

## Stage 3 / 4 (not built yet, per PRD)

- Stage 3: generate synthetic Slack-API-shaped updates with validated-more-recent facts; set original doc timestamps to 2026-01-01; benchmark token+accuracy across strategies.
- Stage 4: `ai4research` + [open-harness](https://github.com/MaxGfeller/open-harness) to auto-generate curation strategies.
