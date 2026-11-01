# Methodology and data model

Read the [CSV-to-Parquet transformation and reproducibility guide](parquet-transparency.md).

## Provenance and layers

Versioned manifests identify official ZIP URLs, published SHA-512 values, source sizes and archive members. Local originals are immutable references. The raw Parquet layer preserves the CSV columns as text and adds `source_package` and `source_sha512`. The analytical `votes` view casts quantities strictly and pads electoral municipality (5), zone (4) and section (4) identifiers. The effective urn number remains text.

Derived files and databases are local, rebuildable artifacts, not infrastructure definitions. DuckDB is used for local preparation and validation only; this does not prescribe a production hosting architecture.

## Grains and keys

- `votes`: one source vote row, identified analytically by election/event, year, round, UF, electoral municipality, zone, section, office, votable type, votable number and party. Source duplicates remain visible; they are not silently removed.
- `section_office`: one record per election/event, UF, municipality, zone, section and office. Min/max values detect repeated metadata disagreements. Never sum turnout or eligible voters over candidate rows or across offices.
- `section_quality`: metadata-consistency flag, eligible = turnout + abstentions, and a diagnostic comparison of vote totals to expected ballot opportunities. The 2026 first-round Senate diagnostic uses two choices per voter; other offices use one. This is a diagnostic, not a legal determination or a rule for historical years.
- `candidate_municipality` and `candidate_state`: sums of recorded BU votes at the respective territorial level, retaining election, office, type and number. A type of `1` selects nominal candidates. Blank/null and party-list votes remain separate.
- `candidates`: distinct BU display-name/number/party combinations. Presidency uses the national constituency; state offices retain UF. Names/party aliases remain distinct rather than silently selecting one. This is not a full candidate-registration directory.
- `territories`: unique electoral municipality/locality records; domestic country is BR, overseas country stays unknown until mapped.

Turnout aggregates only use section/office records with consistent repeated metadata. Conflicts must remain visible in reports; missing values must not be presented as zero or complete totals.

## Aggregated sections and physical urns

An aggregated section shares the principal section's BU. Preserve its listed relation; do not distribute the principal's votes across subordinate sections or create additional vote facts. The current version retains `aggregated_sections` as published text and builds `section_aliases` for lookup from a listed subordinate section to its principal. Join on the full election/event, territory and office key, and use the principal BU once; the bridge must never multiply votes. Conflicting aliases are counted in the validation report. A physical urn identifier is not a globally unique election section key and must not be used as the sole join key.

## Coverage and checks

Package coverage is 28 territories × 2 rounds for 2026. Section counts are observed source coverage, not proof that every expected section is present. Checks measure duplicate vote keys, negative vote quantities, metadata disagreements and section/office balances. No failed row is silently discarded or treated as verified. Published tabular BU votes may differ from legally adjusted official totalization; reconciliation must account for snapshots, annulments, vote destination, substitutions and special contests.

Overseas locality names do not establish a country code. TSE municipality codes are not IBGE geometry codes. Maps need a reviewed crosswalk; polling-place points need independently sourced coordinates. Do not infer individual voter choices from BU aggregates or operational logs.

## Source placeholders

Two second-round source rows use `-1`/`#NULO#` for office and votable, with zero votes. They are retained in raw data, `votes` and section profiles, and counted separately. Candidate and territory aggregates exclude nonpositive office/votable codes. Consequently source-section counts and contest-section counts differ; neither is an independent expected-section census.
