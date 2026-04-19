# Window Functions

**Source:** https://docs.pola.rs/user-guide/expressions/window-functions/
**Fetched:** 2026-04-18

Window functions apply aggregations over partitions within the `select` context, preserving the original row count.

## Operations Per Group — `.over()`

`.over(cols)` partitions by the given columns and evaluates the expression within each partition.

```python
result = pokemon.select(
    pl.col("Name", "Type 1"),
    pl.col("Speed").rank("dense", descending=True).over("Type 1").alias("Speed rank"),
)
```

Multiple partition columns are accepted positionally:

```python
result = pokemon.select(
    pl.col("Name", "Type 1", "Type 2"),
    pl.col("Speed")
      .rank("dense", descending=True)
      .over("Type 1", "Type 2")
      .alias("Speed rank"),
)
```

## Mapping Strategies

The `mapping_strategy` parameter controls how grouped results map back to rows.

### `group_to_rows` (default)

Results stay aligned with original row positions.

```python
result = athletes.select(
    pl.col("athlete", "rank").sort_by(pl.col("rank")).over(pl.col("country")),
    pl.col("country"),
)
```

### `explode`

Groups rows by partition, reordering them together. Faster because position tracking is skipped.

```python
result = athletes.select(
    pl.all()
      .sort_by(pl.col("rank"))
      .over(pl.col("country"), mapping_strategy="explode"),
)
```

### `join`

Aggregates results into a list and broadcasts that list to every row in the group.

```python
result = athletes.with_columns(
    pl.col("rank").sort().over(pl.col("country"), mapping_strategy="join"),
)
```

The result column is `List[i64]`, with identical lists across rows sharing the same country.

## Windowed Scalar Aggregation

When the inner expression reduces to a scalar, it broadcasts:

```python
result = pokemon.select(
    pl.col("Name", "Type 1", "Speed"),
    pl.col("Speed").mean().over(pl.col("Type 1")).alias("Mean speed in group"),
)
```

## Practical Example

Top-3 per group via `explode`:

```python
result = pokemon.sort("Type 1").select(
    pl.col("Type 1").head(3).over("Type 1", mapping_strategy="explode"),
    pl.col("Name")
      .sort_by(pl.col("Speed"), descending=True)
      .head(3)
      .over("Type 1", mapping_strategy="explode")
      .alias("fastest/group"),
    pl.col("Name")
      .sort_by(pl.col("Attack"), descending=True)
      .head(3)
      .over("Type 1", mapping_strategy="explode")
      .alias("strongest/group"),
)
```

## `group_by()` vs `.over()`

- `group_by()` reduces the output to one row per group
- `.over()` preserves original row count (subject to mapping strategy)

Choose `.over()` when you need per-group context alongside individual rows — ranking, percentile, or per-group normalization.
