# Joins

**Source:** https://docs.pola.rs/user-guide/transformations/joins/
**Fetched:** 2026-04-18

A join combines columns from one or more DataFrames. Polars supports three categories:

- **Equi joins** — match by key equality
- **Non-equi joins** — match by arbitrary predicate
- **Asof joins** — match by nearest key (time-series)

## Quick Reference

| Type | Function | Description |
|---|---|---|
| Inner | `join(..., how="inner")` | rows matched on both sides |
| Left | `join(..., how="left")` | all left rows + matches |
| Right | `join(..., how="right")` | all right rows + matches |
| Full | `join(..., how="full")` | all rows from both sides |
| Semi | `join(..., how="semi")` | left rows with a right match |
| Anti | `join(..., how="anti")` | left rows without a right match |
| Non-equi | `join_where(...)` | custom predicate |
| Asof | `join_asof(...)` | nearest-key match |
| Cartesian | `join(..., how="cross")` | all pairings |

## Equi Joins

```python
result = df1.join(df2, on="column_name")
```

Different column names or expressions on each side:

```python
result = df1.join(
    df2,
    left_on="property_name",
    right_on=pl.col("name").str.to_lowercase()
)
```

### Inner (default)

The resulting DataFrame only contains the rows from the left and right DataFrames that matched.

```python
result = df1.join(df2, on="property_name", how="inner")
```

### Left

All rows from left; non-matching right columns are `null`.

```python
result = df1.join(df2, on="property_name", how="left")
```

### Right

`df1.join(df2, how="right")` is equivalent to `df2.join(df1, how="left")`.

### Full

All rows from both sides; unmatched cells filled with `null`. Use `coalesce=True` to merge duplicated key columns.

```python
result = df1.join(df2, on="property_name", how="full", coalesce=True)
```

### Semi

Filter: returns left rows that have a match on the right, without joining columns.

```python
result = df1.join(df2, on="property_name", how="semi")
```

### Anti

The inverse filter — left rows with no match on the right.

```python
result = df1.join(df2, on="property_name", how="anti")
```

## Non-Equi Joins

`join_where()` supports arbitrary predicates. Multiple predicates are AND-combined.

```python
result = df1.join_where(df2, pl.col("cash") > pl.col("cost"))

result = df1.join_where(
    df2,
    [pl.col("a") > pl.col("b"), pl.col("c") < pl.col("d")]
)
```

## Asof Joins

Match on the nearest key rather than exact equality — common for time-series.

```python
result = df_trades.join_asof(
    df_quotes,
    on="time",
    by="stock",
    check_sortedness=False,
)
```

- `by=...` — require exact match on these columns before nearest-key matching
- `strategy="backward"` (default), `"forward"`, or `"nearest"`
- `tolerance="1m"` — cap the allowed distance

```python
result = df_trades.join_asof(
    df_quotes,
    on="time",
    by="stock",
    tolerance="1m",
)
```

## Cartesian Product

```python
tokens = pl.DataFrame({"token": ["hat", "shoe", "boat"]})
result = players.select(pl.col("name")).join(tokens, how="cross")
```

`how="cross"` takes no `on`/`left_on`/`right_on` and produces *n × m* rows.

## API Summary

- `DataFrame.join(other, on=..., how=...)`
- `DataFrame.join_where(other, predicate)`
- `DataFrame.join_asof(other, on=..., by=..., strategy=..., tolerance=...)`
