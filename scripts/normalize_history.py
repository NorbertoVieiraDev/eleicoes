"""Build BI-ready cross-year vote and section Parquet tables from verified TSE sources.

Raw downloads and intermediate Parquets remain local and are excluded from Git.
"""
import argparse
import csv
import hashlib
import io
import json
import pathlib
import re
import shutil
import zipfile

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION = 1

VOTE_COLUMNS = [
    "election_year", "catalog_cycle", "round", "election_id", "event_id", "event_name", "event_date",
    "election_type_code", "election_type_name", "vote_origin_name", "urn_type_code", "urn_type_name",
    "source_basis", "source_granularity", "source_scope", "country_code", "state_code",
    "municipality_code", "municipality_name", "zone_number", "section_number",
    "voting_location_code", "urn_number", "office_code", "office_name", "party_number",
    "party_name", "candidate_number", "candidate_name", "vote_type_code", "vote_type_name",
    "aggregated_sections", "bu_issued_at", "bu_received_at",
    "votes", "eligible_electors", "attendance", "absentees", "source_package", "source_member", "source_url", "source_sha512",
]

SECTION_COLUMNS = [
    "election_year", "catalog_cycle", "round", "election_id", "event_id", "source_basis", "source_granularity",
    "source_scope", "country_code", "state_code", "municipality_code", "municipality_name",
    "zone_number", "section_number", "voting_location_code", "urn_number", "eligible_electors",
    "attendance", "absentees", "nominal_votes", "blank_votes", "null_votes", "legend_votes",
    "annulled_votes", "source_package", "source_member", "source_url", "source_sha512",
]


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def sha512(path):
    h = hashlib.sha512()
    with pathlib.Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ident(value):
    return '"' + str(value).replace('"', '""') + '"'


def clean_expr(name, cast=None):
    if not name:
        return "NULL" if cast != "VARCHAR" else "CAST(NULL AS VARCHAR)"
    value = f"NULLIF(NULLIF(NULLIF(NULLIF(trim(CAST({ident(name)} AS VARCHAR)), ''), '#NULO'), '#NE'), '-1')"
    value = f"NULLIF({value}, '-3')"
    return f"try_cast({value} AS {cast})" if cast else value


def pad_code(expression, width):
    return f"CASE WHEN regexp_full_match({expression}, '[0-9]{{1,{width}}}') THEN lpad({expression}, {width}, '0') ELSE {expression} END"


def date_expr(name):
    if not name: return "NULL::DATE"
    value = clean_expr(name)
    return f"coalesce(try_cast({value} AS DATE), try_strptime({value}, '%d/%m/%Y')::DATE)"


