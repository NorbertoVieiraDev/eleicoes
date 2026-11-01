# Historical BU discovery and raw Parquet conversion

## Scope of “all available elections”

The 2026-11-01 official catalog search for `boletim` returned 11 datasets with **425 tabular BU ZIP resources**: regular 2012, 2014, 2016, 2018, 2020, 2022, 2024 and 2026 elections, plus supplementary BU bundles under the 2020, 2022 and 2024 catalog cycles. This is a catalog snapshot, not a claim that every election ever held has downloadable BU files. Candidate registers, finance, electorate, binary urn archives, logs and RDVs are outside this BU conversion scope.

The resource counts are 46, 56, 46, 56, 54, 56, 52 and 56 for the respective regular years, plus three supplementary outer ZIPs. Municipal-election coverage differs from general elections; missing second-round contests must not be invented. All 425 ZIP URLs responded HTTP 200 in the initial HEAD probe, totaling approximately 13.78 GB of reported compressed size. Successful HEAD probes are not proof of completed downloads or conversions; use the final conversion report.

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

The collector decodes Latin-1 into temporary UTF-8 and parses semicolon-separated quoted fields with an explicit all-text schema, strict parsing, and `force_not_null` for every source column. **Empty strings remain empty strings**; `#NULO#`, `-1`, leading zeroes and duplicates remain source values. Two provenance columns identify the outer source ZIP and its local SHA-512. ZSTD compression is used. These settings differ from the original 2026 analytical pipeline's documented empty-to-NULL convention; see the [transparency guide](parquet-transparency.md).

ZIPs inside supplementary bundles are visited recursively without extracting arbitrary archive paths to the filesystem. When the parent ZIP contains an inner ZIP's `.sha512` or `.sha1`, that checksum is verified before conversion. The outer bundle may have no checksum resource listed in the catalog; that absence is explicit rather than called a successful published-hash verification. The collector records a local SHA-512 for every outer ZIP regardless. Historical published SHA-1 is used only as the source's integrity checksum; it is not represented as modern cryptographic proof of authenticity. Nesting depth and memory bounds are enforced.

Catalog year/electoral cycle and actual election date are different fields. A supplemental bundle catalogued under 2024 can contain events held in 2025 or 2026; original `ANO_ELEICAO`, `DT_PLEITO` and `NR_TURNO` values remain unchanged. Supplementary bundles may contain multiple events/rounds. Folder names describe catalog partitions and do not replace event IDs or dates.

## Validation and reporting

For each member the collector compares parsed source and Parquet row counts, original-column order/names, and two order-independent summaries over all original values: the sum and XOR of DuckDB row hashes. The multiplicity of duplicate rows contributes to these diagnostics. These comparisons use the same parsing/query engine and are **not an independent implementation or a collision-free mathematical proof**. An exact audit can compare full row multisets with `EXCEPT ALL` in both directions. File hashes identify bytes, while fingerprints compare logical parsed records under the stated convention.

The source and output hashes, row counts, source member, schema, sizes and diagnostic result remain in each local package JSON and the public report. An empty CSV can produce a valid zero-row Parquet; this does not establish that a contest existed. Original packages are retained. Unknown schemas, bad hashes and malformed tables are reported as failures without silently discarding rows. Reruns resume from completed metadata; they do not independently re-hash all existing derived outputs. Download/conversion success does not establish complete electoral-section coverage or legal official totalization.
