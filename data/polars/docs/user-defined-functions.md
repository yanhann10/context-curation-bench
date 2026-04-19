# User-Defined Functions (UDFs)

**Source:** https://docs.pola.rs/user-guide/expressions/user-defined-python-functions/
**Fetched:** 2026-04-18

Polars provides two primary APIs for executing custom Python functions on data:

- **`map_elements()`** — applied to each value individually
- **`map_batches()`** — applied to the whole Series at once

Before writing a UDF, check whether a Polars plugin or a vectorized expression can do the job — both outperform Python-level UDFs.

## `map_elements()` — per value

```python
import math

def my_log(value):
    return math.log(value)

out = df.select(
    pl.col("values").map_elements(my_log, return_dtype=pl.Float64)
)
```

This is slow because Python is called once per row. Use only when vectorized options don't exist.

## `map_batches()` — per Series

```python
def diff_from_mean(series):
    total = 0
    for value in series:
        total += value
    mean = total / len(series)
    return pl.Series([value - mean for value in series])

out = df.select(
    pl.col("values").map_batches(diff_from_mean, return_dtype=pl.Float64)
)
```

Works in `group_by` contexts:

```python
out = df.group_by("keys").agg(
    pl.col("values").map_batches(diff_from_mean, return_dtype=pl.Float64)
)
```

## Speeding Up with NumPy / Numba

Pass a NumPy ufunc directly:

```python
import numpy as np
out = df.select(pl.col("values").map_batches(np.log, return_dtype=pl.Float64))
```

Numba `@guvectorize`:

```python
from numba import guvectorize, int64, float64

@guvectorize([(int64[:], float64[:])], "(n)->(n)")
def diff_from_mean_numba(arr, result):
    total = 0
    for v in arr: total += v
    mean = total / len(arr)
    for i, v in enumerate(arr):
        result[i] = v - mean

out = df.select(
    pl.col("values").map_batches(diff_from_mean_numba, return_dtype=pl.Float64)
)
```

Series values are converted to NumPy arrays before calling the function.

## Missing Data Warning

NumPy lacks null support. If the Series has nulls, generalized ufuncs like Numba-compiled code will error. Fill or drop nulls first with `fill_null(...)` or `drop_nulls()`.

## Multi-Column UDFs via Struct

Combine columns into a `Struct` and unpack inside the function:

```python
@guvectorize([(int64[:], int64[:], float64[:])], "(n),(n)->(n)")
def add(arr, arr2, result):
    for i in range(len(arr)):
        result[i] = arr[i] + arr2[i]

df3 = pl.DataFrame({"values_1": [1, 2, 3], "values_2": [10, 20, 30]})

out = df3.select(
    pl.struct(["values_1", "values_2"])
      .map_batches(
          lambda combined: add(
              combined.struct.field("values_1"),
              combined.struct.field("values_2"),
          ),
          return_dtype=pl.Float64,
      )
      .alias("add_columns")
)
```

## Streaming — `is_elementwise`

For truly elementwise ops (e.g. `log`), set `is_elementwise=True` on `map_batches` to process in chunks:

```python
pl.col("x").map_batches(np.log, return_dtype=pl.Float64, is_elementwise=True)
```

**Caution:** misuse (on non-elementwise functions like `mean`) produces incorrect results.

## Return Type Inference

Polars infers return dtype from the first non-null value. Override with `return_dtype=...`.

Python type mappings: `int → Int64`, `float → Float64`, `bool → Boolean`, `str → String`, `list[T] → List[T]`, `dict[str, T] → Struct`.
