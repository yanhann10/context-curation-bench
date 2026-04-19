# Lazy Evaluation

**Source:** https://docs.pola.rs/user-guide/lazy/using/
**Fetched:** 2026-04-18

Polars provides a lazy evaluation system that defers query execution until explicitly requested. With the lazy API, Polars doesn't run each query line-by-line but instead processes the full query end-to-end.

## Why Lazy?

1. **Query optimization** — the optimizer applies predicate/projection/slice pushdown, common subplan elimination, and more.
2. **Memory efficiency** — lazy queries can work with larger-than-memory datasets using streaming.
3. **Early schema errors** — the lazy API can catch schema errors before processing data.

## Starting Lazy from Files

Prefer `pl.scan_*` functions over `pl.read_*` when possible — scanning lets the optimizer push work down to the reader.

```python
q1 = (
    pl.scan_csv("docs/assets/data/reddit.csv")
    .with_columns(pl.col("name").str.to_uppercase())
    .filter(pl.col("comment_karma") > 0)
)
```

A `pl.scan_` function is available for CSV, IPC, Parquet, and JSON.

## Execution: `collect()`

Nothing runs until `collect()` is called.

```python
df = q1.collect()
```

For streaming execution (large data), pass `engine="streaming"`:

```python
df = q1.collect(engine="streaming")
```

## Converting Eager → Lazy

Call `.lazy()` on any DataFrame:

```python
q3 = pl.DataFrame({"foo": ["a", "b", "c"], "bar": [0, 1, 2]}).lazy()
```

This produces a `LazyFrame`, which supports the same query API but defers execution.

## Inspecting Plans

- `lf.explain()` — textual query plan (optimized by default)
- `lf.explain(optimized=False)` — logical plan before optimization
- `lf.show_graph()` — render a plan graph (requires graphviz)
- `lf.profile()` — run and return per-node timing

## Key Methods

- `scan_csv()`, `scan_parquet()`, `scan_ipc()`, `scan_ndjson()` — lazy readers
- `with_columns()` — add/modify columns
- `filter()` — row filtering
- `select()` — choose/compute columns
- `group_by().agg()` — aggregation
- `join()` — lazy-compatible joins
- `pl.col(name)` — column reference
- `lazy()` — eager DataFrame → LazyFrame
- `collect()` — materialize the result

Starting queries with file scanners rather than loading entire datasets into memory first maximizes the benefits of the optimizer.
