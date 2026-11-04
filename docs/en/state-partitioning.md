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
