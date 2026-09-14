"""Unit tests for dependency-free contact-file parsing (CSV / TSV / TXT / XLSX)."""

import io
import zipfile

from app.services.imports import parse_contacts, parse_csv, parse_xlsx


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    """Build a minimal xlsx (one sheet, inline strings) in memory."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet_rows = []
    for r in rows:
        cols = "".join(
            f'<c t="inlineStr"><is><t>{cell}</t></is></c>' for cell in r
        )
        sheet_rows.append(f"<row>{cols}</row>")
    sheet_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{ns}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "placeholder")
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def test_parse_csv_with_header():
    data = "phone,name\n+254 712 345 678,Alice\n254 700 200 100,Bob\n".encode()
    assert parse_csv(data) == ["254712345678", "254700200100"]


def test_parse_csv_no_header():
    data = "254701111111\n234702222222\n".encode()
    assert parse_csv(data) == ["254701111111", "234702222222"]


def test_parse_tsv():
    data = "phone\tname\n254712345678\tAlice\n".encode()
    assert parse_contacts("contacts.tsv", data) == ["254712345678"]


def test_parse_txt_one_per_line():
    data = "254711111111\n\n+234 801 222 3333\n".encode()
    assert parse_contacts("list.txt", data) == ["254711111111", "2348012223333"]


def test_parse_xlsx_inline_strings():
    xlsx = _xlsx_bytes([["phone", "name"], ["+254 712 999 888", "Alice"]])
    assert parse_xlsx(xlsx) == ["254712999888"]


def test_parse_xlsx_numeric_cells():
    # Numbers stored as raw numeric cells (t omitted) should still be sniffed.
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{ns}"><sheetData>'
        f"<row><c><v>234701234567</v></c></row>"
        f"</sheetData></worksheet>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "placeholder")
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    assert parse_xlsx(buf.getvalue()) == ["234701234567"]


def test_parse_empty_returns_nothing():
    assert parse_contacts("notes.txt", b"no numbers here at all") == []