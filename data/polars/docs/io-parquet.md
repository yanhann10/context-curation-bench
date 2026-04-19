# Parquet IO

**Source:** https://docs.pola.rs/user-guide/io/parquet/
**Fetched:** 2026-04-18

Loading or writing Parquet files is very fast in Polars because the in-memory columnar layout closely mirrors the Parquet on-disk format.

## Reading Parquet

`pl.read_parquet()` eagerly loads the file into a `DataFrame`.

```python
df = pl.read_parquet("docs/assets/data/path.parquet")
```

## Writing Parquet

`DataFrame.write_parquet()` serializes to Parquet.

```python
df = pl.DataFrame({"foo": [1, 2, 3], "bar": [None, "bak", "baz"]})
df.write_parquet("docs/assets/data/path.parquet")
```

Useful parameters:

- `compression` — `"zstd"` (default), `"snappy"`, `"gzip"`, `"lz4"`, `"brotli"`, `"uncompressed"`
- `compression_level` — compression-specific tuning
- `statistics: bool = True` — write per-row-group min/max metadata
- `row_group_size: int | None`

## Scanning Parquet (Lazy)

`pl.scan_parquet()` returns a `LazyFrame` — no data is read until `collect()`.

```python
lf = pl.scan_parquet("docs/assets/data/path.parquet")
```

Scanning enables:

- **Predicate pushdown** — filters evaluated per row-group; row-groups whose statistics cannot satisfy the filter are skipped entirely
- **Projection pushdown** — only requested columns are read
- **Cloud efficiency** — when the Parquet lives on S3/GCS/etc., pushdowns minimize bytes downloaded

## Streaming Writes

For larger-than-memory outputs, stream directly from a `LazyFrame`:

```python
lf.sink_parquet("output.parquet")
```

This avoids materializing the full result in memory.

## Summary

- `pl.read_parquet(path)` — eager read
- `pl.scan_parquet(path)` — lazy read
- `df.write_parquet(path)` — eager write
- `lf.sink_parquet(path)` — streaming write
