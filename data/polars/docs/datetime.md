# Datetime and Time Series

**Source:** https://docs.pola.rs/user-guide/transformations/time-series/parsing/
**Fetched:** 2026-04-18

Polars has native support for parsing time-series data and performing temporal grouping, resampling, and feature extraction.

## Datetime Dtypes

- **`Date`** — calendar date (days since Unix epoch, i32)
- **`Datetime`** — date + time (i64 with configurable time unit: `ns`, `us`, `ms`)
- **`Duration`** — time delta, produced by subtracting dates/datetimes
- **`Time`** — time of day (ns since midnight)

## Parsing Dates from Files

Pass `try_parse_dates=True` to `read_csv()` to infer date columns from a sample of rows (default 100).

```python
df = pl.read_csv("docs/assets/data/apple_stock.csv", try_parse_dates=True)
```

Schema inference is computationally expensive. Binary formats like Parquet preserve the schema natively and skip inference.

## Converting Strings to Dates

```python
df = pl.read_csv("docs/assets/data/apple_stock.csv", try_parse_dates=False)
df = df.with_columns(pl.col("Date").str.to_date("%Y-%m-%d"))
```

Format strings follow the chrono `strftime` spec.

For datetimes: `str.to_datetime(format, time_unit=..., time_zone=...)`.

## Extracting Features

The `.dt` namespace exposes component extractors:

- `dt.year()`, `dt.month()`, `dt.day()`
- `dt.hour()`, `dt.minute()`, `dt.second()`, `dt.nanosecond()`
- `dt.weekday()` — 1 (Mon) to 7 (Sun)
- `dt.ordinal_day()` — day of year
- `dt.iso_year()`, `dt.week()`
- `dt.quarter()`
- `dt.timestamp(time_unit="ms" | "us" | "ns")`

```python
df_with_year = df.with_columns(pl.col("Date").dt.year().alias("year"))
```

## Truncating and Offsetting

- `dt.truncate("1mo")` — snap down to month/day/hour/minute boundary
- `dt.round("5m")` — round to the nearest window
- `dt.offset_by("1d")` — add a duration (e.g. `"1y"`, `"3mo"`, `"-7d"`, `"2h30m"`)

## Time Zones

For datasets with mixed UTC offsets (DST transitions), Polars normalizes to UTC at parse time. Then convert with `dt.convert_time_zone(tz)` or set `time_zone=` on `str.to_datetime()`.

```python
data = [
    "2021-03-27T00:00:00+0100",
    "2021-03-28T00:00:00+0100",
    "2021-03-29T00:00:00+0200",
    "2021-03-30T00:00:00+0200",
]
mixed_parsed = (
    pl.Series(data)
    .str.to_datetime("%Y-%m-%dT%H:%M:%S%z")
    .dt.convert_time_zone("Europe/Brussels")
)
```

Use `dt.replace_time_zone(tz)` to attach (or overwrite) a tz without converting the underlying instant.

## Temporal Grouping

- `df.group_by_dynamic("time", every="1d", ...)` — rolling/tumbling windows over time
- `df.upsample(time_column=..., every="1h")` — resample at fixed intervals

These pair well with the usual `agg()` API.
