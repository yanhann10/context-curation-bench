# Expressions and Basic Operations

**Source:** https://docs.pola.rs/user-guide/expressions/basic-operations/
**Fetched:** 2026-04-18

Fundamental operations on DataFrame columns using Polars expressions — arithmetic, comparisons, boolean logic, conditionals.

## Sample DataFrame

```python
import polars as pl
import numpy as np

np.random.seed(42)
df = pl.DataFrame({
    "nrs": [1, 2, 3, None, 5],
    "names": ["foo", "ham", "spam", "egg", "spam"],
    "random": np.random.rand(5),
    "groups": ["A", "A", "B", "A", "B"],
})
```

## Arithmetic

Standard operators broadcast as expected. Supported: `+`, `-`, `*`, `/`, `**`, `%`. Named equivalents: `.add()`, `.sub()`, `.mul()`, `.truediv()`, `.pow()`, `.mod()`.

```python
result = df.select(
    (pl.col("nrs") + 5).alias("nrs + 5"),
    (pl.col("nrs") - 5).alias("nrs - 5"),
    (pl.col("nrs") * pl.col("random")).alias("nrs * random"),
    (pl.col("nrs") / pl.col("random")).alias("nrs / random"),
    (pl.col("nrs") ** 2).alias("nrs ** 2"),
    (pl.col("nrs") % 3).alias("nrs % 3"),
)
```

When an arithmetic operation takes `null` as one of its operands, the result is `null`.

## Comparisons

Comparison operators return booleans. Named equivalents: `.gt()`, `.gt_eq()`, `.lt()`, `.lt_eq()`, `.ne()`, `.eq()`.

```python
result = df.select(
    (pl.col("nrs") > 1).alias("nrs > 1"),
    (pl.col("nrs") >= 3).alias("nrs >= 3"),
    (pl.col("random") < 0.2).alias("random < .2"),
    (pl.col("random") <= 0.5).alias("random <= .5"),
    (pl.col("nrs") != 1).alias("nrs != 1"),
    (pl.col("nrs") == 1).alias("nrs == 1"),
)
```

## Boolean and Bitwise

Python uses `&`, `|`, `~` because `and`/`or`/`not` are reserved. Named: `.and_()`, `.or_()`, `.not_()`.

```python
result = df.select(
    ((~pl.col("nrs").is_null()) & (pl.col("groups") == "A"))
        .alias("number not null and group A"),
    ((pl.col("random") < 0.5) | (pl.col("groups") == "B"))
        .alias("random < 0.5 or group B"),
)
```

Bitwise uses the same operators with integer operands:

```python
df.select(
    pl.col("nrs") & 6,
    pl.col("nrs") | 6,
    ~pl.col("nrs"),
    pl.col("nrs") ^ 6,
)
```

## Counting Unique Values

- `n_unique()` — exact distinct count
- `approx_n_unique()` — HyperLogLog++ estimate for large data
- `value_counts()` — struct column of value/count pairs
- `unique(maintain_order=True)` and `unique_counts()`

```python
result = df.select(
    pl.col("names").value_counts().alias("value_counts"),
)

result = df.select(
    pl.col("names").unique(maintain_order=True).alias("unique"),
    pl.col("names").unique_counts().alias("unique_counts"),
)
```

## Conditionals

`when / then / otherwise` mimics a ternary:

```python
result = df.select(
    pl.col("nrs"),
    pl.when(pl.col("nrs") % 2 == 1)
        .then(3 * pl.col("nrs") + 1)
        .otherwise(pl.col("nrs") // 2)
        .alias("Collatz"),
)
```

Values evaluating to `True` are replaced by the expression inside `then`; `False` rows take `otherwise`, or `null` if `otherwise` is omitted.

### Chained Conditionals

Chain `.when(...).then(...)` for elif-like behavior. Polars evaluates top-to-bottom and takes the first matching branch.

## Key Takeaways

- Null propagation applies to all arithmetic and comparison operations
- Use `&`, `|`, `~` (not `and`/`or`/`not`)
- `when/then/otherwise` for conditional logic
- `pl.col(...)` is the column reference; `.alias(...)` names the output
