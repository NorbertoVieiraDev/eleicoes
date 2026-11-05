# State-scoped Parquet files

## Why these files exist

The election site currently runs DuckDB-Wasm in each visitor's browser. An annual vote file can be hundreds of megabytes, so a query for one state still has to inspect a large remote Parquet file. State-scoped files let the browser download only the selected state's rows. They are an additional access layout; the annual canonical Parquets remain the unchanged source of record.

## Reproduce the files

Use Python 3.9+ and install the repository requirements. Keep the original canonical files outside Git and run one command for each annual file:

```sh
python scripts/partition_canonical.py \
  --input derived/canonical/votes-2024.parquet \
  --output-dir derived/partitioned
python scripts/partition_canonical.py \
  --input derived/canonical/sections-2024.parquet \
  --output-dir derived/partitioned
```

Repeat for each available year. The script uses DuckDB to copy all columns and rows for each exact `state_code` value into `votes-YYYY-UF.parquet` or `sections-YYYY-UF.parquet`. Rows with a missing state are kept in a separate `*-YYYY-_NULL.parquet` shard. Within a shard, rows are sorted by the available election, office, municipality, zone, section, urn, and candidate fields to improve row-group pruning. No votes are recalculated or filtered out.

Each run writes a JSON manifest containing the source and output SHA-512 hashes, row counts, vote sums, null-vote counts, file sizes, and per-state results. The script verifies those counts and sums before recording the manifest. Keep the generated Parquets and manifests outside Git; publish only reviewed aggregate evidence.

## Integrity and interpretation

Partitioning changes file boundaries and row order only. Each output contains the source columns and source values for its state. For every state, the generated row count, sum of non-null votes, and count of null vote values are compared to the corresponding source values. SHA-512 hashes identify the exact input and output bytes; because the output is recompressed and reordered, its hash is expected to differ from the source.

A state file is a query optimization, not a new official TSE dataset. The annual canonical file remains available for searches without a selected state. A missing field remains missing, and an unavailable year remains unavailable. The browser should fall back to the annual file until a state shard has been published.

## Storage and publication

These are duplicate derived files. Before upload, sum their measured sizes and confirm that the bucket has sufficient free storage. Do not delete or replace canonical files as part of this process. Publish state shards under the same `canonical/` prefix only after the public site reader supports the shard filename pattern. Keep credentials out of this repository.

## Generated audit reports

The public [summary report](../../reports/history/state-partitioning-summary.json) lists input and output sizes and row totals by year. Each year also has a detailed report with source and shard SHA-512 hashes, per-state row counts, vote sums, null-vote counts, and file sizes. For example, [2024](../../reports/history/state-partitioning-2024.json). These reports contain metadata only; Parquet data files are not stored in Git.

## Resource-bounded generation

Global sorting is still required by default. For constrained cloud environments,
optional `--memory-limit`, `--temp-dir` and `--max-temp-size` settings bound DuckDB
resources. `--sort-mode best-effort` retries a state's COPY without global sorting
only if the sorted COPY raises `duckdb.OutOfMemoryException`; it removes the
unvalidated temporary output before retrying. Other errors still abort. Explicit
`--sort-mode none` skips sorting, while `required` preserves the previous default.
All modes retain source columns, values, duplicates and integrity checks.

The manifest records `sort_mode`, requested resource limits and each shard's
`sort_applied`. Unsorted shards may require more reads for specific filters;
benchmark them separately. The script never uploads data or removes canonical
inputs. Example:

```sh
python scripts/partition_canonical.py --input /data/votes-2018.parquet \
  --output-dir /data/shards --threads 1 --memory-limit 5GiB \
  --temp-dir /data/spill --max-temp-size 3GiB --sort-mode best-effort
```

## Globally sort large shards with dictionary-coded batches

Optional `scripts/sort_partition_bounded.py` sorts a verified state shard without
carrying repeated strings through the sort. Text fields with up to one million
distinct values use reversible dictionary IDs. Sort-key dictionaries preserve
lexical order and place nulls last; original columns/types are reconstructed in
122,880-row Arrow batches. No dictionary columns enter the final Parquet.

Install `requirements-partition.txt` (DuckDB 1.4.3, PyArrow 20.0.0), then provide
`--input`, `--output-dir`, `--expected-input-sha512` and `--canonical-sha512`.
The helper uses one thread, 6 GiB memory and 3 GiB spill. It checks schemas, input
identity, rows/votes/nulls and two all-column logical hash aggregates. These are
diagnostics, not a collision-free proof. Synthetic tests compare exact multisets
in both directions, including duplicates, lexical keys and nulls.

The output filename includes 12 SHA-512 characters and has a new manifest. Publish
that immutable name instead of replacing an object during active Range reads.
The helper does not upload anything. All five previously unsorted SP vote shards
for 2018–2026 completed this repair in the 2026-11-05 cloud validation.
