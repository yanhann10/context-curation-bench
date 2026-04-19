# Group By and Aggregation

**Source:** https://docs.pola.rs/user-guide/expressions/aggregation/
**Fetched:** 2026-04-18

The Polars `group_by` context enables applying expressions to subsets of data based on unique column values. Use `group_by(...).agg(...)` for aggregations.

## Basic Aggregations

List any number of expressions inside `agg()`:

```python
q = (
    dataset.lazy()
    .group_by("first_name")
    .agg(
        pl.len(),
        pl.col("gender"),
        pl.first("last_name"),
    )
    .sort("len", descending=True)
    .limit(5)
)

df = q.collect()
print(df)
```

Common aggregation helpers:

- `pl.len()` — count rows in each group (row count aggregation)
- `pl.col("column")` — collect values into a list
- `pl.first("column")`, `pl.last("column")` — positional retrieval
- `.mean()`, `.sum()`, `.min()`, `.max()`, `.median()`, `.std()`, `.var()`
- `.n_unique()`, `.count()` (note: `.count()` excludes nulls)

## Conditionals in Aggregations

Filter-and-count inside `agg()` without pre-filtering:

```python
q = (
    dataset.lazy()
    .group_by("state")
    .agg(
        (pl.col("party") == "Anti-Administration").sum().alias("anti"),
        (pl.col("party") == "Pro-Administration").sum().alias("pro"),
    )
    .sort("pro", descending=True)
    .limit(5)
)
```

## Filtering Within Groups

Apply filters to specific aggregations while preserving other rows:

```python
def compute_age():
    return date.today().year - pl.col("birthday").dt.year()

def avg_age(gender: str) -> pl.Expr:
    return (
        compute_age()
        .filter(pl.col("gender") == gender)
        .mean()
        .alias(f"avg {gender} age")
    )

q = (
    dataset.lazy()
    .group_by("state")
    .agg(
        avg_age("M"),
        avg_age("F"),
        (pl.col("gender") == "M").sum().alias("# male"),
        (pl.col("gender") == "F").sum().alias("# female"),
    )
    .limit(5)
)
```

## Nested Grouping

Group by multiple columns:

```python
q = (
    dataset.lazy()
    .group_by("state", "party")
    .agg(pl.len().alias("count"))
    .sort("count", descending=True)
    .limit(5)
)
```

```python
q = (
    dataset.lazy()
    .group_by("state", "gender")
    .agg(
        compute_age().mean().alias("avg age"),
        pl.len().alias("#"),
    )
)
```

## Sorting in Group-By Context

Sort before grouping to control `.first()` / `.last()`:

```python
def get_name() -> pl.Expr:
    return pl.col("first_name") + pl.lit(" ") + pl.col("last_name")

q = (
    dataset.lazy()
    .sort("birthday", descending=True)
    .group_by("state")
    .agg(
        get_name().first().alias("youngest"),
        get_name().last().alias("oldest"),
        get_name().sort().first().alias("alphabetical_first"),
        pl.col("gender").sort_by(get_name()).first(),
    )
    .sort("state")
)
```

## Performance Considerations

Avoid `lambda` / custom Python functions inside parallel aggregation phases when possible — Python is slower than Rust and the GIL limits parallelism. Prefer native expressions. Reserve UDFs (`map_elements`, `map_batches`) for operations the expression API cannot express.

## Key Method Summary

- `group_by(columns)` — start a group-by context
- `agg(expressions)` — apply aggregations
- `sort()`, `sort_by()` — order
- `limit()` — restrict rows
- `filter()` — conditional selection inside agg
- `first()`, `last()`, `sum()`, `mean()`, `len()`, `n_unique()`
