import zipfile

import pytest

from evaluation.labels import load_label_rows


def workbook_fixture(path, content):
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{namespace}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Labels" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{namespace}"><si><t>synthetic</t></si></sst>')
        archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{namespace}"><sheetData>{content}</sheetData></worksheet>')


def test_xlsx_literals_preserve_missing_cells(tmp_path):
    path = tmp_path / "labels.xlsx"
    workbook_fixture(path, '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="C2" t="inlineStr"><is><t>no_violation</t></is></c></row>')
    before = path.read_bytes()
    assert load_label_rows(path) == [[{"cell": "A2", "value": "synthetic"}, {"cell": "C2", "value": "no_violation"}]]
    assert path.read_bytes() == before


def test_xlsx_formulas_are_not_executed(tmp_path):
    path = tmp_path / "labels.xlsx"
    workbook_fixture(path, '<row r="1"><c r="A1"><f>1+1</f><v>2</v></c></row>')
    with pytest.raises(ValueError, match="literal"):
        load_label_rows(path)
