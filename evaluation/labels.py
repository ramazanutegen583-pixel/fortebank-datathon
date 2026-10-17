"""Read literal training labels without evaluating spreadsheet formulas."""

import json
from pathlib import Path
import posixpath
import xml.etree.ElementTree as element_tree
import zipfile

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def load_label_rows(path: Path) -> list:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() != ".xlsx" or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Unsupported local label file.")
    with zipfile.ZipFile(path) as archive:
        def read_xml(name):
            if archive.getinfo(name).file_size > 1024 * 1024:
                raise ValueError("Label worksheet exceeds the import limit.")
            raw = archive.read(name)
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError("Unsupported XML declarations.")
            return element_tree.fromstring(raw)

        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(text.text or "" for text in item.findall(".//m:t", NS))
                      for item in read_xml("xl/sharedStrings.xml").findall("m:si", NS)]
        sheet = read_xml("xl/workbook.xml").find("m:sheets/m:sheet", NS)
        if sheet is None:
            raise ValueError("Training label worksheet unavailable.")
        relationship_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        relationships = read_xml("xl/_rels/workbook.xml.rels")
        relation = next(item for item in relationships if item.attrib.get("Id") == relationship_id)
        if relation.attrib.get("TargetMode") == "External":
            raise ValueError("External label relationships are unsupported.")
        target = relation.attrib["Target"]
        name = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        if not name.startswith("xl/"):
            raise ValueError("Invalid label worksheet reference.")
        rows = []
        for row in read_xml(name).findall("m:sheetData/m:row", NS):
            values = []
            for cell in row.findall("m:c", NS):
                if cell.find("m:f", NS) is not None:
                    raise ValueError("Labels must contain literal values, not formulas.")
                kind = cell.attrib.get("t")
                raw = cell.findtext("m:v", default="", namespaces=NS)
                if kind == "s":
                    value = shared[int(raw)]
                elif kind == "inlineStr":
                    value = "".join(text.text or "" for text in cell.findall(".//m:t", NS))
                else:
                    value = raw
                if value != "":
                    values.append({"cell": cell.attrib["r"], "value": value})
            if values:
                rows.append(values)
        return rows
