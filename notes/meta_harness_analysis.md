# Meta-Harness — Analysis & Integration Spec for Onboarding-Agent Hackathon

Sources inspected:
- Paper landing page: https://yoonholee.com/meta-harness/
- Main code repo: https://github.com/stanford-iris-lab/meta-harness
- Final-harness artifact: https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact
- Paper: arXiv 2603.28052 (Lee, Nair, Zhang, K. Lee, Khattab, Finn, 2026)

Primary reference example that maps to our use-case:
`reference_examples/text_classification/` (predict-from-text, evolve a "memory system" = context-curation module). The `terminal_bench_2/` example is agentic coding; the `tbench2-artifact` repo is only the final harness, no search code.

---

## 1. What Meta-Harness actually is

- **Unit of search = a "harness":** Python code around a *fixed* base LLM that decides "what to store, retrieve, and show." In the text-classification example it is a `MemorySystem` subclass implementing `predict(input) -> (answer, meta)`, `learn_from_batch(results)`, `get_state()/set_state()`. The base model is frozen; only this wrapper code mutates.
- **Proposer = Claude Code subprocess with filesystem access.** The outer loop literally shells out to the `claude` CLI (`claude_wrapper.run(...)`, model=`opus`, tools=`Read/Glob/Grep/Agent/Write/Edit/Bash`, plus a Skill at `.claude/skills/meta-harness/SKILL.md`). The proposer reads prior candidates' *source code + evaluation logs + scores* via grep/cat, diagnoses failures, writes a new candidate `.py` file into `agents/`, and emits `logs/<run>/pending_eval.json` listing the candidates plus `{name, axis, hypothesis, components}` metadata.
- **Scorer = run each candidate on a validation split.** `benchmark.py` imports the proposed module, runs it over N datasets (val split of ~50 items each by default), computes accuracy. A Pareto frontier is maintained in `frontier_val.json`; the test split is only touched once at the very end (the framework is paranoid about leakage — ONBOARDING.md flags this repeatedly).
- **Outer loop** (simplified from `meta_harness.py::run_evolve`):
  1. Run baselines, initialize `frontier_val.json`.
  2. For iteration i in 1..N: render task prompt → call proposer Claude → import-check candidates → run benchmark on val → update frontier + `evolution_summary.jsonl` (one JSONL row per candidate: iteration, system, avg_val, hypothesis, delta vs best).
  3. After all iters: score frontier systems on held-out test.
- **Key distinctive claim** (from the blog): the proposer gets "up to 10M tokens of diagnostic context per step" by *not* summarizing — it reads the raw filesystem of prior runs. This is the thing that is hard to faithfully reproduce without Claude Code subscription auth and a long time budget.

Paper numbers worth citing: Terminal-Bench 2.0 from 28.5% (KIRA baseline) to 46.5% in 10 iterations of search; final artifact at 76.4% (5 trials/task). Text-classification experiments used ~20 iterations × 2 candidates/iter.

---

## 2. Repo structure

### `stanford-iris-lab/meta-harness` (the search framework)
```
ONBOARDING.md              # Prompt you feed your coding assistant to spec a new domain
reference_examples/
  text_classification/
    meta_harness.py        # Outer loop (~500 lines) — THE file to read
    benchmark.py           # Sweep orchestration, frontier bookkeeping (~1000 lines)
    inner_loop.py          # Single-candidate evaluator (~900 lines)
    memory_system.py       # Abstract base class candidates must implement
    llm.py                 # OpenAI-compatible LLM wrapper
    claude_wrapper.py      # Subprocess wrapper around `claude` CLI (~700 lines)
    config.yaml            # Datasets, models, baselines, splits
    agents/                # Where proposer writes new candidate .py files
      no_memory.py, fewshot_memory.py, fewshot_all.py  # Baselines
    .claude/skills/meta-harness/SKILL.md   # Proposer's prior (how to mutate)
    logs/<run>/
      pending_eval.json             # Proposer → benchmark handoff
      frontier_val.json             # Pareto frontier
      evolution_summary.jsonl       # One row per candidate, all iterations
      claude_sessions/              # Full proposer transcripts
      reports/                      # Post-eval diagnostic reports
  terminal_bench_2/        # Same shape, for agentic coding
```

