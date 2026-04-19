# CSV IO

**Source:** https://docs.pola.rs/user-guide/io/csv/
**Fetched:** 2026-04-18

Polars exposes three CSV operations: eager read, lazy scan, and write.

## Reading CSV (Eager)

`pl.read_csv()` parses the file immediately into a `DataFrame`.

```python
df = pl.read_csv("docs/assets/data/path.csv")
```

Useful parameters:

- `has_header: bool = True`
- `separator: str = ","`
- `columns: list[str] | list[int] | None`
- `dtypes: dict[str, DataType] | None` — schema override
- `null_values: str | list[str] | dict | None`
- `try_parse_dates: bool = False` — infer date columns
- `n_rows: int | None` — limit rows read
- `skip_rows: int = 0`
- `encoding: str = "utf8"`

## Writing CSV

`DataFrame.write_csv()` writes a CSV file.

```python
df = pl.DataFrame({"foo": [1, 2, 3], "bar": [None, "bak", "baz"]})
df.write_csv("docs/assets/data/path.csv")
```

Useful parameters: `separator`, `include_header`, `null_value`, `date_format`, `datetime_format`, `float_precision`, `quote_style`.

## Scanning CSV (Lazy)

`pl.scan_csv()` returns a `LazyFrame` — parsing is deferred until `collect()`.

```python
df = pl.scan_csv("docs/assets/data/path.csv")
```

Lazy scanning enables:

- **Predicate pushdown** — filters applied at the scanner, reducing parsed rows
- **Projection pushdown** — only requested columns are parsed
- **Slice pushdown** — limits are applied at scan time

This is typically much faster than `read_csv()` followed by a filter.

## Summary

- `pl.read_csv(path, ...)` — eager read, returns `DataFrame`
- `pl.scan_csv(path, ...)` — lazy read, returns `LazyFrame`
- `df.write_csv(path, ...)` — eager write
- `lf.sink_csv(path)` — streaming write from a `LazyFrame`
