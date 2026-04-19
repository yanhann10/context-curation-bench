# DataFrame, Series, and Data Types

**Source:** https://docs.pola.rs/user-guide/concepts/data-types-and-structures/
**Fetched:** 2026-04-18

Polars supports a comprehensive range of data types organized into several categories: numeric (signed/unsigned integers, floats, decimals), nested (lists, arrays, structs), temporal (date/time), and miscellaneous (strings, booleans).

All types support missing values represented by the special value `null`. This is not to be conflated with the special value `NaN` in floating number data types.

## Series: One-Dimensional Data Structure

A `Series` is a 1-dimensional homogeneous data structure — all elements share the same dtype.

```python
import polars as pl
s = pl.Series("ints", [1, 2, 3, 4, 5])
print(s)
```

Polars automatically infers data types, but you can override:

```python
s1 = pl.Series("ints", [1, 2, 3, 4, 5])
s2 = pl.Series("uints", [1, 2, 3, 4, 5], dtype=pl.UInt64)
print(s1.dtype, s2.dtype)
```

## DataFrame: Two-Dimensional Data Structure

A `DataFrame` is a 2-dimensional heterogeneous structure containing uniquely named series.

```python
from datetime import date

df = pl.DataFrame(
    {
        "name": ["Alice Archer", "Ben Brown", "Chloe Cooper", "Daniel Donovan"],
        "birthdate": [
            date(1997, 1, 10),
            date(1985, 2, 15),
            date(1983, 3, 22),
            date(1981, 4, 30),
        ],
        "weight": [57.9, 72.5, 53.6, 83.1],
        "height": [1.56, 1.77, 1.65, 1.75],
    }
)
print(df)
```

## Inspecting DataFrames

- `df.head(n)` — first n rows (default 5)
- `df.tail(n)` — last n rows
- `df.glimpse(return_type="string")` — vertically-oriented view, useful for wide data
- `df.sample(n)` — random sample
- `df.describe()` — summary statistics

```python
print(df.head(3))
print(df.tail(3))
print(df.sample(2))
print(df.describe())
```

## Schema Management

`df.schema` maps column names to their dtypes.

```python
print(df.schema)
```

Specify schema at construction:

```python
df = pl.DataFrame(
    {"name": ["Alice", "Ben", "Chloe", "Daniel"], "age": [27, 39, 41, 43]},
    schema={"name": None, "age": pl.UInt8},
)
```

Or partially override with `schema_overrides`:

```python
df = pl.DataFrame(
    {"name": ["Alice", "Ben"], "age": [27, 39]},
    schema_overrides={"age": pl.UInt8},
)
```

## Data Types Reference

| Type | Purpose |
|---|---|
| `Boolean` | bit-packed booleans |
| `Int8`, `Int16`, `Int32`, `Int64`, `Int128` | signed integers |
| `UInt8`, `UInt16`, `UInt32`, `UInt64`, `UInt128` | unsigned integers |
| `Float32`, `Float64` | floating-point |
| `Decimal` | precision-controlled decimals |
| `String` | UTF-8 text |
| `Binary` | raw binary |
| `Date`, `Time`, `Datetime`, `Duration` | temporal types |
| `Array` | fixed-shape nested |
| `List` | variable-length nested |
| `Categorical` | runtime string categories |
| `Enum` | predetermined string categories |
| `Struct` | composite multi-field |

## Floating-Point Considerations

Polars generally adheres to IEEE 754, with one exception: any `NaN` compares equal to any other `NaN`, and greater than any non-`NaN` value.