### Dependencies (text_classification example)
- Python 3.11+, `uv sync`.
- `claude` CLI installed + logged in (proposer uses *subscription* auth — the loop explicitly strips `ANTHROPIC_API_KEY` before calling it so you don't get rate-limited on the pay-per-token tier).
- An OpenAI-compatible endpoint for the *solver* model (default: OpenRouter `openai/gpt-oss-120b`; paper used local vLLM).
- NOT self-contained for our use case: pinned to MCE text-classification datasets and the memory-system interface.

### tau-bench coupling?
None in this repo. The name `tbench2-artifact` is **Terminal-Bench 2.0** (coding shell tasks), *not* τ-bench (customer-service dialog). No tau-bench code anywhere.

---

## 3. Integration difficulty assessment

**Verdict: do not attempt a faithful integration in 2 hours. Re-implement the concept.**

Concrete coupling points that would need to be replaced or adapted:

| Coupling point | What it assumes | What we'd need |
|---|---|---|
| Proposer transport | `claude` CLI + subscription auth + MCP skills dir | We don't have claude-cli-as-subprocess + Skill set up; rewriting as Anthropic SDK call is ~1hr by itself |
| Harness interface | `MemorySystem` ABC with `predict` / `learn_from_batch` / `get_state` / online-or-offline mode switch | Our harness is *one function* `curate(docs, question) -> context`. Forcing our task into their ABC is fighting the framework |
| Dataset loader | HuggingFace datasets + split caches under `data/`, dataset names hard-coded in config.yaml | Our tasks are 6-8 handwritten HR QA items — no dataset plumbing needed |
| Scoring | Classification accuracy over N datasets, Pareto over (accuracy, context_length) | We need semantic equivalence / rubric scoring over free-text answers — totally different scorer |
| Filesystem layout | `logs/<run>/evolution_summary.jsonl`, `frontier_val.json`, `pending_eval.json`, `claude_sessions/`, `reports/` — the proposer prompt hardcodes these paths | Every one of these is load-bearing for the proposer skill; changing the layout means rewriting SKILL.md |
| Proposer prior | `.claude/skills/meta-harness/SKILL.md` (not shown in the README; ~hundreds of lines of domain-specific guidance) | Would need to be re-authored for HR-QA anyway |

**Honest hour estimate for a faithful port** (someone who already has `claude` CLI working):
- Set up uv project, claude CLI auth, dataset adapter to wrap 6-8 HR Qs as a "dataset": 1.5 hr
- Build a `CurationHarness(MemorySystem)` shim adapting our `curate()` into their `predict()`: 1 hr
- Implement free-text scorer (LLM-as-judge) and wire into `benchmark.py`: 1.5 hr
- Re-author `SKILL.md` for context-curation mutations + re-point all log paths: 2 hr
- Debug first end-to-end iteration: 2+ hr (their README literally says "has not been tested beyond verifying that it runs")
- **Total: 8-12 hours minimum, plausibly 16.** Not doable in a 2-hour hackathon window.

We should re-implement the *idea* (propose → score → keep-best loop with LLM-as-proposer) in ~100 lines and explicitly cite Meta-Harness as inspiration.

---

## 4. Minimal in-house proposer spec (~100 LOC target)

### Interfaces

```python
# harness.py  — the thing we are optimizing
def curate(docs: list[Doc], question: str, params: dict) -> str:
    """Select, order, and format context for the agent.
    `params` is a dict of tunables the proposer can mutate
    (e.g. top_k, section_order, format_template, include_slack).
    Returns the final context string fed to the answering LLM."""

# agent.py  — fixed; frozen base model
def answer(question: str, context: str) -> str: ...

# eval.py
def score_task(q: str, gold: str, pred: str) -> float:
    """LLM-as-judge rubric: 0.0 | 0.5 | 1.0. Return mean over the 6-8 task set."""

def eval_harness(params: dict, tasks: list[Task], docs: list[Doc]) -> EvalResult:
    """Returns {'score': float, 'per_task': list[dict], 'traces': list[str]}."""
```

### Proposer module (the core ~100 lines)

```python
# meta_proposer.py
import json, anthropic
from pathlib import Path

RUN_DIR = Path("runs/current")
HISTORY = RUN_DIR / "history.jsonl"   # one row per evaluated candidate

BASELINE_PARAMS = {
    "top_k_docs": 5,
    "include_slack": True,
    "section_order": ["handbook", "slack"],
    "format": "markdown_headers",   # or "xml", "plain"
    "max_chars": 8000,
    "question_first": True,
}

MUTATION_AXES = [
    "top_k_docs", "include_slack", "section_order",
    "format", "max_chars", "question_first",
]

PROPOSER_SYSTEM = """You are optimizing a context-curation function for an HR
onboarding agent. You will see the full history of prior candidates: their
parameter dicts, per-task scores, and failure traces. Diagnose WHY the current
best fails on specific tasks, then propose ONE new parameter dict that tests a
concrete hypothesis. Return JSON:
{"hypothesis": "...", "axis": "one of MUTATION_AXES", "params": {...}}"""

def load_history() -> list[dict]:
    if not HISTORY.exists(): return []
    return [json.loads(l) for l in HISTORY.read_text().splitlines() if l.strip()]

def render_history_for_proposer(hist: list[dict], k: int = 5) -> str:
    # Show baseline + top-k by score + most-recent
    ranked = sorted(hist, key=lambda r: -r["score"])[:k]
    recent = hist[-3:]
    shown = {id(r): r for r in ranked + recent}.values()
    lines = []
    for r in shown:
        fails = [t for t in r["per_task"] if t["score"] < 1.0]
        lines.append(json.dumps({
            "iter": r["iter"], "score": r["score"],
            "params": r["params"], "hypothesis": r.get("hypothesis", ""),
            "failed_tasks": [{"q": t["q"][:80], "why": t["judge_note"][:200]}
                             for t in fails[:3]],
        }, indent=2))
    return "\n\n---\n\n".join(lines)

def propose(hist: list[dict], client: anthropic.Anthropic) -> dict:
    if not hist:
        return {"hypothesis": "baseline", "axis": "init", "params": BASELINE_PARAMS}
    prompt = (f"History of prior candidates (best/recent):\n\n"
              f"{render_history_for_proposer(hist)}\n\n"
              f"Mutable axes: {MUTATION_AXES}\n"
              f"Propose ONE new candidate as JSON.")
    msg = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        system=PROPOSER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(extract_json_block(msg.content[0].text))

def search_loop(tasks, docs, n_iters: int = 8):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()
    hist = load_history()
    # seed with baseline if empty
    if not hist:
        res = eval_harness(BASELINE_PARAMS, tasks, docs)
        row = {"iter": 0, "params": BASELINE_PARAMS, "hypothesis": "baseline",
               "score": res["score"], "per_task": res["per_task"]}
        HISTORY.write_text(json.dumps(row) + "\n"); hist = [row]
    best = max(hist, key=lambda r: r["score"])
    for i in range(1, n_iters + 1):
        cand = propose(hist, client)
        res = eval_harness(cand["params"], tasks, docs)
        row = {"iter": i, **cand, "score": res["score"], "per_task": res["per_task"]}
        with HISTORY.open("a") as f: f.write(json.dumps(row) + "\n")
        hist.append(row)
        if res["score"] > best["score"]:
            best = row
            print(f"iter {i}: NEW BEST {res['score']:.3f}  ({cand['hypothesis']})")
        else:
            print(f"iter {i}: {res['score']:.3f} (best {best['score']:.3f})")
    (RUN_DIR / "best.json").write_text(json.dumps(best, indent=2))
    return best
```

### Why this captures Meta-Harness's core idea faithfully
- **Mutates the harness**, not the base model (same split as the paper).
- **Proposer is an LLM that reads structured history**, including failure traces — directly mirrors their "filesystem of prior candidates" idea, scaled down to a JSONL file.
- **Scoring on held-out tasks** (here: the 6-8 HR Q set, or split into 5 search + 3 test if you want real leakage discipline).
- **Keep-best with explicit hypothesis + axis metadata** — same columns as their `evolution_summary.jsonl`.

### What we deliberately drop
- No Pareto frontier over multiple objectives (we just maximize score).
- No sandboxed code execution for candidates — we mutate a *parameter dict*, not freshly-written Python files. This is a simplification; Meta-Harness proper lets the proposer write arbitrary `MemorySystem` subclasses. Writing the restricted param-dict form saves the `validate_candidates` import-check step and removes the exec-safety concern for a 2hr build.
- No multi-dataset sweep, no multi-seed noise reduction.
- No separate proposer-Skill file — the system prompt is inline.

### Expected runtime in the hackathon
- 8 iterations × (6-8 tasks × ~1 API call each + 1 proposer call) ≈ 70-80 API calls ≈ 5-8 minutes wall-clock at Opus rates. Fits comfortably in the 2hr window with time left for demo/README.

---

## 5. Honest framing for the README

### Legitimate claims
- "Inspired by Stanford IRIS Lab's Meta-Harness (Lee et al., 2026, arXiv:2603.28052), which searches over model-harness code using an LLM proposer that reads prior candidates' traces."
- "We apply the same core loop — LLM-proposer mutates, validation-set scores, keep-best — to the problem of context curation for an onboarding agent."
- "Held-out split: we never show the proposer our test questions during search" (assuming we actually split the 6-8 tasks, e.g. 5 search / 3 test).

### What we must NOT claim
- NOT "a reproduction of Meta-Harness" — we use their idea, not their code. We do not run their `meta_harness.py`.
- NOT "we ran Meta-Harness on our domain." We did not; we re-implemented the loop from scratch in ~100 LOC.
- NOT "our proposer reads 10M tokens of diagnostic context" — we render a pruned JSONL history of top-k + recent candidates, which is far smaller.
- NOT performance-comparable claims to their paper (Terminal-Bench 2.0 76.4%) — different domain, different base model, different task count.

### Suggested README paragraph
> This project is inspired by **Meta-Harness** (Lee et al., 2026), which frames
> prompt/context engineering as search over harness code with an LLM proposer.
> We apply the same outer loop — propose → evaluate on a held-out set →
> keep-best with failure traces fed back to the proposer — to the specific
> problem of context curation for an HR onboarding agent. Our implementation is
> a ~100-line standalone module; it is not a port of their codebase and does
> not use their Claude-Code-based proposer. The harness we mutate is a
> parameter dict over retrieval top-k, section ordering, format template, and
> whether to include synthetic Slack context. Task set: 6-8 HR questions over
> static GitLab Handbook sections plus synthetic Slack threads.

---

## Appendix: load-bearing file paths (for future deeper integration)

- Outer loop reference implementation: `reference_examples/text_classification/meta_harness.py` lines 286-476 (`run_evolve`).
- Harness interface we'd need to satisfy in a real port: `reference_examples/text_classification/memory_system.py` (`MemorySystem` ABC).
- Per-candidate log row schema: `update_evolution_summary` in `meta_harness.py` lines 207-247.
- Proposer invocation (the only non-trivial dependency): `claude_wrapper.run(...)` in `meta_harness.py` lines 137-167. Requires `claude` CLI logged in with subscription auth; the loop strips `ANTHROPIC_API_KEY` before calling it.
- Onboarding prompt (useful as a checklist even when re-implementing): `ONBOARDING.md` "Required Fields" section — problem framing, harness definition, evaluation, baselines, offline/online experience, budget.
