# Project guide

## Purpose

Provide publicly reusable election data acquisition and analysis, followed by an interactive website with candidate search, territorial navigation, maps and charts. The project has downloaded the 425 cataloged tabular BU ZIPs for 2012–2026 cycles and supplementary contests, and 170 official section-result ZIPs for 2000–2010. Local canonical Parquets contain 637,673,681 vote rows and 16,849,380 section/urn summary rows across the covered cycles. See the [historical data report](historical-data.md), [package-level BU evidence](../../reports/history/conversion-records.json), [download report](../../reports/history/legacy-results-downloads.json), and [field coverage audit](../../reports/history/canonical-coverage.json). The interface defaults to Brazilian Portuguese; code identifiers and tooling use English.

## Reproduction

Follow the root quick start. `download.py --year 2026 --round 1` downloads one round; omitting `--round` downloads both. Files resume with `.part`; existing complete files are checked against the versioned SHA-512. A mismatch stops processing and preserves the file for investigation. Do not delete the source file to hide a failure.

`prepare.py --year 2026` converts one package at a time from Latin-1 CSV into UTF-8 and then lossless text-column Parquet. Each source checksum is checked before conversion. Strict CSV parsing rejects malformed records rather than silently skipping them. The UTF-8 scratch copy is removed after each package. The local database references Parquet files; keep the derived directory in place, or rerun preparation after moving it. Rerunning reuses outputs with the current pipeline version and matching source identity; it does not independently hash previously generated derived files.

Optional `--raw-dir /path/to/existing/bu` reuses an existing flat collection without moving or duplicating original ZIPs. Do not commit local absolute paths.

## Querying

```python
import duckdb
con = duckdb.connect('derived/2026/elections.duckdb', read_only=True)
rows = con.execute('''
    SELECT state, municipality_name, zone_number, section_number, votes
    FROM votes
    WHERE election_id = ? AND office_code = ?
      AND votable_type = '1' AND votable_number = ?
      AND state = ? AND municipality_code = ?
    ORDER BY zone_number, section_number
''', ['6257', '1', '13', 'SP', '71072']).fetchall()
```

Use parameterized queries in applications. Use `candidates` for BU display-name search and `candidate_municipality` / `candidate_state` for common aggregate charts. Any percentage must state its denominator (all ballots, nominal votes, or another explicit measure). National aggregations of state-specific offices do not represent a single national contest.

## Status and development

See `reports/2026/` and `reports/history/` for generated evidence and [methodology](methodology.md) for interpretation. The canonical cross-election outputs are local and excluded from Git because of their size. Results from 2000–2010 are post-totalization section data without urn numbers; BU records begin in 2012. Independent expected-section and official-total reconciliation remain pending, and no hosted dashboard or national dataset is published. Development follows issue → branch → commit → PR → review and tests → approved promotion. A local test run is not a deployment approval. No deployment or infrastructure configuration belongs in this public repository.

## Roadmap

1. Validate 2026 source rows, key uniqueness and section/office balances.
2. Reconcile against an independent expected-section roster and official aggregate results, preserving snapshot dates and legal vote-destination differences.
3. Acquire candidate registers and official geographical crosswalks; add country mapping, boundaries and available voting-location coordinates.
4. Build the responsive portal with a gray background and red/orange/yellow accents. No live public site exists yet.
5. Review cross-election schema adapters and territorial/candidate mappings before building combined historical analytics.
6. Evaluate separate distribution for large public derived datasets; no dataset hosting decision has been made.
