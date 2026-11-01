# Decisions and open work

## D001 — Public, independent project

User direction: publish a new repository named `eleicoes`, with English and Brazilian Portuguese documentation, no infrastructure or credentials, for public reuse. Separate from Chegada.net. Public source manifests and scripts are included; national raw data remain downloadable from the TSE rather than committed to Git. Rehosting large derived datasets requires a separate distribution decision.

## D002 — Organize by year and round

User direction: support past elections with separate folders for each year and round. Use English identifiers consistently: `data/<year>/round-<n>/`. Preserve election/event IDs inside each partition so simultaneous contests do not mix. Historical adapters must validate schema differences; only 2026 is currently processed.

## D003 — Local analytical preparation

Problem: source CSVs exceed comfortable spreadsheet limits and contain repeated turnout values. Alternatives: direct CSV dashboard queries; load everything into a hosted database; prepare compressed local analytical files. Current implementation uses lossless Parquet plus local DuckDB to validate and query the data reproducibly. This reduces repeated parsing and avoids a hosting commitment. Operational cost: disk space, derived files tied to local paths, regeneration when moving the database, and review of schema adapters. It is a local preparation choice, not approval of a production architecture.

## Open work

- Reconcile observed BUs against expected section rosters and official aggregate snapshots.
- Review the two overseas zero-vote placeholder rows using authoritative section status.
- Enrich candidate display names with registration IDs and full names.
- Map overseas localities to countries and TSE municipalities to IBGE geography.
- Source map boundaries and available polling-place coordinates with attribution.
- Add historical election catalogs/adapters and per-year validation evidence.
- Build and test a responsive public dashboard; decide hosting and large-data distribution separately.
