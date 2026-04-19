# HR Living Docs — Context Curation Benchmark

Stage 1 experiment comparing **Full Context stuffing** vs **Meta-Harness-inspired optimized curation** on a New Hire Onboarding Agent. Corpus = public GitLab Handbook sections + synthetic Slack threads.

## `ccbench` — the barebones bench layer

Shape borrowed from [letta-evals](https://github.com/letta-ai/letta-evals) (YAML suite → JSONL data → decorator registry → runner CLI). Four twists that are novel to context curation:

1. **`strategies:` is a list** — a suite IS a matrix, not a single `target:`.
2. **`CorpusSpec` is first-class**, separate from the dataset. Docs carry `kind` (static|fresh), `timestamp`, `freshness_priority`. Questions reference corpus slices by name.
3. **`frontier:` replaces `gate:`** — output is the Pareto-non-dominated set over `(quality, cost, tokens)` plus per-axis winners, instead of a boolean threshold.
4. **`optimize:` is a built-in phase** — propose → evaluate → keep-best on a typed `StrategySpec` runs before final scoring.

```
ccbench/
├── cli.py              # python -m ccbench run|validate|list-strategies
├── registry.py         # @strategy / @grader / @corpus_loader decorators
├── spec.py             # YAML → SuiteSpec
├── corpus.py           # CorpusSpec, Doc (kind/timestamp/freshness_priority)
├── dataset.py          # Question
├── runner.py           # async matrix + per-category summary
├── judge.py            # llm_judge grader
├── frontier.py         # Pareto report
├── optimizer.py        # built-in propose/eval/keep loop
└── strategies/         # full_context, rag_embedding, hierarchical, agent_managed, meta_harness
suites/hr_living_docs.yaml
data/corpus.jsonl, questions.jsonl
```

**Run:**
```bash
.venv/bin/python -m ccbench.convert_data      # one-shot: legacy → JSONL
.venv/bin/python -m ccbench validate suites/hr_living_docs.yaml
.venv/bin/python -m ccbench run      suites/hr_living_docs.yaml
```

Artifacts: `output/{suite}_matrix.csv`, `{suite}_summary.json`, `{suite}_frontier.json`, `{suite}_optimizer_history.json`.

**What the old `main.py` / `main_stage2.py` / `main_stage3.py` scripts still do:** they hard-code strategies and print specific tables. `ccbench` makes the same thing a declarative suite. The existing `src/` code is re-used as strategy adapters — no rewrite.

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

## Findings (Stage 3, 7 strategies, Claude Sonnet 4.6 throughout)

N=10 v2 HR onboarding questions (4 slack_contradicts, 2 slack_only, 2 needs_both, 2 portal_only). Corpus: 11 handbook docs (timestamped 2026-01-01) + 10 Slack-API-shape threads (HR-validated, recent). Full eval log in `eval/eval_runs.md`.

| strategy | quality | f1 | latency_s | prompt_tok | cost_usd |
|---|---|---|---|---|---|
| full_context | 0.995 | 0.534 | 6.6 | 19,957 | 0.670 |
| meta_harness_optimized | 0.890 | 0.467 | 7.5 | 11,863 | 0.431 |
| rag_embedding | 0.925 | 0.455 | 6.7 | 2,161 | **0.141** |
| hierarchical | 0.910 | 0.491 | 6.1 | **1,489** | **0.118** |
| agent_managed | 0.990 | 0.524 | 8.9 | 7,739 | 0.320 |
| cascade_router | 0.925 | 0.546 | 23.5 | 24,522 | 0.904 |
| **ensemble** | **0.995** | 0.527 | 11.3 | 9,817 | 0.428 |

**Oracle router** (pick cheapest max-quality per question): **1.000 quality at $0.138** — 3× cheaper than ensemble, 5× cheaper than full_context. Picks hierarchical 9/10, agent_managed 1/10.

Charts: `output/chart_stage3.png`, `output/chart_stage3_heatmap.png`.

### Headlines
- **Ensemble matches full_context quality at 64% the cost** — best demonstrated strategy at this model class.
- **Cascade routing is WORSE than its tier-2 alone** (0.925 at $0.90 vs agent_managed 0.990 at $0.32). LLM self-verification is over-confident on confidently-wrong tier-1 outputs.
- **Oracle-vs-ensemble gap is $0.29 / 10q** — a learned router or cross-model verifier that beats self-verification is the highest-leverage improvement.

### Per-strategy failure modes

- **full_context**: 0.995 — one 0.95 on q-v2-007 (needs_both); 2× the cost of agent_managed.
- **meta_harness_optimized**: drops q-v2-009 (portal_only STD benefits → **0.00**). Optimizer spec excluded `us-benefits-overview`. Train-set overfit is recurrent.
- **rag_embedding / hierarchical**: fail q-v2-010 (military leave: RAG 0.30, hier 0.10). Neither retrieves `parental-and-other-leave.md`.
- **agent_managed**: 0.990, 0.90 on q-v2-007 only.
- **cascade_router**: 0.30 on q-v2-010. **Self-verifier failure mode:** hier returned confidently-wrong, verifier said `confident: 1`, never escalated. Also pays all 3 tiers on ~8/10 questions because verifier over-eagerly fires on hedging/missing citations.
- **ensemble**: 0.95 on q-v2-007 — judge picked hier's answer when agent_managed's was also ~0.95; not a real failure.

### When to pick what

- **Max demonstrated quality** → `ensemble` (0.995 at $0.428)
- **Best single-strategy quality/cost** → `agent_managed` (0.990 at $0.320)
- **Cheapest with 1 catastrophic failure tolerance** → `hierarchical` ($0.118, but fails q-v2-010)
- **Avoid**: `cascade_router` as implemented — single-model self-verification defeats the purpose. Fix with a cross-model verifier.
- **Theoretical ceiling**: oracle router ($0.138, 1.000) — implementable with a learned router or cross-model verifier

Recency-handling: all strategies correctly prefer the recent Slack value on `slack_contradicts` questions. Recency is table stakes at Sonnet 4.6 and was dropped as a separate metric.

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
- `cascade_router` — Tier 1 `hierarchical` → self-verifier (`{"confident": 0|1}`) → if 0, Tier 2 `agent_managed` → verifier again → if 0, Tier 3 `full_context`. Tokens summed across all tiers. **Finding: self-verification is the weak link** — see Findings below.
- `ensemble` — Runs `hierarchical` and `agent_managed` **in parallel** per question; judge-LLM picks A or B on correctness + specificity. Tokens additive.

Each strategy lives in its own module: `src/strategies.py` (full + meta-harness), `src/strategies_rag.py`, `src/strategies_hierarchical.py`, `src/strategies_agent_managed.py`, `src/strategies_cascade.py`, `src/strategies_ensemble.py`. All calls run async via `AsyncAnthropic` + `asyncio.gather` with staggered phases for rate-limit hygiene (5 base strategies concurrent → cascade → ensemble).

## Stage 3 / 4 (not built yet, per PRD)

- Stage 3: generate synthetic Slack-API-shaped updates with validated-more-recent facts; set original doc timestamps to 2026-01-01; benchmark token+accuracy across strategies.
- Stage 4: `ai4research` + [open-harness](https://github.com/MaxGfeller/open-harness) to auto-generate curation strategies.
