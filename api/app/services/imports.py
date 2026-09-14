"""Parse contact lists from uploaded files (CSV / TSV / TXT / XLSX).

Deliberately dependency-free: CSV/TSV/TXT use the stdlib ``csv`` module, and
XLSX is read through its native ZIP+XML layout (``zipfile`` + ``ElementTree``)
supporting shared strings, inline strings and raw numeric cells. Returns a flat
list of phone-like digit strings; everything downstream (country detection,
dedup, per-row creation) lives in ``registration.py``.
"""

import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}

# First-row cells that mark a header rather than a contact.
_HEADER_HINTS = re.compile(
    r"(phone|number|contact|mobile|tel|name|username|sns|sms|country|note|comment)",
    re.IGNORECASE,
)

# A phone-like run of digits we are willing to treat as a number.
_PHONE_DIGITS = re.compile(r"\d{7,15}")


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _is_header_row(cells: list[str]) -> bool:
    flat = " ".join(c for c in cells[:3] if c)
    return bool(_HEADER_HINTS.search(flat)) and not any(
        _PHONE_DIGITS.search(c) for c in cells[:3]
    )


def _pick_phone(cells: list[str]) -> str | None:
    """Return the first cell that looks like a phone number."""
    for cell in cells:
        digits = _digits(cell)
        if len(digits) >= 7:
            return digits
    return None


def parse_csv(data: bytes, delimiter: str = ",") -> list[str]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    numbers: list[str] = []
    for i, row in enumerate(reader):
        cells = [c for c in row if c is not None]
        if i == 0 and _is_header_row(cells):
            continue
        phone = _pick_phone(cells)
        if phone:
            numbers.append(phone)
    return numbers


def _parse_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    out: list[str] = []
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return out
    for si in root.findall("main:si", NS):
        texts = [t.text or "" for t in si.iter(f"{{{NS['main']}}}t")]
        out.append("".join(texts))
    return out


def _row_cells(row_elem, shared: list[str]) -> list[str]:
    cells: list[str] = []
    for c in row_elem.iter(f"{{{NS['main']}}}c"):
        t = c.get("t")
        v = c.find(f"{{{NS['main']}}}v")
        value = ""
        if t == "s" and v is not None:
            idx = int(v.text or "0")
            value = shared[idx] if idx < len(shared) else ""
        elif t == "inlineStr":
            value = "".join(
                (n.text or "") for n in c.iter(f"{{{NS['main']}}}t")
            )
        elif v is not None:
            value = v.text or ""
            if value.startswith("="):  # formula result not evaluated
                value = ""
        if value:
            cells.append(value)
    return cells


def parse_xlsx(data: bytes) -> list[str]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Not a valid .xlsx file") from exc

    shared = _parse_shared_strings(zf)
    sheet = next(
        (n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
        None,
    )
    if sheet is None:
        return []
    root = ET.fromstring(zf.read(sheet))

    numbers: list[str] = []
    for i, row in enumerate(root.iter(f"{{{NS['main']}}}row")):
        cells = _row_cells(row, shared)
        if i == 0 and _is_header_row(cells):
            continue
        phone = _pick_phone(cells)
        if phone:
            numbers.append(phone)
    return numbers


def parse_contacts(filename: str, data: bytes) -> list[str]:
    """Dispatch by extension: csv/tsv/txt -> text parse, xlsx -> zip parse."""
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        return parse_xlsx(data)
    if name.endswith((".csv", ".tsv", ".txt")):
        delimiter = "\t" if name.endswith(".tsv") else ","
        return parse_csv(data, delimiter=delimiter)
    # Unknown extension: sniff a delimiter that yields results.
    for delimiter in (",", "\t", ";"):
        nums = parse_csv(data, delimiter=delimiter)
        if nums:
            return nums
    return []