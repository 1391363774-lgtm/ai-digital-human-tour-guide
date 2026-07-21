from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
XLSX_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True)
class ParsedSection:
    title: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    source_path: str
    file_type: str
    sections: list[ParsedSection]

    @property
    def text(self) -> str:
        return "\n\n".join(section.content for section in self.sections if section.content)


class DocumentParserError(ValueError):
    pass


class DocumentParser:
    supported_suffixes = {".txt", ".md", ".csv", ".tsv", ".docx", ".xlsx"}

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix not in self.supported_suffixes:
            raise DocumentParserError(f"暂不支持的文件类型：{suffix}")
        if not path.exists():
            raise DocumentParserError(f"文件不存在：{path}")

        if suffix in {".txt", ".md"}:
            sections = self._parse_plain_text(path)
        elif suffix in {".csv", ".tsv"}:
            sections = self._parse_delimited_text(path, delimiter="\t" if suffix == ".tsv" else ",")
        elif suffix == ".docx":
            sections = self._parse_docx(path)
        elif suffix == ".xlsx":
            sections = self._parse_xlsx(path)
        else:
            raise DocumentParserError(f"暂不支持的文件类型：{suffix}")

        return ParsedDocument(
            title=path.stem,
            source_path=str(path),
            file_type=suffix.lstrip("."),
            sections=sections,
        )

    def _parse_plain_text(self, path: Path) -> list[ParsedSection]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return [ParsedSection(title=path.stem, content=normalize_text_block(text))]

    def _parse_delimited_text(self, path: Path, delimiter: str) -> list[ParsedSection]:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [[" ".join(normalize_inline(cell) for cell in row if cell.strip())] for row in reader]
        lines = [row[0] for row in rows if row and row[0]]
        return [ParsedSection(title=path.stem, content="\n".join(lines))]

    def _parse_docx(self, path: Path) -> list[ParsedSection]:
        with zipfile.ZipFile(path) as docx:
            root = ET.fromstring(docx.read("word/document.xml"))

        sections: list[ParsedSection] = []
        current_title = path.stem
        current_lines: list[str] = []

        for paragraph in root.findall(".//w:p", WORD_NS):
            text = normalize_inline("".join(node.text or "" for node in paragraph.findall(".//w:t", WORD_NS)))
            if not text:
                continue
            if looks_like_heading(text):
                if current_lines:
                    sections.append(
                        ParsedSection(title=current_title, content="\n".join(current_lines).strip())
                    )
                    current_lines = []
                current_title = text
            else:
                current_lines.append(text)

        for table_index, table in enumerate(root.findall(".//w:tbl", WORD_NS), start=1):
            rows: list[str] = []
            for row in table.findall("w:tr", WORD_NS):
                cells = []
                for cell in row.findall("w:tc", WORD_NS):
                    text = normalize_inline(
                        "".join(node.text or "" for node in cell.findall(".//w:t", WORD_NS))
                    )
                    if text:
                        cells.append(text)
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                current_lines.append(f"表格 {table_index}\n" + "\n".join(rows))

        if current_lines:
            sections.append(ParsedSection(title=current_title, content="\n".join(current_lines).strip()))

        return sections or [ParsedSection(title=path.stem, content="")]

    def _parse_xlsx(self, path: Path) -> list[ParsedSection]:
        with zipfile.ZipFile(path) as workbook:
            shared_strings = self._read_shared_strings(workbook)
            workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
            rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
            rel_map = {
                rel.attrib["Id"]: rel.attrib["Target"]
                for rel in rels_root.findall("rel:Relationship", XLSX_NS)
            }
            sections: list[ParsedSection] = []
            for sheet in workbook_root.findall(".//main:sheet", XLSX_NS):
                sheet_name = sheet.attrib.get("name", "Sheet")
                rel_id = sheet.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                target = rel_map.get(rel_id or "", "")
                sheet_path = "xl/" + target.lstrip("/")
                if sheet_path not in workbook.namelist():
                    sheet_path = "xl/worksheets/" + Path(target).name
                if sheet_path not in workbook.namelist():
                    continue
                rows = self._read_sheet_rows(workbook.read(sheet_path), shared_strings)
                content = "\n".join(" | ".join(row) for row in rows if any(row))
                sections.append(
                    ParsedSection(
                        title=sheet_name,
                        content=content,
                        metadata={"sheet_name": sheet_name, "row_count": str(len(rows))},
                    )
                )
        return sections

    def _read_shared_strings(self, workbook: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in workbook.namelist():
            return []
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        result: list[str] = []
        for item in root.findall(".//main:si", XLSX_NS):
            result.append("".join(node.text or "" for node in item.findall(".//main:t", XLSX_NS)))
        return result

    def _read_sheet_rows(self, sheet_xml: bytes, shared_strings: list[str]) -> list[list[str]]:
        root = ET.fromstring(sheet_xml)
        rows: list[list[str]] = []
        for row in root.findall(".//main:sheetData/main:row", XLSX_NS):
            values: list[tuple[int, str]] = []
            for cell in row.findall("main:c", XLSX_NS):
                value_node = cell.find("main:v", XLSX_NS)
                value = "" if value_node is None else value_node.text or ""
                if cell.attrib.get("t") == "s" and value.isdigit():
                    value = shared_strings[int(value)]
                values.append((column_index(cell.attrib.get("r", "A1")), normalize_inline(value)))
            max_index = max((idx for idx, _ in values), default=-1)
            normalized_row = [""] * (max_index + 1)
            for idx, value in values:
                normalized_row[idx] = value
            rows.append(normalized_row)
        return rows


def normalize_inline(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_text_block(value: str) -> str:
    lines = [normalize_inline(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def looks_like_heading(text: str) -> bool:
    if len(text) > 40:
        return False
    if text.startswith(("第", "一、", "二、", "三、", "四、", "五、")):
        return True
    return bool(re.match(r"^\d+(\.\d+)*[、. ]", text))


def column_index(cell_ref: str) -> int:
    letters = re.sub(r"\d", "", cell_ref)
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - ord("A") + 1
    return max(index - 1, 0)
