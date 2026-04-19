# String Expressions

**Source:** https://docs.pola.rs/user-guide/expressions/strings/
**Fetched:** 2026-04-18

All string operations live under the `str` namespace on expressions. Polars follows the Arrow columnar format for efficient text processing.

## Length

```python
import polars as pl

df = pl.DataFrame({
    "language": ["English", "Dutch", "Portuguese", "Finish"],
    "fruit": ["pear", "peer", "pêra", "päärynä"],
})

result = df.with_columns(
    pl.col("fruit").str.len_bytes().alias("byte_count"),
    pl.col("fruit").str.len_chars().alias("letter_count"),
)
```

- `str.len_bytes()` — UTF-8 byte length
- `str.len_chars()` — Unicode character length

## Pattern Matching

- `str.contains(pattern, literal=False)` — regex by default
- `str.starts_with(prefix)`
- `str.ends_with(suffix)`

```python
result = df.select(
    pl.col("fruit"),
    pl.col("fruit").str.starts_with("p").alias("starts_with_p"),
    pl.col("fruit").str.contains("p..r").alias("p..r"),
    pl.col("fruit").str.ends_with("r").alias("ends_with_r"),
)
```

Polars uses the Rust `regex` crate — the regex flavor differs from Python's `re`.

## Extraction

`str.extract(pattern, group_index=1)` returns the captured group; `str.extract_all(pattern)` returns all matches as a list column.

```python
df = pl.DataFrame({"urls": [
    "http://vote.com/ballon_dor?candidate=messi&ref=polars",
    "http://vote.com/ballon_dor?candidate=ronaldo&ref=polars",
]})

result = df.select(
    pl.col("urls").str.extract(r"candidate=(\w+)", group_index=1),
)
```

```python
df = pl.DataFrame({"text": ["123 bla 45 asd", "xyz 678 910t"]})
result = df.select(
    pl.col("text").str.extract_all(r"(\d+)").alias("extracted_nrs"),
)
```

## Replacement

- `str.replace(pattern, value)` — first occurrence
- `str.replace_all(pattern, value)` — all non-overlapping occurrences

```python
df = pl.DataFrame({"text": ["123abc", "abc456"]})
result = df.with_columns(
    pl.col("text").str.replace(r"\d", "-"),
    pl.col("text").str.replace_all(r"\d", "-").alias("text_replace_all"),
)
```

## Case Conversion

- `str.to_lowercase()`
- `str.to_uppercase()`
- `str.to_titlecase()`

```python
addresses = pl.DataFrame({"addresses": ["128 PERF st", "Rust blVD, 158"]})
result = addresses.select(
    pl.col("addresses").str.to_titlecase(),
    pl.col("addresses").str.to_lowercase().alias("lower"),
    pl.col("addresses").str.to_uppercase().alias("upper"),
)
```

## Stripping

| Function | Behavior |
|---|---|
| `str.strip_chars(chars)` | remove any of `chars` from both ends |
| `str.strip_chars_end(chars)` | remove any of `chars` from end |
| `str.strip_chars_start(chars)` | remove any of `chars` from start |
| `str.strip_prefix(prefix)` | remove exact literal prefix |
| `str.strip_suffix(suffix)` | remove exact literal suffix |

The first three treat their argument as a character set; the last two treat it as a literal substring. When called with no argument, the first three default to whitespace.

## Slicing

- `str.slice(offset, length=None)` — general slice
- `str.head(n)` — first n characters
- `str.tail(n)` — last n characters

```python
df = pl.DataFrame({
    "fruits": ["pear", "mango", "dragonfruit", "passionfruit"],
    "n": [1, -1, 4, -4],
})

result = df.with_columns(
    pl.col("fruits").str.slice(pl.col("n")).alias("slice"),
    pl.col("fruits").str.head(pl.col("n")).alias("head"),
    pl.col("fruits").str.tail(pl.col("n")).alias("tail"),
)
```

## Splitting

- `str.split(by)` — split into a list column
- `str.split_exact(by, n)` — fixed-width split into struct
- `str.splitn(by, n)` — cap the number of splits

Consult the API docs for the full `str` namespace — there are 40+ functions.