def names_for_year(year, columns):
    if columns and columns[0].startswith("field_"):
        base = {"year": None, "election": "field_004", "uf": "field_005",
                "office": "field_006", "office_name": "field_007", "zone": "field_008",
                "section": "field_009", "location": "field_010", "party": "field_011",
                "party_name": "field_012", "municipality": "field_013", "municipality_name": "field_014",
                "eligible": "field_016", "absentees": "field_017", "attendance": "field_018",
                "election_type": "field_019", "vote_origin_name": "field_020",
                "vote_type": "field_026", "vote_type_name": None}
        if year == 2012:
            base.update(event="field_003", election="field_004", office="field_006", office_name="field_007",
                        candidate="field_023", candidate_name="field_024", votes="field_025",
                        vote_type="field_026", vote_type_name=None, urn="field_027", urn_type="field_021",
                        urn_type_name="field_022", aggregated_sections=None, bu_received="field_015", bu_issued=None)
        else:
            base.update(event="field_003", election="field_004", office="field_006", office_name="field_007",
                        candidate="field_022", candidate_name="field_023", votes="field_024",
                        vote_type="field_025", vote_type_name=None, urn="field_026", urn_type="field_020",
                        urn_type_name="field_021", vote_origin_name=None, aggregated_sections=None,
                        bu_received="field_015", bu_issued=None)
        base.update(round=None, event_name=None, event_date=None, party=None, zone="field_008", section="field_009",
                    location="field_010", municipality="field_013", municipality_name="field_014",
                    state="field_005", year=None, source_scope=None)
        base.update(party="field_011", party_name="field_012")
        return base
    # TSE changed the spelling of a few columns over the years. Normalize names only for lookup.
    by_upper = {c.upper().replace(" ", ""): c for c in columns}
    aliases = {
        "year": ["ANO_ELEICAO"], "round": ["NR_TURNO"], "election": ["CD_ELEICAO"],
        "event": ["CD_PLEITO"], "event_name": ["DS_ELEICAO"], "event_date": ["DT_PLEITO", "DT_ELEICAO"],
        "election_type": ["CD_TIPO_ELEICAO"], "election_type_name": ["NM_TIPO_ELEICAO"],
        "urn_type": ["CD_TIPO_URNA"], "urn_type_name": ["DS_TIPO_URNA"],
        "state": ["SG_UF"], "municipality": ["CD_MUNICIPIO"], "municipality_name": ["NM_MUNICIPIO"],
        "zone": ["NR_ZONA"], "section": ["NR_SECAO"], "location": ["NR_LOCAL_VOTACAO"],
        "urn": ["NR_URNA_EFETIVADA"], "office": ["CD_CARGO_PERGUNTA", "CD_CARGO"],
        "office_name": ["DS_CARGO_PERGUNTA", "DS_CARGO"], "party": ["NR_PARTIDO"],
        "party_name": ["NM_PARTIDO", "SG_PARTIDO"], "candidate": ["NR_VOTAVEL"],
        "candidate_name": ["NM_VOTAVEL"], "vote_type": ["CD_TIPO_VOTAVEL"],
        "vote_type_name": ["DS_TIPO_VOTAVEL"], "votes": ["QT_VOTOS"],
        "eligible": ["QT_APTOS"], "attendance": ["QT_COMPARECIMENTO"],
        "absentees": ["QT_ABSTENCOES"], "aggregated_sections": ["DS_SECOES_AGREGADAS", "DS_AGREGADAS"],
        "bu_issued": ["DT_EMISSAO_BU"], "bu_received": ["DT_BU_RECEBIDO"], "vote_origin_name": [], "source_scope": [],
    }
    result = {}
    for key, candidates in aliases.items():
        result[key] = next((by_upper[x.replace(" ", "")] for x in candidates if x.replace(" ", "") in by_upper), None)
    result["vote_type_name"] = next((by_upper[x] for x in ("DS_TIPO_VOTAVEL",) if x in by_upper), None)
    return result


def canonical_select(path, year, metadata, member):
    columns = member["columns"]
    m = names_for_year(year, columns)
    src = f"read_parquet({q(ROOT / member['parquet_file'])})"
    def e(key, cast=None):
        return clean_expr(m.get(key), cast or "VARCHAR")
    round_value = e("round", "INTEGER") if m.get("round") else str(metadata.get("round") or 1)
    values = {
        "election_year": e("year", "INTEGER") if m.get("year") else str(year), "catalog_cycle": str(metadata["year"]), "round": round_value,
        "election_id": e("election", "VARCHAR"), "event_id": e("event", "VARCHAR"),
        "event_name": e("event_name", "VARCHAR"), "event_date": date_expr(m.get("event_date")),
        "election_type_code": e("election_type"), "election_type_name": e("election_type_name"),
        "vote_origin_name": e("vote_origin_name"), "urn_type_code": e("urn_type"), "urn_type_name": e("urn_type_name"),
        "source_basis": q("boletim_de_urna"), "source_granularity": q("urn_section"),
        "source_scope": q(metadata.get("scope", "unknown")), "country_code": "CASE WHEN " + e("state") + " IS NOT NULL AND " + e("state") + " NOT IN ('ZZ','VT') THEN 'BR' END",
        "state_code": e("state"), "municipality_code": pad_code(e("municipality"), 5), "municipality_name": e("municipality_name"),
        "zone_number": pad_code(e("zone"), 4), "section_number": pad_code(e("section"), 4), "voting_location_code": e("location"),
        "urn_number": e("urn"), "office_code": e("office"), "office_name": e("office_name"),
        "party_number": e("party"), "party_name": e("party_name"), "candidate_number": e("candidate"),
        "candidate_name": e("candidate_name"), "vote_type_code": e("vote_type"),
        "vote_type_name": e("vote_type_name"), "aggregated_sections": e("aggregated_sections"),
        "bu_issued_at": e("bu_issued"), "bu_received_at": e("bu_received"), "votes": e("votes", "BIGINT"),
        "eligible_electors": e("eligible", "BIGINT"), "attendance": e("attendance", "BIGINT"),
        "absentees": e("absentees", "BIGINT"),
        "source_package": q(metadata["source_package"]), "source_member": q(member["source_member"]),
        "source_url": q(metadata["source_url"]), "source_sha512": q(metadata["source_sha512"]),
    }
    select = ",".join(f"{values[c]} AS {ident(c)}" for c in VOTE_COLUMNS)
    return f"SELECT {select} FROM {src}"


