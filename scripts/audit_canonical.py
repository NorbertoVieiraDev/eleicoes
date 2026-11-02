"""Summarize field availability in the local, harmonized Parquet outputs."""
import hashlib
import json
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def sha512(path):
    h = hashlib.sha512()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit_table(con, table_name, fields):
    paths = sorted((ROOT / "derived/canonical").glob(f"{table_name}-*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No {table_name} canonical Parquet files found")
    path_sql = "[" + ",".join(q(p) for p in paths) + "]"
    null_metrics = ",\n".join(f"count({field}) AS {field}_non_null" for field in fields)
    rows = con.execute(f"""SELECT catalog_cycle, election_year, source_basis, source_granularity,
        count(*)::BIGINT AS row_count,
        count(DISTINCT source_package)::BIGINT AS source_packages,
        {null_metrics}
      FROM read_parquet({path_sql}, union_by_name=true)
      GROUP BY ALL ORDER BY ALL""").fetchall()
    columns = [x[0] for x in con.description]
    results = []
    for row in rows:
        item = dict(zip(columns, row))
        total = int(item["row_count"])
        coverage = {}
        for field in fields:
            present = int(item.pop(f"{field}_non_null"))
            coverage[field] = {"non_null_rows": present, "null_rows": total - present,
                               "available_percent": round(100 * present / total, 4) if total else 0.0}
        item["row_count"] = total
        item["source_packages"] = int(item["source_packages"])
        item["field_coverage"] = coverage
        results.append(item)
    files = [{"file": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha512": sha512(p)} for p in paths]
    return {"groups": results, "files": files,
            "rows": sum(x["row_count"] for x in results), "files_count": len(files)}


def main():
    out = ROOT / "derived/canonical/duckdb-tmp"
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'; SET threads=2")
    con.execute("SET temp_directory=" + q(out))
    report = {
        "scope": "Local canonical Parquet field coverage by catalog cycle and source basis",
        "interpretation": "NULL counts include source markers documented as null/not recorded and fields unavailable in the source layout; use the raw source member and historical-data documentation to distinguish them. Zero values remain zero.",
        "votes": audit_table(con, "votes", ["country_code", "state_code", "municipality_code", "zone_number",
            "section_number", "voting_location_code", "urn_number", "office_code", "candidate_number",
            "candidate_name", "vote_type_code", "election_type_code", "urn_type_code", "aggregated_sections",
            "bu_issued_at", "bu_received_at", "votes"]),
        "sections": audit_table(con, "sections", ["country_code", "state_code", "municipality_code", "zone_number",
            "section_number", "voting_location_code", "urn_number", "eligible_electors", "attendance", "absentees",
            "nominal_votes", "blank_votes", "null_votes", "legend_votes", "annulled_votes"]),
    }
    con.close()
    report_path = ROOT / "reports/history/canonical-coverage.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: {"rows": v["rows"], "files": v["files_count"]} for k, v in report.items() if k in {"votes", "sections"}}))


if __name__ == "__main__":
    main()
