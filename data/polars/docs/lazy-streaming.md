# Streaming Execution and Performance

**Source:** https://docs.pola.rs/user-guide/concepts/streaming/ and https://docs.pola.rs/user-guide/lazy/optimizations/
**Fetched:** 2026-04-18

## Streaming Engine

Polars can execute queries in a streaming fashion, processing batches rather than materializing the entire dataset in memory.

### Enabling Streaming

Pass `engine="streaming"` to `collect()`:

```python
q1 = (
    pl.scan_csv("docs/assets/data/iris.csv")
    .filter(pl.col("sepal_length") > 5)
    .group_by("species")
    .agg(pl.col("sepal_width").mean())
)
df = q1.collect(engine="streaming")
```

Not every operation has a streaming implementation; Polars automatically falls back to the in-memory engine where needed, without user intervention.

### Inspecting Streaming Plans

```python
q1.show_graph(plan_stage="physical", engine="streaming")
```

The legend shows memory intensity per node, helping locate bottlenecks.

## Lazy Query Optimizations

When you call `.collect()` on a `LazyFrame`, the optimizer transforms the plan:

### Predicate Pushdown

Filters are applied as early as possible — ideally at the scanner — to reduce the volume of parsed data. Runs once per query.

### Projection Pushdown

Only the columns needed downstream are read from the source. Runs once per query.

### Slice Pushdown

`.head(n)` / `.limit(n)` propagate back to the reader so only the needed prefix is materialized. Runs once per query.

### Common Subplan Elimination

Repeated subtrees (e.g. a scan used in two branches) are computed once and cached.

### Simplify Expressions

Iterative: constant folding, dead-code removal, cheaper-op substitution — runs to a fixed point.

### Join Ordering

Branches are reordered to minimize memory pressure based on size estimates.

### Type Coercion

Iteratively chooses the smallest numeric type that works.

### Cardinality Estimation

Used to pick between hash-based vs sort-based group-by strategies. Runs zero or more times.

## Optimization Cheat-Sheet

| Optimization | Frequency |
|---|---|
| Predicate pushdown | once |
| Projection pushdown | once |
| Slice pushdown | once |
| Common subplan elimination | once |
| Simplify expressions | to fixed point |
| Join ordering | once |
| Type coercion | to fixed point |
| Cardinality estimation | 0–n times |

## Performance Tips

1. **Start lazy** — use `scan_*` rather than `read_*` whenever you plan to filter/aggregate.
2. **Prefer expressions over UDFs** — `map_elements` is row-by-row Python; expression-native code parallelizes over columns and groups.
3. **Streaming for large data** — pass `engine="streaming"` to `collect()`, or use `sink_csv` / `sink_parquet` to avoid materialization.
4. **Inspect plans** — `lf.explain()` for text, `lf.show_graph()` for a visual DAG, `lf.profile()` for per-node timing.
5. **Use the right dtype** — `Categorical` / `Enum` for low-cardinality strings, `UInt32` over `Int64` when values fit.

## Sink APIs (streaming writes)

- `lf.sink_csv(path)`
- `lf.sink_parquet(path)`
- `lf.sink_ipc(path)`
- `lf.sink_ndjson(path)`

These execute the query incrementally and write output chunk-by-chunk, bypassing the full in-memory materialization that `collect()` + `write_*` would require.