def write_legacy_csv(con, resource, archive_path, outdir):
    """Convert a selected CSV member into UTF-8 scratch, retaining the raw ZIP unchanged."""
    with zipfile.ZipFile(archive_path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv") or (resource["year"] == 2010 and resource.get("area_code") in {"ZZ", "VT"} and n.lower().endswith(".txt"))]
        if resource["kind"] == "section_totals":
            members = [n for n in members if pathlib.PurePosixPath(n).name.upper().endswith("BRASIL.CSV")]
        if resource["kind"] == "section_votes":
            members = [n for n in members if not pathlib.PurePosixPath(n).name.upper().endswith("BRASIL.CSV")]
        if len(members) != 1:
            raise ValueError(f"Expected one canonical CSV member in {resource['filename']}; found {members[:4]}")
        member_name = members[0]
        scratch = outdir / (re.sub(r"[^A-Za-z0-9_.-]", "_", resource["filename"]) + ".utf8.csv")
        with io.TextIOWrapper(z.open(member_name), encoding="latin-1", newline="") as src, scratch.open("w", encoding="utf-8", newline="") as dst:
            if resource["year"] == 2010 and resource.get("area_code") in {"ZZ", "VT"} and member_name.lower().endswith(".txt"):
                expected_header = "DT_GERACAO;HH_GERACAO;ANO_ELEICAO;NR_TURNO;DS_ELEICAO;SG_UF;SG_UE;CD_MUNICIPIO;NM_MUNICIPIO;NR_ZONA;NR_SECAO;CD_CARGO;DS_CARGO;NR_VOTAVEL;QT_VOTOS".split(";")
                writer = csv.writer(dst, delimiter=";", quotechar='"', lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
                writer.writerow(expected_header)
                for row_number, row in enumerate(csv.reader(src, delimiter=";", quotechar='"'), start=2):
                    if len(row) != len(expected_header):
                        raise ValueError(f"2010 {resource['area_code']} row {row_number} has {len(row)} columns; expected 15")
                    writer.writerow(row)
            else:
                shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
    return scratch, member_name


def legacy_projection(con, scratch, resource, metadata, member_name):
    cols = [x[0] for x in con.execute(f"DESCRIBE SELECT * FROM read_csv({q(scratch)}, delim=';', header=true, all_varchar=true, encoding='utf-8')").fetchall()]
    m = names_for_year(resource["year"], cols)
    def e(key, cast=None): return clean_expr(m.get(key), cast or "VARCHAR")
    basis = "official_section_result"
    vals = {
        "election_year": str(resource["year"]), "catalog_cycle": str(resource["year"]), "round": e("round", "INTEGER") if m.get("round") else "1",
        "election_id": e("election", "VARCHAR"), "event_id": e("event", "VARCHAR"),
        "event_name": e("event_name", "VARCHAR"), "event_date": date_expr(m.get("event_date")),
        "election_type_code": e("election_type"), "election_type_name": e("election_type_name"),
        "vote_origin_name": e("vote_origin_name"), "urn_type_code": e("urn_type"), "urn_type_name": e("urn_type_name"),
        "source_basis": q(basis), "source_granularity": q("section"), "source_scope": q(resource["scope"]),
        "country_code": "CASE WHEN " + e("state") + " IS NOT NULL AND " + e("state") + " NOT IN ('ZZ','VT') THEN 'BR' END",
        "state_code": e("state"), "municipality_code": pad_code(e("municipality"), 5), "municipality_name": e("municipality_name"),
        "zone_number": pad_code(e("zone"), 4), "section_number": pad_code(e("section"), 4), "voting_location_code": e("location"),
        "urn_number": "CAST(NULL AS VARCHAR)", "office_code": e("office"), "office_name": e("office_name"),
        "party_number": "CAST(NULL AS VARCHAR)", "party_name": "CAST(NULL AS VARCHAR)", "candidate_number": e("candidate"),
        "candidate_name": e("candidate_name"), "vote_type_code": "CAST(NULL AS VARCHAR)", "vote_type_name": "CAST(NULL AS VARCHAR)",
        "aggregated_sections": "CAST(NULL AS VARCHAR)", "bu_issued_at": "CAST(NULL AS VARCHAR)", "bu_received_at": "CAST(NULL AS VARCHAR)",
        "votes": e("votes", "BIGINT"), "eligible_electors": "NULL", "attendance": "NULL", "absentees": "NULL",
        "source_package": q(resource["filename"]),
        "source_member": q(member_name), "source_url": q(resource["url"]),
        "source_sha512": q(metadata["source_sha512"]),
    }
    sql = ",".join(f"{vals[c]} AS {ident(c)}" for c in VOTE_COLUMNS)
    return f"SELECT {sql} FROM read_csv({q(scratch)}, delim=';', header=true, all_varchar=true, encoding='utf-8', nullstr='')"


def legacy_section_projection(con, scratch, resource, metadata, member_name):
    cols = [x[0] for x in con.execute(f"DESCRIBE SELECT * FROM read_csv({q(scratch)}, delim=';', header=true, all_varchar=true, encoding='utf-8')").fetchall()]
    by_upper = {c.upper().replace(" ", ""): c for c in cols}
    def pick(*names): return next((by_upper[n.replace(" ", "")] for n in names if n.replace(" ", "") in by_upper), None)
    def e(name, cast=None): return clean_expr(name, cast or "VARCHAR")
    vals = {
        "election_year": str(resource["year"]), "catalog_cycle": str(resource["year"]), "round": e(pick("NR_TURNO"), "INTEGER"),
        "election_id": e(pick("CD_ELEICAO")), "event_id": e(pick("CD_PLEITO")),
        "source_basis": q("official_section_result"), "source_granularity": q("section"),
        "source_scope": q("all_states"), "country_code": "CASE WHEN " + e(pick("SG_UF")) + " IS NOT NULL AND " + e(pick("SG_UF")) + " NOT IN ('ZZ','VT') THEN 'BR' END",
        "state_code": e(pick("SG_UF")), "municipality_code": pad_code(e(pick("CD_MUNICIPIO")), 5),
        "municipality_name": e(pick("NM_MUNICIPIO")), "zone_number": pad_code(e(pick("NR_ZONA")), 4),
        "section_number": pad_code(e(pick("NR_SECAO")), 4), "voting_location_code": e(pick("NR_LOCAL_VOTACAO")),
        "urn_number": "CAST(NULL AS VARCHAR)", "eligible_electors": e(pick("QT_APTOS"), "BIGINT"),
        "attendance": e(pick("QT_COMPARECIMENTO"), "BIGINT"), "absentees": e(pick("QT_ABSTENCOES"), "BIGINT"),
        "nominal_votes": e(pick("QT_VOTOS_NOMINAIS"), "BIGINT"), "blank_votes": e(pick("QT_VOTOS_BRANCOS"), "BIGINT"),
        "null_votes": e(pick("QT_VOTOS_NULOS"), "BIGINT"), "legend_votes": e(pick("QT_VOTOS_LEGENDA"), "BIGINT"),
        "annulled_votes": e(pick("QT_VOTOS_ANULADOS_APU_SEP"), "BIGINT"),
        "source_package": q(resource["filename"]), "source_member": q(member_name),
        "source_url": q(resource["url"]), "source_sha512": q(metadata["source_sha512"]),
    }
    sql = ",".join(f"{vals[c]} AS {ident(c)}" for c in SECTION_COLUMNS)
    return f"SELECT {sql} FROM read_csv({q(scratch)}, delim=';', header=true, all_varchar=true, encoding='utf-8', nullstr='')"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=2000)
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--legacy-only", action="store_true")
    args = ap.parse_args()
    outroot = ROOT / "derived" / "canonical"
    outroot.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'; SET threads=2")
    temp_dir = outroot / "duckdb-tmp"
    temp_dir.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory={q(temp_dir)}")
    inventory = json.loads((ROOT / "data/catalog/legacy-results-2000-2010.json").read_text())
    legacy_status = []
    for year in range(max(2000, args.from_year), min(2010, args.to_year) + 1):
        resources = [r for r in inventory["resources"] if r["year"] == year and r.get("canonical_include") and r["kind"] == "section_votes"]
        sqls = []
        scratch_files = []
        for resource in resources:
            archive = ROOT / "data" / str(year) / "results" / "raw" / resource["filename"]
            meta_path = archive.with_name(archive.name + ".json")
            if not archive.exists() or not meta_path.exists():
                legacy_status.append({"year": year, "source_package": resource["filename"], "status": "missing_download"})
                continue
            meta = json.loads(meta_path.read_text())
            if sha512(archive) != meta["source_sha512"]:
                raise ValueError(f"Legacy source SHA-512 mismatch: {resource['filename']}")
            scratch_dir = outroot / "scratch"
            scratch_dir.mkdir(exist_ok=True)
            scratch, member_name = write_legacy_csv(con, resource, archive, scratch_dir)
            scratch_files.append(scratch)
            sqls.append(legacy_projection(con, scratch, resource, meta, member_name))
        if sqls:
            target = outroot / f"votes-{year}.parquet"
            temp = target.with_suffix(".parquet.part")
            con.execute(f"COPY ({' UNION ALL '.join(sqls)}) TO {q(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)")
            temp.replace(target)
            row_count = con.execute(f"SELECT count(*) FROM read_parquet({q(target)})").fetchone()[0]
        else: row_count = 0
        for scratch in scratch_files: scratch.unlink(missing_ok=True)
        legacy_status.append({"year": year, "status": "normalized" if sqls else "no_verified_sources", "vote_rows": row_count,
                             "source_packages": len(sqls), "parquet_file": str(target.relative_to(ROOT)) if sqls else None,
                             "parquet_bytes": target.stat().st_size if sqls else 0})

        section_resources = [r for r in inventory["resources"] if r["year"] == year and r.get("canonical_include") and r["kind"] == "section_totals"]
        section_sqls = []
        section_missing = []
        for resource in section_resources:
            archive = ROOT / "data" / str(year) / "results" / "raw" / resource["filename"]
            meta_path = archive.with_name(archive.name + ".json")
            if not archive.exists() or not meta_path.exists():
                section_missing.append(resource["filename"])
                continue
            meta = json.loads(meta_path.read_text())
            if sha512(archive) != meta["source_sha512"]:
                raise ValueError(f"Legacy source SHA-512 mismatch: {resource['filename']}")
            scratch_dir = outroot / "scratch"; scratch_dir.mkdir(exist_ok=True)
            scratch, member_name = write_legacy_csv(con, resource, archive, scratch_dir)
            scratch_files.append(scratch)
            section_sqls.append(legacy_section_projection(con, scratch, resource, meta, member_name))
        section_target = outroot / f"sections-{year}.parquet"
        if section_sqls:
            temp = section_target.with_suffix(".parquet.part")
            con.execute(f"COPY ({' UNION ALL '.join(section_sqls)}) TO {q(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)")
            temp.replace(section_target)
            section_rows = con.execute(f"SELECT count(*) FROM read_parquet({q(section_target)})").fetchone()[0]
            print(f"SECTIONS {year}: {section_rows:,} rows", flush=True)
        else: section_rows = 0
        legacy_status[-1].update(section_rows=section_rows, section_source_packages=len(section_sqls),
                                 section_missing_downloads=section_missing,
                                 section_parquet_file=str(section_target.relative_to(ROOT)) if section_sqls else None,
                                 section_parquet_bytes=section_target.stat().st_size if section_sqls else 0)
        for scratch in scratch_files: scratch.unlink(missing_ok=True)
        print(f"LEGACY {year}: {row_count:,} rows from {len(sqls)} ZIPs", flush=True)

    bu_status = []
    if not args.legacy_only:
        for year in range(max(2012, args.from_year), args.to_year + 1):
            source_sql = []
            for meta_path in sorted((ROOT / "derived/history" / str(year)).glob("**/*.json")):
                try: meta = json.loads(meta_path.read_text())
                except Exception: continue
                if meta.get("status") != "converted": continue
                for member in meta.get("members", []):
                    if member.get("status") != "converted" or not member.get("parquet_file"): continue
                    parquet_path = ROOT / member["parquet_file"]
                    if member.get("parquet_sha512") and sha512(parquet_path) != member["parquet_sha512"]:
                        raise ValueError(f"Source Parquet SHA-512 mismatch: {member['parquet_file']}")
                    source_sql.append(canonical_select(ROOT / member["parquet_file"], year, meta, member))
            if not source_sql:
                bu_status.append({"year": year, "status": "no_converted_sources", "source_members": 0})
                continue
            target = outroot / f"votes-{year}.parquet"
            temp = target.with_suffix(".parquet.part")
            union = " UNION ALL ".join(source_sql)
            con.execute(f"COPY ({union}) TO {q(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)")
            temp.replace(target)
            row_count = con.execute(f"SELECT count(*) FROM read_parquet({q(target)})").fetchone()[0]
            null_votes = con.execute(f"SELECT count(*) FROM read_parquet({q(target)}) WHERE votes IS NULL").fetchone()[0]
            section_target = outroot / f"sections-{year}.parquet"
            section_temp = section_target.with_suffix(".parquet.part")
            con.execute(f"""COPY (
              SELECT election_year, catalog_cycle, round, election_id, event_id, source_basis, source_granularity,
                source_scope, country_code, state_code, municipality_code, municipality_name,
                zone_number, section_number, voting_location_code, urn_number,
                max(eligible_electors)::BIGINT eligible_electors, max(attendance)::BIGINT attendance,
                max(absentees)::BIGINT absentees, NULL::BIGINT nominal_votes, NULL::BIGINT blank_votes,
                NULL::BIGINT null_votes, NULL::BIGINT legend_votes, NULL::BIGINT annulled_votes,
                source_package, source_member, source_url, source_sha512
              FROM read_parquet({q(target)})
              GROUP BY ALL
            ) TO {q(section_temp)} (FORMAT PARQUET, COMPRESSION ZSTD)""")
            section_temp.replace(section_target)
            section_rows = con.execute(f"SELECT count(*) FROM read_parquet({q(section_target)})").fetchone()[0]
            bu_status.append({"year": year, "status": "normalized", "vote_rows": row_count, "null_vote_rows": null_votes,
                              "source_members": len(source_sql), "parquet_file": str(target.relative_to(ROOT)),
                              "parquet_bytes": target.stat().st_size, "section_rows": section_rows,
                              "section_parquet_file": str(section_target.relative_to(ROOT)),
                              "section_parquet_bytes": section_target.stat().st_size})
            print(f"BU {year}: {row_count:,} vote rows and {section_rows:,} section rows from {len(source_sql)} Parquet members", flush=True)

    # Include already-built legacy cycles when resuming from a later year.
    reported_legacy_years = {x["year"] for x in legacy_status if x.get("status") != "missing_download"}
    for year in range(2000, 2011):
        if year in reported_legacy_years: continue
        vote_path = outroot / f"votes-{year}.parquet"
        section_path = outroot / f"sections-{year}.parquet"
        vote_resources = [r for r in inventory["resources"] if r["year"] == year and r.get("canonical_include") and r["kind"] == "section_votes"]
        section_resources = [r for r in inventory["resources"] if r["year"] == year and r.get("canonical_include") and r["kind"] == "section_totals"]
        if vote_path.exists():
            vote_rows = con.execute(f"SELECT count(*) FROM read_parquet({q(vote_path)})").fetchone()[0]
            status = "normalized"
        else:
            vote_rows = 0
            status = "no_verified_sources" if not vote_resources else "missing_canonical_output"
        if section_path.exists():
            section_rows = con.execute(f"SELECT count(*) FROM read_parquet({q(section_path)})").fetchone()[0]
            section_bytes = section_path.stat().st_size
        else:
            section_rows = section_bytes = 0
        legacy_status.append({"year": year, "status": status, "vote_rows": vote_rows,
                              "source_packages": len(vote_resources) if vote_path.exists() else 0,
                              "parquet_file": str(vote_path.relative_to(ROOT)) if vote_path.exists() else None,
                              "parquet_bytes": vote_path.stat().st_size if vote_path.exists() else 0,
                              "section_rows": section_rows, "section_source_packages": len(section_resources) if section_path.exists() else 0,
                              "section_missing_downloads": [],
                              "section_parquet_file": str(section_path.relative_to(ROOT)) if section_path.exists() else None,
                              "section_parquet_bytes": section_bytes})

    report = {"pipeline_version": VERSION, "scope": "Canonical vote rows; 2000–2010 official section results and 2012+ BU records",
              "missing_value_policy": "Blank, #NULO, #NE, -1, and -3 become NULL where documented; zero remains zero; absent source fields remain NULL.",
              "legacy": legacy_status, "boletim_de_urna": bu_status}
    report_path = ROOT / "reports/history/normalization-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    con.close()
    print("REPORT", report_path, flush=True)


if __name__ == "__main__":
    main()
