# Null and Missing Data Handling

**Source:** https://docs.pola.rs/user-guide/expressions/missing-data/
**Fetched:** 2026-04-18

Polars represents missing data uniformly with `null` across all dtypes — unlike pandas, which uses type-dependent markers. `NaN` is a distinct concept applicable only to floating-point columns.

The value `NaN` is considered a valid floating-point value, which is different from missing data.

## Creating Nulls

```python
import polars as pl

df = pl.DataFrame({"value": [1, None]})
print(df)
```

## Validity Bitmap

Polars tracks nulls with a validity bitmap — for a series of length n, the bitmap needs n/8 bytes. This makes null checks O(1) to metadata queries like `null_count`.

## Counting and Detecting Nulls

- `df.null_count()` — total nulls per column
- `pl.col(...).is_null()` — boolean mask of nulls
- `pl.col(...).is_not_null()`

```python
print(df.null_count())

is_null_series = df.select(pl.col("value").is_null())
```

## Filling Nulls — `fill_null`

### Literal value

```python
df.with_columns(pl.col("col2").fill_null(3))
```

### Expression-based

```python
df = pl.DataFrame({
    "col1": [0.5, 1, 1.5, 2, 2.5],
    "col2": [1, None, 3, None, 5],
})

df.with_columns(
    pl.col("col2").fill_null((2 * pl.col("col1")).cast(pl.Int64)),
)
```

### Forward / backward strategies

```python
df.with_columns(
    pl.col("col2").fill_null(strategy="forward").alias("forward"),
    pl.col("col2").fill_null(strategy="backward").alias("backward"),
)
```

Other valid strategies: `"mean"`, `"min"`, `"max"`, `"zero"`, `"one"`.

### Interpolation

For numeric columns:

```python
df.with_columns(pl.col("col2").interpolate())
```

Nulls at the beginning and end of the series remain null after interpolation.

## Dropping Nulls

- `df.drop_nulls()` — drop any row with a null
- `df.drop_nulls(subset=["col"])` — only check specified columns

## NaN vs Null

| Aspect | `null` | `NaN` |
|---|---|---|
| counted by `null_count` | yes | no |
| touched by `fill_null` | yes | no |
| touched by `fill_nan` | no | yes |
| tracked via metadata bitmap | yes | no |
| in aggregations (mean/sum) | skipped | propagates |

To exclude NaN from aggregates, convert it to null first:

```python
mean_nan_df = nan_df.with_columns(
    pl.col("value").fill_nan(None).alias("replaced"),
).select(
    pl.all().mean().name.suffix("_mean"),
)
```

## Useful Methods Summary

- `is_null()`, `is_not_null()`, `is_nan()`, `is_finite()`, `is_infinite()`
- `null_count()`
- `fill_null(value_or_strategy)`
- `fill_nan(value)`
- `drop_nulls(subset=None)`
- `interpolate()`
