"""导入官方资料包中的灵山胜境景点结构化数据。

用法：
    python scripts/import_official_data.py --dry-run
    python scripts/import_official_data.py --source data/raw/official.zip
    python scripts/import_official_data.py --download --commit
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

OFFICIAL_PACKAGE_URL = "https://www.cnsoftbei.com/uploadfile/2026/0323/20260323113204906.zip"
STRUCTURED_DOC_KEYWORDS = ("灵山胜境", "结构化数据集")
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass(frozen=True)
class ScenicSpotRecord:
    scenic_area: str
    code: str
    name: str
    location: str
    parameters: str
    core_function: str
    cultural_meaning: str
    description: str
    highlights: str
    open_info: str
    remarks: str
    category: str | None = None


FIELD_MAP = {
    "景区名称": "scenic_area",
    "景点ID": "code",
    "景点名称": "name",
    "具体位置": "location",
    "建筑/景观参数": "parameters",
    "核心功能": "core_function",
    "文化内涵": "cultural_meaning",
    "详细介绍": "description",
    "游玩亮点": "highlights",
    "演艺/开放信息": "open_info",
    "备注": "remarks",
}


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def read_docx_tables(docx_bytes: bytes) -> list[list[list[str]]]:
    """读取 docx 表格，返回 table -> row -> cell 文本。"""

    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    tables: list[list[list[str]]] = []
    for table in root.findall(".//w:tbl", WORD_NS):
        rows: list[list[str]] = []
        for row in table.findall("w:tr", WORD_NS):
            cells: list[str] = []
            for cell in row.findall("w:tc", WORD_NS):
                text_parts = [node.text or "" for node in cell.findall(".//w:t", WORD_NS)]
                cells.append(normalize_text("".join(text_parts)))
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def read_docx_paragraphs(docx_bytes: bytes) -> list[str]:
    """读取 docx 段落，作为表格解析失败时的兜底。"""

    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", WORD_NS):
        text_parts = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NS)]
        text = normalize_text("".join(text_parts))
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_structured_docx(package_path: Path) -> bytes:
    if package_path.suffix.lower() == ".docx":
        return package_path.read_bytes()

    if package_path.suffix.lower() != ".zip":
        raise ValueError(f"不支持的资料格式：{package_path}")

    with zipfile.ZipFile(package_path) as package:
        candidates = [
            name
            for name in package.namelist()
            if name.lower().endswith(".docx")
            and all(keyword in name for keyword in STRUCTURED_DOC_KEYWORDS)
        ]
        if not candidates:
            candidates = [
                name
                for name in package.namelist()
                if name.lower().endswith(".docx") and "结构化" in name
            ]
        if not candidates:
            docx_names = [name for name in package.namelist() if name.lower().endswith(".docx")]
            for name in docx_names:
                content = package.read(name)
                preview = "\n".join(read_docx_paragraphs(content)[:20])
                if all(keyword in preview for keyword in STRUCTURED_DOC_KEYWORDS):
                    candidates = [name]
                    break
        if not candidates:
            raise FileNotFoundError("资料包中未找到灵山胜境结构化数据集 docx")
        return package.read(candidates[0])


def parse_records_from_tables(tables: list[list[list[str]]]) -> list[ScenicSpotRecord]:
    records: list[ScenicSpotRecord] = []
    expected_headers = list(FIELD_MAP.keys())

    for table in tables:
        if not table:
            continue

        header_index = next(
            (
                idx
                for idx, row in enumerate(table)
                if len(row) >= len(expected_headers)
                and row[: len(expected_headers)] == expected_headers
            ),
            None,
        )
        if header_index is None:
            continue

        for row in table[header_index + 1 :]:
            if len(row) < len(expected_headers):
                continue
            values = dict(zip(expected_headers, row[: len(expected_headers)], strict=False))
            code = normalize_text(values.get("景点ID"))
            name = normalize_text(values.get("景点名称"))
            if not code or not name or not code.startswith(("LS-", "NHW-", "NHH-", "LSSJ-")):
                continue
            records.append(
                ScenicSpotRecord(
                    scenic_area=normalize_text(values.get("景区名称")) or "灵山胜境",
                    code=code,
                    name=name,
                    location=normalize_text(values.get("具体位置")),
                    parameters=normalize_text(values.get("建筑/景观参数")),
                    core_function=normalize_text(values.get("核心功能")),
                    cultural_meaning=normalize_text(values.get("文化内涵")),
                    description=normalize_text(values.get("详细介绍")),
                    highlights=normalize_text(values.get("游玩亮点")),
                    open_info=normalize_text(values.get("演艺/开放信息")),
                    remarks=normalize_text(values.get("备注")),
                    category=infer_category(name, normalize_text(values.get("核心功能"))),
                )
            )

    return deduplicate_records(records)


def parse_records_from_paragraphs(paragraphs: list[str]) -> list[ScenicSpotRecord]:
    """兜底解析：按字段顺序从线性段落中恢复记录。"""

    records: list[ScenicSpotRecord] = []
    headers = list(FIELD_MAP.keys())
    i = 0
    while i < len(paragraphs):
        if paragraphs[i] not in {"灵山胜境", "拈花湾禅意小镇"}:
            i += 1
            continue
        chunk = paragraphs[i : i + len(headers)]
        if len(chunk) < len(headers):
            break
        scenic_area, code, name = chunk[0], chunk[1], chunk[2]
        if not re.match(r"^[A-Z]+-\d{3}$", code):
            i += 1
            continue
        records.append(
            ScenicSpotRecord(
                scenic_area=scenic_area,
                code=code,
                name=name,
                location=chunk[3],
                parameters=chunk[4],
                core_function=chunk[5],
                cultural_meaning=chunk[6],
                description=chunk[7],
                highlights=chunk[8],
                open_info=chunk[9],
                remarks=chunk[10],
                category=infer_category(name, chunk[5]),
            )
        )
        i += len(headers)

    return deduplicate_records(records)


def infer_category(name: str, core_function: str) -> str:
    text = f"{name} {core_function}"
    if any(keyword in text for keyword in ("寺", "佛", "坛", "禅", "朝圣", "祈福")):
        return "佛教文化"
    if any(keyword in text for keyword in ("表演", "演艺", "动态", "喷泉", "剧场")):
        return "演艺体验"
    if any(keyword in text for keyword in ("桥", "大道", "广场", "塔", "壁")):
        return "景观打卡"
    if any(keyword in text for keyword in ("小镇", "街", "商业", "休闲")):
        return "休闲体验"
    return "综合景点"


def deduplicate_records(records: list[ScenicSpotRecord]) -> list[ScenicSpotRecord]:
    result: dict[str, ScenicSpotRecord] = {}
    for record in records:
        result[record.code] = record
    return list(result.values())


def parse_scenic_spots(package_path: Path) -> list[ScenicSpotRecord]:
    docx_bytes = extract_structured_docx(package_path)
    records = parse_records_from_tables(read_docx_tables(docx_bytes))
    if records:
        return records
    return parse_records_from_paragraphs(read_docx_paragraphs(docx_bytes))


def download_official_package() -> Path:
    target_dir = PROJECT_ROOT / "data" / "raw"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "cnsoftbei_a5_official_package.zip"
    if target.exists() and target.stat().st_size > 0:
        return target

    with urllib.request.urlopen(OFFICIAL_PACKAGE_URL, timeout=60) as response:
        target.write_bytes(response.read())
    return target


def upsert_records(records: list[ScenicSpotRecord]) -> tuple[int, int]:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.scenic import ScenicSpot

    created = 0
    updated = 0

    with SessionLocal() as session:
        for record in records:
            spot = session.scalar(select(ScenicSpot).where(ScenicSpot.code == record.code))
            values = {
                "scenic_area": record.scenic_area,
                "name": record.name,
                "location": record.location,
                "category": record.category,
                "parameters": record.parameters,
                "core_function": record.core_function,
                "cultural_meaning": record.cultural_meaning,
                "description": record.description,
                "highlights": record.highlights,
                "open_info": record.open_info,
                "remarks": record.remarks,
            }
            if spot is None:
                session.add(ScenicSpot(code=record.code, **values))
                created += 1
            else:
                for key, value in values.items():
                    setattr(spot, key, value)
                updated += 1
        session.commit()

    return created, updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导入软件杯 A5 官方灵山胜境结构化景点数据")
    parser.add_argument("--source", type=Path, help="官方资料包 zip 或结构化 docx 路径")
    parser.add_argument("--download", action="store_true", help="下载官方资料包到 data/raw 后导入")
    parser.add_argument("--dry-run", action="store_true", help="仅解析并打印统计，不写入数据库")
    parser.add_argument("--commit", action="store_true", help="确认写入数据库")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.source:
        source = args.source
    elif args.download:
        source = download_official_package()
    else:
        default_source = PROJECT_ROOT / "data" / "raw" / "cnsoftbei_a5_official_package.zip"
        if default_source.exists():
            source = default_source
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_source = Path(temp_dir) / "official.zip"
                with urllib.request.urlopen(OFFICIAL_PACKAGE_URL, timeout=60) as response:
                    temp_source.write_bytes(response.read())
                records = parse_scenic_spots(temp_source)
                print_summary(records, dry_run=True)
                return

    records = parse_scenic_spots(source)
    if args.dry_run or not args.commit:
        print_summary(records, dry_run=True)
        return

    created, updated = upsert_records(records)
    print(f"导入完成：新增 {created} 条，更新 {updated} 条，总计 {len(records)} 条。")


def print_summary(records: list[ScenicSpotRecord], dry_run: bool) -> None:
    prefix = "解析完成（未写入数据库）" if dry_run else "解析完成"
    print(f"{prefix}：共 {len(records)} 条景点记录。")
    for record in records[:5]:
        print(f"- {record.code} | {record.scenic_area} | {record.name} | {record.category}")


if __name__ == "__main__":
    main()
