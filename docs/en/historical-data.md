# Historical BU discovery and raw Parquet conversion

## Scope of “all available elections”

The 2026-11-01 official catalog search for `boletim` returned 11 datasets with **425 tabular BU ZIP resources**: regular 2012, 2014, 2016, 2018, 2020, 2022, 2024 and 2026 elections, plus supplementary BU bundles under the 2020, 2022 and 2024 catalog cycles. This is a catalog snapshot, not a claim that every election ever held has downloadable BU files. Candidate registers, finance, electorate, binary urn archives, logs and RDVs are outside this BU conversion scope.

The resource counts are 46, 56, 46, 56, 54, 56, 52 and 56 for the respective regular years, plus three supplementary outer ZIPs. Municipal-election coverage differs from general elections; missing second-round contests must not be invented. All 425 ZIP URLs responded HTTP 200 in the initial HEAD probe, totaling approximately 13.78 GB of reported compressed size. Successful HEAD probes are not proof of completed downloads or conversions; use the final conversion report.

## Completed collection snapshot (2026-11-01)

All **425 of 425** cataloged outer ZIP packages were downloaded and converted successfully. They produced **466 local Parquet member files**, **420,378,316 rows**, and **5,655,459,985 bytes** of Parquet output (about 5.66 GB decimal). The package-level record, including source URL, source SHA-512, published-checksum status, source member, output SHA-512, row count and validation fields, is [`reports/history/conversion-records.json`](../../reports/history/conversion-records.json). A separate audit recomputed the SHA-512 of every downloaded ZIP and every generated Parquet; all sizes and hashes matched the records. All member row counts, source column names/order and DuckDB logical fingerprints matched.

| Catalog cycle | ZIP packages | Parquet members | Rows | Parquet bytes |
|---:|---:|---:|---:|---:|
| 2012 | 46 | 46 | 34,430,589 | 206,369,956 |
| 2014 | 56 | 56 | 56,748,147 | 258,592,988 |
| 2016 | 46 | 46 | 36,685,609 | 168,634,421 |
| 2018 | 56 | 56 | 73,552,486 | 349,764,055 |
| 2020 | 55 | 83 | 37,911,271 | 247,162,413 |
| 2022 | 57 | 57 | 72,978,729 | 460,030,267 |
| 2024 | 53 | 66 | 38,124,404 | 1,395,039,627 |
| 2026 | 56 | 56 | 69,947,081 | 2,569,866,258 |
| **Total** | **425** | **466** | **420,378,316** | **5,655,459,985** |

The catalog listed and matched an outer-package checksum for 422 packages. Three supplementary outer ZIPs had no checksum listed in the catalog; where inner ZIP checksums were present in their parent archive they were verified separately. The 2018 and 2020 source CSVs contained **46,580 unescaped quote marks** inside quoted text fields (29,778 and 16,802 respectively). The documented compatibility step preserves those literal quote characters and records the repair count per member; it does not skip malformed rows. Actual source ZIPs and Parquets remain local and are excluded from GitHub because of their size. The report and reproducible scripts are public; the report's logical fingerprints are consistency diagnostics, not an independent implementation or collision-free proof.

## Reproduce

```sh
python scripts/discover_bu.py
python scripts/probe_inventory.py
python scripts/collect_history.py --include-2026 --workers 2
python -m unittest discover -s tests -v
```

Run from an environment with the pinned requirements installed. Discovery refreshes the source inventory; review changes before downloading. `--year 2012` limits collection to one catalog year. By default, the historical collector skips 2026 because the earlier analytical pipeline already covers it; `--include-2026` also produces the new raw historical-format exports for 2026. The two output families are separate and must not be unioned as if they were different votes.

Source indexes: `data/<catalog-year>/round-<n>/source-index.json`; supplementary bundles: `data/<catalog-year>/supplementary/source-index.json`. Downloads remain under each ignored `raw/`. Conversion outputs are under ignored `derived/history/<catalog-year>/<partition>/`. Public evidence is under `reports/history/`. SHA-512 hashes of local derived Parquets are recorded for identifying a particular run, not as signatures by the TSE.

## Schema adapters and preservation

CSV header names are retained verbatim, including historical spelling/spacing differences such as `SG_ UF`. For TXT without a header, a first field shaped like a generation date is recognized as data, and columns are named `field_001`, `field_002`, etc. The first record is never consumed as a header. These positional names deliberately do not assert an unreviewed semantic mapping. Other first-record patterns stop conversion for review. No harmonized historical dashboard schema is implied by raw conversion.

The collector decodes Latin-1 into temporary UTF-8 and parses semicolon-separated quoted fields with an explicit all-text schema, strict parsing, and `force_not_null` for every source column. Some 2018 and 2020 BU rows contain unescaped quote marks inside candidate names. On those two election cycles the collector normalizes every file, repairs only quote marks that cannot be field terminators, retains them in the parsed name, and records the number of repairs per member as `csv_unescaped_quote_repairs`; files with no such cases receive zero repairs. Strict parsing stays enabled after this compatibility step, and malformed records are not skipped. **Empty strings remain empty strings**; `#NULO#`, `-1`, leading zeroes and duplicates remain source values. Two provenance columns identify the outer source ZIP and its local SHA-512. ZSTD compression is used. These settings differ from the original 2026 analytical pipeline's documented empty-to-NULL convention; see the [transparency guide](parquet-transparency.md).

ZIPs inside supplementary bundles are visited recursively without extracting arbitrary archive paths to the filesystem. When the parent ZIP contains an inner ZIP's `.sha512` or `.sha1`, that checksum is verified before conversion. The outer bundle may have no checksum resource listed in the catalog; that absence is explicit rather than called a successful published-hash verification. The collector records a local SHA-512 for every outer ZIP regardless. Historical published SHA-1 is used only as the source's integrity checksum; it is not represented as modern cryptographic proof of authenticity. Nesting depth and memory bounds are enforced.

Catalog year/electoral cycle and actual election date are different fields. A supplemental bundle catalogued under 2024 can contain events held in 2025 or 2026; original `ANO_ELEICAO`, `DT_PLEITO` and `NR_TURNO` values remain unchanged. Supplementary bundles may contain multiple events/rounds. Folder names describe catalog partitions and do not replace event IDs or dates.

## Validation and reporting

For each member the collector compares parsed source and Parquet row counts, original-column order/names, and two order-independent summaries over all original values: the sum and XOR of DuckDB row hashes. The multiplicity of duplicate rows contributes to these diagnostics. These comparisons use the same parsing/query engine and are **not an independent implementation or a collision-free mathematical proof**. An exact audit can compare full row multisets with `EXCEPT ALL` in both directions. File hashes identify bytes, while fingerprints compare logical parsed records under the stated convention.

The source and output hashes, row counts, source member, schema, sizes and diagnostic result remain in each local package JSON and the public report. An empty CSV can produce a valid zero-row Parquet; this does not establish that a contest existed. Original packages are retained. Unknown schemas, bad hashes and malformed tables are reported as failures without silently discarding rows. Reruns resume from completed metadata; they do not independently re-hash all existing derived outputs. Download/conversion success does not establish complete electoral-section coverage or legal official totalization.
