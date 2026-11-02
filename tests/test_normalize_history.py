import datetime
import pathlib
import tempfile
import unittest
import zipfile

import duckdb

from scripts.normalize_history import clean_expr, date_expr, names_for_year, pad_code, write_legacy_csv


class NormalizeHistoryTests(unittest.TestCase):
    def test_2012_positional_bu_layout(self):
        columns = [f"field_{i:03d}" for i in range(1, 33)]
        mapping = names_for_year(2012, columns)
        self.assertEqual(mapping["event"], "field_003")
        self.assertEqual(mapping["candidate"], "field_023")
        self.assertEqual(mapping["votes"], "field_025")
        self.assertEqual(mapping["urn"], "field_027")
        self.assertEqual(mapping["urn_type"], "field_021")
        self.assertEqual(mapping["bu_received"], "field_015")

    def test_2014_positional_bu_layout(self):
        columns = [f"field_{i:03d}" for i in range(1, 32)]
        mapping = names_for_year(2014, columns)
        self.assertEqual(mapping["candidate"], "field_022")
        self.assertEqual(mapping["votes"], "field_024")
        self.assertEqual(mapping["urn"], "field_026")
        self.assertEqual(mapping["party"], "field_011")

    def test_header_aliases_ignore_internal_spaces(self):
        mapping = names_for_year(2018, ["ANO_ELEICAO", "SG_ UF", "NR_VOTAVEL", "QT_VOTOS"])
        self.assertEqual(mapping["state"], "SG_ UF")
        self.assertEqual(mapping["candidate"], "NR_VOTAVEL")
        self.assertEqual(mapping["votes"], "QT_VOTOS")

    def test_documented_missing_markers_become_null_but_zero_survives(self):
        con = duckdb.connect()
        expr = clean_expr("value", "BIGINT")
        rows = con.execute(
            f"SELECT {expr} FROM (VALUES ('0'), ('-1'), ('-3'), ('#NULO'), ('#NE'), ('')) t(value)"
        ).fetchall()
        con.close()
        self.assertEqual(rows, [(0,), (None,), (None,), (None,), (None,), (None,)])

    def test_location_codes_are_padded_without_changing_non_numeric_codes(self):
        con = duckdb.connect()
        expr = pad_code("code", 4)
        rows = con.execute(f"SELECT {expr} FROM (VALUES ('5'), ('0057'), ('ZZ'), (NULL)) t(code)").fetchall()
        con.close()
        self.assertEqual(rows, [("0005",), ("0057",), ("ZZ",), (None,)])

    def test_event_date_accepts_iso_and_brazilian_date_text(self):
        con = duckdb.connect()
        expr = date_expr("value")
        rows = con.execute(f"SELECT {expr} FROM (VALUES ('2018-10-07'), ('07/10/2018'), ('')) t(value)").fetchall()
        con.close()
        self.assertEqual(rows, [(datetime.date(2018, 10, 7),), (datetime.date(2018, 10, 7),), (None,)])

    def test_2010_headerless_overseas_member_gets_explicit_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            tempdir = pathlib.Path(temp)
            archive = tempdir / "votacao_secao_2010_ZZ.zip"
            row = '"28/07/2016";"19:05:06";"2010";"1";"ELEICOES 2010";"ZZ";"ZZ";"29807";"HOUSTON-EUA";"1";"485";"1";"PRESIDENTE";"28";"2"\n'
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("votacao_secao_2010_ZZ.txt", row)
            resource = {"year": 2010, "area_code": "ZZ", "kind": "section_votes", "filename": archive.name}
            adapter_con = duckdb.connect()
            scratch, member = write_legacy_csv(adapter_con, resource, archive, tempdir)
            adapter_con.close()
            con = duckdb.connect()
            result = con.execute(f"SELECT count(*), any_value(SG_UF) FROM read_csv('{scratch}', delim=';', header=true, all_varchar=true)").fetchone()
            con.close()
            self.assertEqual(member, "votacao_secao_2010_ZZ.txt")
            self.assertEqual(result, (1, "ZZ"))


if __name__ == "__main__":
    unittest.main()
