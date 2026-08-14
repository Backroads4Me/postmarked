"""The xlsx import parses attacker-shaped XML inside the API process.

openpyxl only refuses DTDs when defusedxml is installed; without it the stdlib
parser expands internal entities, so a sub-3 KB workbook could exhaust memory in
the process that also serves every page.
"""

import io
import zipfile

import openpyxl
import pytest

from app.imports.rv_trip_wizard import parse_excel

_CONTENT_TYPES = """<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK = """<?xml version="1.0"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""

_WORKBOOK_RELS = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""

# Three nested entities at 10x each: 1000 characters from a tiny declaration.
_BOMB_SHEET = """<?xml version="1.0"?>
<!DOCTYPE worksheet [
  <!ENTITY a "aaaaaaaaaa">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>&c;</t></is></c></row></sheetData>
</worksheet>"""


def _bomb_workbook(tmp_path):
    path = tmp_path / "bomb.xlsx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("xl/workbook.xml", _WORKBOOK)
        zf.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        zf.writestr("xl/worksheets/sheet1.xml", _BOMB_SHEET)
    path.write_bytes(buf.getvalue())
    return path


def test_defusedxml_is_active():
    # openpyxl decides this at import time; without the dependency it is False
    # and the stdlib parser expands entities.
    assert openpyxl.DEFUSEDXML is True


def test_entity_expansion_is_refused(tmp_path):
    path = _bomb_workbook(tmp_path)
    assert path.stat().st_size < 3000, "the archive stays tiny; the expansion is the payload"

    with pytest.raises(Exception) as exc:
        parse_excel(str(path))

    # openpyxl wraps the real cause in a generic ValueError, so walk the chain.
    # Matching on the message is not enough: it embeds the file path, and under
    # pytest that path is named after this test.
    causes = []
    current = exc.value
    while current is not None and len(causes) < 6:
        causes.append(f"{type(current).__module__}.{type(current).__name__}")
        current = current.__cause__ or current.__context__

    assert "defusedxml.common.EntitiesForbidden" in causes, (
        f"expected defusedxml to reject the DTD, got chain: {causes}"
    )
