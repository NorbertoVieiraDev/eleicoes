# How the official files become Parquet

This project changes the **storage representation** to make analysis practical. Readers should be able to verify this claim from the source files, published code and explicit transformation rules, rather than relying on an assurance from the project. The original TSE ZIPs remain unchanged.

## Traceable sequence for the existing 2026 pipeline

1. Obtain the official ZIP URL and SHA-512 from `data/2026/round-1/manifest.json` or `round-2/manifest.json`. These are snapshots, not automatically updated results.
2. Download the ZIP over HTTPS. Compute its SHA-512 and compare with the published value. Stop on mismatch. A matching ZIP hash says nothing by itself about the correctness of a derived Parquet file.
3. Open the ZIP and require exactly one CSV member. Read its text with **Latin-1**, then write a temporary **UTF-8** copy. This changes byte encoding, not the intended accented characters. ZIP reading also checks archive CRCs while extracting the member.
4. Parse the CSV with **DuckDB 1.4.3**, separator `;`, header enabled, `all_varchar=true`, `strict_mode=true`, and `nullstr=''`. Every original column is initially stored as text. Empty CSV fields are represented as SQL `NULL` under this parser configuration; literal markers such as `#NULO#` and `-1` are retained. This empty-to-NULL convention is a transformation and is disclosed here.
5. Select every original column, then append two provenance columns: `source_package` (ZIP filename) and `source_sha512` (the checked source ZIP hash). No candidate selection, vote summation, deduplication or zero-padding is applied to this raw export.
6. Write `<source-package>.parquet` using **Zstandard (ZSTD)** compression. Compression is reversible. The raw export does not intentionally filter records. It is a parsed table, not a byte-for-byte copy of the CSV: separators, quoting, encoding and physical row layout belong to the source representation.
7. Record row count, source hash, pipeline version, output size and processing time in the local package JSON. Remove only the temporary UTF-8 copy. Original ZIPs are preserved.

Implementation: [`scripts/prepare.py`](../../scripts/prepare.py). Dependencies: [`requirements.txt`](../../requirements.txt). Source URLs, checksums and the corrected RR source link are in the manifests. File SHA values differ between ZIP, CSV and Parquet by design; none can be compared as if they were the same bytes. Exact Parquet bytes/order may also vary across library versions. Compare logical records with duplicate multiplicity, not file hashes across different formats.

## Raw exports versus calculated products

| Product | What changes |
| --- | --- |
| `<package>.parquet` | CSV parsing/encoding and compression; two provenance columns added; original columns retained as text |
| `votes` view | English analytical aliases, strict numeric casts for measures, and leading-zero padding for municipality/zone/section codes |
| `*.sections.parquet` / `section_office` | Groups source rows by election, territory, section and office; sums votes and computes consistency diagnostics |
| Candidate aggregates | Sum recorded votes at municipality/UF level; explicitly exclude nonpositive office/votable placeholder codes |
| `section_aliases` | Resolves listed aggregated sections to a principal BU for lookup; does not allocate or manufacture extra votes |

Two 2026 second-round source placeholders with zero votes and `-1`/`#NULO#` codes stay in the raw exports and `votes`. Exclusion from candidate aggregates is documented, not hidden removal from the source layer. Senate diagnostics account for two choices in the first round of 2026. These calculated products must not be described as unchanged official source files.

## Reproduce and inspect independently

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/download.py --year 2026
python scripts/prepare.py --year 2026
python -m unittest discover -s tests -v
```

For a small initial example, run preparation with `--only bweb_2t_ZZ_261020260742.zip` after downloading. This produces that package's Parquet/profile; it does not constitute a full national run. Inspect its original CSV and the original-named columns in Parquet, excluding the two added provenance columns. For a full equivalence audit, compare column names, row counts and the **multiset of all parsed original-column values**, preserving duplicates and the stated NULL convention. A total-vote match alone cannot prove row-level equality. Do not assume identical physical row order.

The current published report records 56 source packages, 69,947,081 parsed rows, approximately 32.42 GB of CSV and 2.57 GB of raw Parquet. Compression gains come from columnar encoding and repeated values, not from a reported row-reduction step. Size figures exclude section profiles and other aggregates. Three synthetic integration tests cover identifier/vote preservation and turnout grain, checksum rejection and invalid numeric votes.

## What has and has not been verified

The existing report checks source package hashes, key/quantity validity, duplicate vote keys, repeated metadata and ballot/turnout balances. It **does not report a full independent source-versus-Parquet multiset comparison**. Resume mode trusts existing conversion metadata and does not hash existing derived files again. For an independent reproduction, use a clean output directory/checkout and original sources. Parquet files are project-derived artifacts, not files signed or certified by the TSE. This process does not establish the presence of every expected section, verify urn digital signatures, or reproduce judicial adjustments to official totalization.

## Historical collector / Coletor histórico

The newer historical collector has separate settings and per-member fingerprint comparisons. See [historical data](historical-data.md); do not apply the earlier 2026 settings to every output.
