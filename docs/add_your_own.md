# Add your own strategy, corpus loader, or grader

ccbench is a decorator-registry. Anything you decorate becomes usable as a
`name:` in a suite YAML. Three extension points, each ~10 lines.

## 1. Add a strategy

A strategy is an async function `(ctx, question, corpus, **params) -> str | dict`.

- Return a **`str`** for the common case: a single prompt. The runner handles
  the agent call, judging, token accounting, and cost.
- Return a **`dict`** (`{"answer", "prompt_tokens", "completion_tokens", "latency_s"}`)
  when your strategy runs its own tool-use loop (see `agent_managed`) and you
  want to report aggregated tokens across turns.

```python
# ccbench/strategies/keyword_filter.py
from ccbench.registry import strategy

@strategy("keyword_filter")
async def keyword_filter(ctx, question, corpus, terms=None):
    """Trivial baseline: include only docs whose title matches any keyword."""
    terms = terms or [w for w in question.input.lower().split() if len(w) > 4]
    picks = [d for d in corpus.docs if any(t in d.title.lower() for t in terms)]
    blob = "\n\n---\n\n".join(f"# {d.title}\n\n{d.content}" for d in picks)
    return f"Context:\n{blob}\n\nQuestion: {question.input}\n\nAnswer concisely."
```

Make sure it's imported somewhere the CLI loads (e.g. from `ccbench/strategies/__init__.py`
or added to the `from . import strategies` line in `ccbench/cli.py`). Then:

```yaml
strategies:
  - name: keyword_filter
    params: {terms: ["pto", "leave", "holiday"]}
```

## 2. Add a corpus loader

A corpus loader takes a path and returns a `CorpusSpec`. The bundled `jsonl`
loader is the reference. Use this if your docs live in a DB, a different file
format, or a remote index.

```python
# ccbench/corpus_loaders/markdown_dir.py
from pathlib import Path
from ccbench.registry import corpus_loader
from ccbench.corpus import CorpusSpec, Doc

@corpus_loader("markdown_dir")
def load_markdown_dir(path: str) -> CorpusSpec:
    docs = []
    for p in sorted(Path(path).glob("*.md")):
        docs.append(Doc(
            id=p.stem,
            kind="static",
            content=p.read_text(encoding="utf-8"),
            title=p.stem.replace("-", " ").title(),
            source="local",
        ))
    return CorpusSpec(docs=docs, slices={"handbook": [d.id for d in docs]})
```

Then in the suite:

```yaml
corpus:
  loader: markdown_dir
  path: data/handbook/
```

## 3. Add a grader

A grader is `(ctx, question, answer) -> dict` with at minimum a `"quality"`
key (0..1). The bundled `llm_judge` calls Claude; you can swap in SQuAD-style
token F1, an ensemble judge, or a human-in-the-loop queue.

```python
# ccbench/graders/contains_key_facts.py
from ccbench.registry import grader

@grader("contains_key_facts")
async def contains_key_facts(ctx, question, answer):
    lo = answer.lower()
    hits = sum(1 for fact in question.key_facts if fact.lower() in lo)
    denom = max(1, len(question.key_facts))
    return {"quality": hits / denom, "note": f"{hits}/{denom} key_facts present"}
```

```yaml
grader:
  kind: contains_key_facts
```

## 4. Verify

```bash
python -m ccbench list-strategies
python -m ccbench list-graders
python -m ccbench list-corpus-loaders
python -m ccbench validate path/to/your/suite.yaml
python -m ccbench run      path/to/your/suite.yaml
```

## Where existing extensions live

- `ccbench/strategies/` — `full_context`, `rag_embedding`, `hierarchical`,
  `agent_managed`, `cascade`, `ensemble`, `meta_harness`.
- `ccbench/corpus.py` — `jsonl` loader.
- `ccbench/judge.py` — `llm_judge` grader.

Read any of them as a template before writing your own.
