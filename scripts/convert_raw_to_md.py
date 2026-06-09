from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W_NS = NS["w"]
SUPPORTED_SUFFIXES = {".docx", ".pdf"}
MAX_ACCENT_REVIEW_PER_FILE = 1_000_000


@dataclass
class Block:
    kind: str
    text: str = ""
    md: str = ""
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    source: Path
    extractor: str
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
    doc_number: str = ""
    title: str = ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00a0", " ").replace("\u202f", " ").replace("\ufeff", "")
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return text


def remove_noise_fragments(text: str) -> str:
    # Distorted ThuVienPhapLuat scan footers often merge into legal text on OCR lines.
    patterns = [
        r"(?i)(?:[#*]\s*)?T[eE][eE]\s*\+[A-Z0-9\-]*28[-\d\s]+[”“\"'`* ]*www\.\s*\S+",
        r"(?i)(?:[#*]\s*)?T[eE][tT]\s*\+[A-Z0-9\-]*28[-\d\s]+[”“\"'`* ]*www\.\s*\S+",
        r"(?i)(?:[#*]\s*)?Tel\s*\+[A-Z0-9\-]*28[-\d\s]+[”“\"'`* ]*www\.\s*\S+",
        r"(?i)(?:[#*]\s*)?www\.\s*\S*(?:phap|vien|luat)\S*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, " ", text)
    return text


def clean_inline(text: str) -> str:
    text = normalize_unicode(text)
    text = remove_noise_fragments(text)
    text = text.replace("\t", " ")
    text = text.replace("VIỆT NAMĐộc", "VIỆT NAM Độc")
    text = text.replace("Việt NamĐộc", "Việt Nam Độc")
    text = text.replace("NAMĐộc", "NAM Độc")
    text = re.sub(r"[ \r\n]+", " ", text)
    text = re.sub(r"\s*[-‐‑‒–—_]{3,}\s*$", "", text)
    text = re.sub(r"^\s*[-‐‑‒–—_]{3,}\s*", "", text)
    return text.strip()


def is_noise_line(text: str) -> bool:
    s = clean_inline(text)
    if not s:
        return False
    suspicious = len(re.findall(r"[ÃÄÂˆ£§`~_=<>°]", s))
    letters = sum(1 for ch in s if ch.isalpha())
    if len(s) <= 100 and suspicious >= 3 and letters <= 12:
        return True
    key = match_key(s)
    if len(s) <= 120 and ("3930 3279" in key or "3950 3279" in key):
        return True
    return False


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("Đ", "D").replace("đ", "d")


def match_key(text: str) -> str:
    return strip_accents(normalize_unicode(text)).upper()


def should_drop_line(text: str) -> bool:
    s = clean_inline(text)
    if not s:
        return False
    key = match_key(s)
    if re.fullmatch(r"\d{1,4}", s):
        return True
    if re.fullmatch(r"[-‐‑‒–—_\s]{3,}", s):
        return True
    if is_noise_line(s):
        return True
    if "THU VIEN PHAP LUAT" in key or "THUVIENPHAP" in key:
        return True
    if "IHUVIENPHAP" in key or "HUVIENPHAP" in key or "PHAPLM" in key:
        return True
    if "WWW.THUV" in key or "THUVIENPHAPLUAT.VN" in key:
        return True
    if "WWW." in key and "PHAP" in key and len(s) < 220:
        return True
    if ("TEL +84" in key or "TET +84" in key or "+84-28" in key) and len(s) < 180:
        return True
    signing_prefixes = (
        "KY BOI",
        "BOI:",
        "CO QUAN:",
        "QUAN:",
        "THOI GIAN KY",
        "THOI KY",
        "NGUOI KY",
    )
    if len(s) < 160 and key.startswith(signing_prefixes):
        return True
    return False


def is_bold_run(run: ET.Element) -> bool:
    rpr = run.find("./w:rPr", NS)
    if rpr is None:
        return False
    bold = rpr.find("./w:b", NS)
    if bold is None:
        return False
    val = bold.get(f"{{{W_NS}}}val")
    return val not in {"0", "false", "False", "off"}


def paragraph_segments(paragraph: ET.Element) -> list[tuple[str, bool]]:
    segments: list[tuple[str, bool]] = []
    for run in paragraph.findall("./w:r", NS):
        bold = is_bold_run(run)
        parts: list[str] = []
        for child in run:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "t":
                parts.append(child.text or "")
            elif tag == "tab":
                parts.append(" ")
            elif tag == "br":
                parts.append("\n")
            elif tag == "footnoteReference":
                fid = child.get(f"{{{W_NS}}}id")
                if fid:
                    parts.append(f"[{fid}]")
        if parts:
            segments.append(("".join(parts), bold))
    return merge_segments(segments)


def merge_segments(segments: Iterable[tuple[str, bool]]) -> list[tuple[str, bool]]:
    merged: list[tuple[str, bool]] = []
    for text, bold in segments:
        if not text:
            continue
        if merged and merged[-1][1] == bold:
            merged[-1] = (merged[-1][0] + text, bold)
        else:
            merged.append((text, bold))
    return merged


def segments_to_plain(segments: list[tuple[str, bool]]) -> str:
    return clean_inline("".join(text for text, _ in segments))


def bold_wrap(text: str) -> str:
    if not text.strip():
        return text
    leading = re.match(r"^\s*", text).group(0)
    trailing = re.search(r"\s*$", text).group(0)
    core = text[len(leading) : len(text) - len(trailing) if trailing else len(text)]
    if not core:
        return text
    return f"{leading}**{core}**{trailing}"


def segments_to_md(segments: list[tuple[str, bool]]) -> str:
    parts = [bold_wrap(text) if bold else text for text, bold in segments]
    return clean_inline("".join(parts))


def paragraph_block(paragraph: ET.Element) -> Block | None:
    segments = paragraph_segments(paragraph)
    plain = segments_to_plain(segments)
    if not plain or should_drop_line(plain):
        return None
    return Block(kind="para", text=plain, md=segments_to_md(segments))


def paragraph_plain_text(paragraph: ET.Element) -> str:
    return segments_to_plain(paragraph_segments(paragraph))


def cell_text(cell: ET.Element) -> str:
    paras = []
    for p in cell.findall(".//w:p", NS):
        text = paragraph_plain_text(p)
        if text and not should_drop_line(text):
            paras.append(text)
    return "<br>".join(paras)


def table_block(table: ET.Element) -> Block | None:
    rows: list[list[str]] = []
    for tr in table.findall("./w:tr", NS):
        cells = [clean_inline(cell_text(tc)) for tc in tr.findall("./w:tc", NS)]
        if any(cells):
            rows.append(cells)
    if not rows:
        return None
    width = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (width - len(row)))
    return Block(kind="table", rows=rows)


def iter_body_blocks(root: ET.Element) -> Iterable[ET.Element]:
    body = root.find("./w:body", NS)
    if body is None:
        return []
    return list(body)


def read_docx_footnotes(path: Path) -> dict[str, str]:
    footnotes: dict[str, str] = {}
    try:
        with zipfile.ZipFile(path) as z:
            if "word/footnotes.xml" not in z.namelist():
                return footnotes
            root = ET.fromstring(z.read("word/footnotes.xml"))
    except (zipfile.BadZipFile, ET.ParseError):
        return footnotes

    for footnote in root.findall("./w:footnote", NS):
        fid = footnote.get(f"{{{W_NS}}}id")
        if fid is None or fid.startswith("-"):
            continue
        paras = []
        for p in footnote.findall("./w:p", NS):
            text = paragraph_plain_text(p)
            if text and not should_drop_line(text):
                paras.append(text)
        if paras:
            footnotes[fid] = " ".join(paras)
    return footnotes


def extract_docx(path: Path) -> ExtractedDocument:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        return ExtractedDocument(path, "docx-ooxml", [], [f"docx_parse_error: {exc}"])

    blocks: list[Block] = []
    for child in iter_body_blocks(root):
        tag = child.tag.rsplit("}", 1)[-1]
        block: Block | None = None
        if tag == "p":
            block = paragraph_block(child)
        elif tag == "tbl":
            block = table_block(child)
        if block:
            blocks.append(block)

    footnotes = read_docx_footnotes(path)
    if footnotes:
        blocks.append(Block(kind="para", text="Chú thích", md="Chú thích"))
        for fid in sorted(footnotes, key=lambda value: int(value) if value.isdigit() else value):
            text = f"[{fid}] {footnotes[fid]}"
            blocks.append(Block(kind="para", text=text, md=text))

    return ExtractedDocument(path, "docx-ooxml", blocks, warnings)


def run_pdftotext(path: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    cmd = ["pdftotext", "-layout", str(path), "-"]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return "", ["pdftotext_not_found"]
    if completed.returncode != 0:
        warnings.append(f"pdftotext_returncode_{completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout, warnings


def is_main_doc_type_line(text: str) -> bool:
    key = match_key(text)
    key = re.sub(r"\[[^\]]+\]", "", key)
    key = re.sub(r"[^A-Z ]+", "", key).strip()
    return key in {"LUAT", "NGHI DINH", "THONG TU", "NGHI QUYET", "QUYET DINH"}


def normalize_doc_type(text: str) -> str:
    text = re.sub(r"[!?]+$", "", clean_inline(text))
    return text.strip()


def is_chapter_line(text: str) -> bool:
    return re.match(r"^Chương\s+([IVXLCDM]+|\d+)\b", clean_inline(text), re.IGNORECASE) is not None


def is_section_line(text: str) -> bool:
    return re.match(r"^Mục\s+\d+\b", clean_inline(text), re.IGNORECASE) is not None


def is_article_line(text: str) -> bool:
    return re.match(r"^Điều\s+\d+[a-zA-Z]?\.", clean_inline(text), re.IGNORECASE) is not None


def is_appendix_line(text: str) -> bool:
    return re.match(r"^Phụ\s+lục\b", clean_inline(text), re.IGNORECASE) is not None


def is_structural_line(text: str) -> bool:
    return (
        is_main_doc_type_line(text)
        or is_chapter_line(text)
        or is_section_line(text)
        or is_article_line(text)
        or is_appendix_line(text)
    )


def uppercase_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if ch.upper() == ch) / len(letters)


def is_heading_subtitle(text: str) -> bool:
    s = clean_inline(text)
    if not s:
        return False
    if is_structural_line(s):
        return False
    if re.match(r"^(Căn cứ|Theo đề nghị|Quốc hội ban hành|Chính phủ ban hành|Bộ trưởng)", s, re.IGNORECASE):
        return False
    if len(s) > 220:
        return False
    return uppercase_ratio(s) >= 0.65


def is_title_follow_line(text: str) -> bool:
    s = clean_inline(text)
    if not s or is_structural_line(s):
        return False
    if re.match(
        r"^(Căn cứ|Theo đề nghị|Quốc hội ban hành|Chính phủ ban hành|Bộ trưởng|Luật số|Số:|Hà Nội)",
        s,
        re.IGNORECASE,
    ):
        return False
    if re.match(r"^(Luật|Nghị định|Thông tư)\s+(số|này)\b", s, re.IGNORECASE):
        return False
    return len(s) <= 260


def is_new_list_item(text: str) -> bool:
    return re.match(r"^(\d+\.|[a-zđ]\)|[a-zđ]\.|[-+])\s+", clean_inline(text), re.IGNORECASE) is not None


def ends_sentence(text: str) -> bool:
    return bool(re.search(r"[.;:!?]([\"”’']|\])?$", clean_inline(text)))


def pdf_lines_to_blocks(raw_text: str) -> list[Block]:
    raw_text = normalize_unicode(raw_text).replace("\f", "\n\n")
    cleaned_lines: list[str] = []
    for raw_line in raw_text.splitlines():
        line = clean_inline(raw_line)
        if not line:
            cleaned_lines.append("")
            continue
        if should_drop_line(line):
            continue
        cleaned_lines.append(line)

    blocks: list[Block] = []
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        text = clean_inline(" ".join(buffer))
        if text and not should_drop_line(text):
            blocks.append(Block(kind="para", text=text, md=text))
        buffer = []

    for line in cleaned_lines:
        if not line:
            flush()
            continue
        if is_structural_line(line) or (uppercase_ratio(line) >= 0.8 and len(line) <= 90):
            flush()
            blocks.append(Block(kind="para", text=line, md=line))
            continue
        if not buffer:
            buffer.append(line)
            continue
        previous = buffer[-1]
        if is_new_list_item(line) or (ends_sentence(previous) and re.match(r"^[A-ZÀ-ỴĐ0-9]", line)):
            flush()
            buffer.append(line)
        else:
            buffer.append(line)
    flush()
    return blocks


def extract_pdf(path: Path) -> ExtractedDocument:
    text, warnings = run_pdftotext(path)
    if len(text.strip()) < 500:
        warnings.append("pdf_text_too_short_or_empty")
    blocks = pdf_lines_to_blocks(text)
    return ExtractedDocument(path, "pdftotext-layout", blocks, warnings)


def markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]

    def esc(cell: str) -> str:
        return clean_inline(cell).replace("|", r"\|")

    lines = ["| " + " | ".join(esc(c) for c in padded[0]) + " |"]
    lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
    for row in padded[1:]:
        lines.append("| " + " | ".join(esc(c) for c in row) + " |")
    return "\n".join(lines)


def split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip().replace(r"\|", "|") for cell in stripped.strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    return re.fullmatch(r"\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|", line.strip()) is not None


def is_national_motto_text(text: str) -> bool:
    key = match_key(text)
    return "CONG HOA XA HOI CHU NGHIA VIET" in key or "DOC LAP - TU DO - HANH PHUC" in key


def is_opening_agency_text(text: str) -> bool:
    key = match_key(text)
    if len(key) > 80:
        return False
    agencies = (
        "QUOC HOI",
        "CHINH PHU",
        "BO TAI CHINH",
        "VAN PHONG QUOC HOI",
        "UY BAN THUONG VU QUOC HOI",
    )
    return any(key == agency or key.startswith(agency) for agency in agencies)


def looks_like_doc_number_text(text: str) -> bool:
    return re.match(r"^(Số|Luật số|Nghị quyết số|Thông tư số|Nghị định số)\s*:", clean_inline(text), re.IGNORECASE) is not None


def looks_like_issued_date_text(text: str) -> bool:
    return re.search(r"\bngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}\b", clean_inline(text), re.IGNORECASE) is not None


def normalize_opening_header(markdown: str) -> str:
    lines = markdown.splitlines()
    if len(lines) >= 3 and lines[0].strip().startswith("|") and is_table_separator(lines[1]):
        first_cells = split_markdown_row(lines[0])
        meta_cells = split_markdown_row(lines[2])
        first_text = " ".join(first_cells)
        if len(meta_cells) >= 2 and is_national_motto_text(first_text) and (
            is_opening_agency_text(first_text) or len(first_cells) >= 2
        ):
            meta_text = " | ".join(cell for cell in meta_cells if cell)
            if looks_like_doc_number_text(meta_text) or looks_like_issued_date_text(meta_text):
                lines = [meta_text] + lines[3:]

    first_heading = next((idx for idx, line in enumerate(lines) if line.startswith("# ")), min(len(lines), 12))
    normalized: list[str] = []
    for idx, line in enumerate(lines):
        text = clean_inline(line)
        if idx < first_heading and (is_national_motto_text(text) or is_opening_agency_text(text)):
            continue
        normalized.append(line)

    text = "\n".join(normalized)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text


def escape_accidental_markdown(text: str) -> str:
    if re.match(r"^\s{0,3}#{1,6}\s+", text):
        return "\\" + text
    return text


def heading_text(base: str, subtitle: str | None = None) -> str:
    base = clean_inline(base)
    if subtitle:
        subtitle = clean_inline(subtitle)
        if subtitle:
            sep = " " if base.endswith((".", ":", "-")) else ". "
            return f"{base}{sep}{subtitle}"
    return base


def blocks_to_markdown(blocks: list[Block]) -> tuple[str, list[str], str]:
    output: list[str] = []
    headings: list[str] = []
    title = ""
    title_seen = False
    i = 0

    while i < len(blocks):
        block = blocks[i]
        if block.kind == "table":
            table_md = markdown_table(block.rows)
            if table_md:
                output.append(table_md)
            i += 1
            continue

        text = clean_inline(block.text)
        md = clean_inline(block.md or block.text)
        if not text or should_drop_line(text):
            i += 1
            continue

        if is_main_doc_type_line(text) and not title_seen and i < 40:
            parts = [normalize_doc_type(text)]
            j = i + 1
            while j < len(blocks) and len(parts) < 4:
                nxt = blocks[j]
                if nxt.kind != "para" or not is_title_follow_line(nxt.text):
                    break
                parts.append(clean_inline(nxt.text))
                j += 1
            title = clean_inline(" ".join(parts))
            output.append(f"# {title}")
            headings.append(title)
            title_seen = True
            i = j
            continue

        if is_chapter_line(text):
            subtitle = None
            if i + 1 < len(blocks) and blocks[i + 1].kind == "para" and is_heading_subtitle(blocks[i + 1].text):
                subtitle = blocks[i + 1].text
                i += 1
            head = heading_text(text, subtitle)
            output.append(f"## {head}")
            headings.append(head)
            i += 1
            continue

        if is_section_line(text):
            subtitle = None
            if i + 1 < len(blocks) and blocks[i + 1].kind == "para" and is_heading_subtitle(blocks[i + 1].text):
                subtitle = blocks[i + 1].text
                i += 1
            head = heading_text(text, subtitle)
            output.append(f"### {head}")
            headings.append(head)
            i += 1
            continue

        if is_appendix_line(text):
            output.append(f"## {text}")
            headings.append(text)
            i += 1
            continue

        if is_article_line(text):
            output.append(f"#### {text}")
            headings.append(text)
            i += 1
            continue

        output.append(escape_accidental_markdown(md))
        i += 1

    markdown = "\n\n".join(part for part in output if part.strip())
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip() + "\n"
    markdown = normalize_opening_header(markdown)
    return markdown, headings, title


def case_like(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def replacement_with_case(replacement: str):
    def repl(match: re.Match[str]) -> str:
        return case_like(match.group(0), replacement)

    return repl


def apply_regex_rule(text: str, name: str, pattern: str, replacement: str) -> tuple[str, list[str]]:
    updated = re.sub(pattern, replacement_with_case(replacement), text, flags=re.IGNORECASE)
    return updated, ([name] if updated != text else [])


def apply_contextual_ocr_fixes_to_line(line: str) -> tuple[str, list[str]]:
    rules: list[str] = []
    fixed = line

    safe_rules = [
        ("co_cau", r"\bcơ c[ầẩ]u\b", "cơ cấu"),
        ("sua_doi", r"\bsửa đ[ôồố]i\b", "sửa đổi"),
        ("bo_sung_joined", r"\bb[ôồốỏỗộê]\s*sung(?=[A-Za-zÀ-Ỵà-ỵĐđ])", "bổ sung "),
        ("bo_sung", r"\bb[ôồốỏỗộê] sung\b", "bổ sung"),
        ("chi_tiet", r"\bchỉ tiết\b", "chi tiết"),
        ("thi_hanh", r"\bth[ỉìị] hành\b", "thi hành"),
        ("ke_tu", r"\bk[êềẻế] từ\b", "kể từ"),
        ("cau_truc", r"\bcầu trúc\b", "cấu trúc"),
        ("ngan_sach", r"\bngán sách\b", "ngân sách"),
        ("quyen_han", r"\bquyên hạn\b", "quyền hạn"),
        ("mau_bieu", r"\bmâu biểu\b", "mẫu biểu"),
        ("mau_so", r"\bmâu s[ôố]\b", "mẫu số"),
        ("hieu_nhu", r"\bhiều như\b", "hiểu như"),
        ("chinh_quyen", r"\bchính quyên\b", "chính quyền"),
        ("quoc_hoi", r"\bquôc hội\b", "quốc hội"),
        ("to_chuc", r"\bt[ôỏ] chức\b", "tổ chức"),
        ("ca_nhan", r"\bcá nhãn\b|\bcánhân\b", "cá nhân"),
        ("uy_quyen", r"\b[ủu]ỷ? quyên\b|\buỷ quyên\b|\bủy quyên\b", "ủy quyền"),
        ("quyen_loi", r"\bquyên lợi\b", "quyền lợi"),
        ("doi_voi", r"\bđ[ôồ]i với\b", "đối với"),
        ("doi_voi_distorted", r"[ÐĐ]+ồi với\b", "Đối với"),
        ("truc_tiep", r"\btrực tiêp\b", "trực tiếp"),
        ("tiep_nhan", r"\btiêp nhận\b", "tiếp nhận"),
        ("tiep_tuc", r"\btiêp tục\b", "tiếp tục"),
        ("bo_tai_chinh", r"\bBộ Tải chính\b", "Bộ Tài chính"),
    ]
    for name, pattern, replacement in safe_rules:
        fixed, applied = apply_regex_rule(fixed, name, pattern, replacement)
        rules.extend(applied)

    authority_patterns = [
        r"\bthẳm quyền\b",
        r"\bthâm quyền\b",
        r"\bthầm quyền\b",
        r"\bthấm quyền\b",
        r"\bthắm quyền\b",
        r"\bthẳm quyên\b",
        r"\bthâm quyên\b",
        r"\bthầm quyên\b",
        r"\bthẩm quyên\b",
        r"\bthấm quyên\b",
        r"\bthắm quyên\b",
    ]
    for pattern in authority_patterns:
        fixed, applied = apply_regex_rule(fixed, "tham_quyen", pattern, "thẩm quyền")
        rules.extend(applied)

    thue_prefixes = [
        "quản lý",
        "người nộp",
        "mã số",
        "khai",
        "nộp",
        "hoàn",
        "miễn",
        "giảm",
        "quyết toán",
        "đăng ký",
        "cơ quan",
        "hồ sơ",
        "nghĩa vụ về",
        "luật quản lý",
    ]
    for prefix in thue_prefixes:
        pattern = rf"\b{re.escape(prefix)} thuê\b"
        fixed, applied = apply_regex_rule(fixed, "thue_to_thue_after_context", pattern, f"{prefix} thuế")
        rules.extend(applied)

    tax_name_suffixes = [
        "thu nhập",
        "giá trị gia tăng",
        "tiêu thụ",
        "xuất khẩu",
        "nhập khẩu",
        "tài nguyên",
        "môn bài",
        "sử dụng đất",
    ]
    for suffix in tax_name_suffixes:
        pattern = rf"\bthu[êé] {re.escape(suffix)}\b"
        fixed, applied = apply_regex_rule(fixed, "thue_to_thue_tax_name", pattern, f"thuế {suffix}")
        rules.extend(applied)

    direct_so_rules = [
        ("so_lieu", r"\bs[ôố] liệu\b", "số liệu"),
        ("so_tien", r"\bs[ôố] tiền\b", "số tiền"),
        ("so_thue", r"\bs[ôố] thuế\b", "số thuế"),
        ("so_ngay", r"\bs[ôố] ngày\b", "số ngày"),
        ("so_dinh_danh", r"\bs[ôố] định danh\b", "số định danh"),
        ("so_nop", r"\bs[ôố] nộp\b", "số nộp"),
        ("so_phu", r"\bs[ôố] phụ\b", "số phụ"),
    ]
    for name, pattern, replacement in direct_so_rules:
        fixed, applied = apply_regex_rule(fixed, name, pattern, replacement)
        rules.extend(applied)

    so_contexts = [
        "mã",
        "mẫu",
        "chữ",
        "thông tư",
        "nghị định",
        "luật",
        "nghị quyết",
        "văn bản",
        "một",
        "các",
        "tiền",
        "thuế",
        "định danh",
        "hồ sơ",
        "phụ lục",
        "tờ khai",
        "chứng chỉ hành nghề",
    ]
    for prefix in so_contexts:
        pattern = rf"\b{re.escape(prefix)} s[ôố]\b"
        fixed, applied = apply_regex_rule(fixed, "so_to_so_after_context", pattern, f"{prefix} số")
        rules.extend(applied)

    return fixed, sorted(set(rules))


def apply_contextual_ocr_fixes(markdown: str, output_name: str) -> tuple[str, list[dict]]:
    lines = markdown.splitlines()
    corrected: list[str] = []
    corrections: list[dict] = []
    for line_number, line in enumerate(lines, start=1):
        fixed, rules = apply_contextual_ocr_fixes_to_line(line)
        corrected.append(fixed)
        if rules and fixed != line:
            corrections.append(
                {
                    "file": output_name,
                    "line": line_number,
                    "rules": rules,
                    "before": line,
                    "after": fixed,
                }
            )
    return "\n".join(corrected).strip() + "\n", corrections


DOC_NUMBER_PATTERNS = [
    re.compile(r"\b(?:Số|số|Luật số|Thông tư số|Nghị định số)[:\s]*([0-9]+/[0-9]{4}/[A-ZĐ\-0-9]+)", re.UNICODE),
    re.compile(r"\b(Số:\s*[0-9]+/[A-ZĐ\-0-9]+)", re.UNICODE),
]


def extract_doc_number(blocks: list[Block], path: Path) -> str:
    first_text = "\n".join(block.text for block in blocks[:60] if block.kind == "para")
    for pattern in DOC_NUMBER_PATTERNS:
        match = pattern.search(first_text)
        if match:
            value = match.group(1)
            return clean_inline(value.replace("Số:", ""))
    stem = path.stem
    match = re.match(r"^(\d+)[_\-](\d{4})[_\-]([A-Za-z]+(?:-[A-Za-z]+)?|QH\d+)", stem)
    if match:
        suffix = match.group(3).upper().replace("ND-CP", "NĐ-CP")
        return f"{match.group(1)}/{match.group(2)}/{suffix}"
    match = re.match(r"^(\d+)[_\-]VBHN[_\-]([A-Za-z]+)", stem, re.IGNORECASE)
    if match:
        return f"{match.group(1)}/VBHN-{match.group(2).upper()}"
    return ""


def suspicious_reasons(text: str) -> list[str]:
    reasons: list[str] = []
    if re.search(r"[�Ä¡Ï⁄]", text):
        reasons.append("suspicious_unicode_or_mojibake")
    if re.search(r"(?<![A-Za-zÀ-Ỵà-ỵĐđ])Ì|Ì(?![A-Za-zÀ-Ỵà-ỵĐđ])", text):
        reasons.append("suspicious_unicode_or_mojibake")
    if re.search(r"\b(sô|Sô|sỐ|bô|Bô|bố Sung|sửa đôi|kê từ|thẳm|quyên|mâu|thué|ngán sách|chỉ tiết|thỉ hành|hiều|cầu trúc)\b", text):
        reasons.append("likely_ocr_vietnamese_accent_error")
    if re.search(r"\b[A-ZĐ]{0,3}[IÌÏJ]\d{1,3}/\d{4}/QH", text):
        reasons.append("likely_ocr_document_number_error")
    if "THƯ VIỆN PHÁP LUẬT" in text or "ThuVienPhap" in text:
        reasons.append("watermark_leftover")
    return reasons


def build_accent_review(markdown: str, output_name: str) -> dict:
    entries = []
    omitted = 0
    for idx, line in enumerate(markdown.splitlines(), start=1):
        reasons = suspicious_reasons(line)
        if not reasons:
            continue
        if len(entries) < MAX_ACCENT_REVIEW_PER_FILE:
            entries.append({"line": idx, "reasons": reasons, "text": line})
        else:
            omitted += 1
    return {"file": output_name, "entries": entries, "omitted_after_limit": omitted}


def output_stem(path: Path) -> str:
    stem = normalize_unicode(path.stem).strip()
    stem = stem.replace("+", " + ")
    stem = re.sub(r'[<>:"/\\|?*]+', " ", stem)
    stem = re.sub(r"\s+", " ", stem)
    stem = re.sub(r"\s+([,.;])", r"\1", stem)
    stem = stem.strip(" ._-")
    return stem or "document"


def duplicate_choice(paths: list[Path]) -> Path:
    def key(path: Path) -> tuple[int, int, str]:
        normalized_stem = match_key(path.stem).lower()
        has_copy_suffix = 1 if re.search(r"\(\d+\)", path.stem) or "ban sao" in normalized_stem else 0
        return (has_copy_suffix, len(path.name), path.name.lower())

    return sorted(paths, key=key)[0]


def select_unique_by_hash(raw_files: list[Path]) -> tuple[list[Path], list[dict], dict[Path, dict]]:
    by_hash: dict[str, list[Path]] = {}
    sizes: dict[Path, int] = {}
    for path in raw_files:
        digest = sha256_file(path)
        by_hash.setdefault(digest, []).append(path)
        sizes[path] = path.stat().st_size

    selected: list[Path] = []
    duplicate_report: list[dict] = []
    skipped: dict[Path, dict] = {}

    for digest, paths in sorted(by_hash.items(), key=lambda item: min(p.name.lower() for p in item[1])):
        if len(paths) == 1:
            selected.append(paths[0])
            continue
        chosen = duplicate_choice(paths)
        selected.append(chosen)
        skipped_paths = [p for p in sorted(paths, key=lambda p: p.name.lower()) if p != chosen]
        for skipped_path in skipped_paths:
            skipped[skipped_path] = {
                "status": "skipped_duplicate_hash",
                "duplicate_of": str(chosen),
                "sha256": digest,
            }
        duplicate_report.append(
            {
                "sha256": digest,
                "selected": str(chosen),
                "skipped": [str(p) for p in skipped_paths],
                "files": [{"path": str(p), "size": sizes[p]} for p in sorted(paths, key=lambda p: p.name.lower())],
            }
        )
    return sorted(selected, key=lambda p: p.name.lower()), duplicate_report, skipped


def metadata_key(doc: ExtractedDocument) -> tuple[str, str] | None:
    doc_number = match_key(doc.doc_number)
    title = match_key(doc.title)
    if not doc_number or not title:
        return None
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", doc_number):
        return None
    return doc_number, title


def choose_metadata_group(docs: list[ExtractedDocument]) -> ExtractedDocument:
    docx_docs = [doc for doc in docs if doc.source.suffix.lower() == ".docx"]
    if docx_docs:
        return sorted(docx_docs, key=lambda doc: doc.source.name.lower())[0]
    return sorted(docs, key=lambda doc: doc.source.name.lower())[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert legal raw DOCX/PDF files to cleaned Markdown.")
    parser.add_argument("--raw", default="data/raw", type=Path, help="Raw input directory")
    parser.add_argument("--out", default="data/processed", type=Path, help="Processed Markdown output directory")
    args = parser.parse_args()

    raw_dir = args.raw
    out_dir = args.out
    reports_dir = out_dir / "_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        raise SystemExit(f"Raw directory not found: {raw_dir}")

    raw_files = sorted(
        [p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES],
        key=lambda p: (str(p.relative_to(raw_dir)).lower(), p.name.lower()),
    )
    selected_files, duplicate_report, skipped_by_hash = select_unique_by_hash(raw_files)

    manifest_entries: list[dict] = []
    extracted_docs: list[ExtractedDocument] = []

    for path in selected_files:
        if path.suffix.lower() == ".docx":
            doc = extract_docx(path)
        else:
            doc = extract_pdf(path)
        markdown, headings, title = blocks_to_markdown(doc.blocks)
        doc.title = title
        doc.doc_number = extract_doc_number(doc.blocks, path)
        doc.blocks = [Block(kind="para", text=markdown, md=markdown)]
        doc.warnings.extend([] if markdown.strip() else ["empty_markdown_output"])
        doc.warnings.extend([] if headings else ["no_markdown_headings_detected"])
        doc._markdown = markdown  # type: ignore[attr-defined]
        doc._headings = headings  # type: ignore[attr-defined]
        extracted_docs.append(doc)

    metadata_groups: dict[tuple[str, str], list[ExtractedDocument]] = {}
    for doc in extracted_docs:
        key = metadata_key(doc)
        if key:
            metadata_groups.setdefault(key, []).append(doc)

    metadata_skipped: dict[Path, dict] = {}
    for docs in metadata_groups.values():
        suffixes = {doc.source.suffix.lower() for doc in docs}
        if len(docs) <= 1 or suffixes != {".docx", ".pdf"}:
            continue
        chosen = choose_metadata_group(docs)
        for doc in docs:
            if doc is chosen:
                continue
            metadata_skipped[doc.source] = {
                "status": "skipped_duplicate_metadata_prefer_docx",
                "duplicate_of": str(chosen.source),
                "doc_number": doc.doc_number,
                "title": doc.title,
            }

    accent_review = []
    ocr_corrections: list[dict] = []
    processed_count = 0
    for doc in extracted_docs:
        if doc.source in metadata_skipped:
            info = metadata_skipped[doc.source]
            manifest_entries.append(
                {
                    "source": str(doc.source),
                    "status": info["status"],
                    "duplicate_of": info["duplicate_of"],
                    "doc_number": info.get("doc_number", ""),
                    "title": info.get("title", ""),
                    "warnings": doc.warnings,
                }
            )
            continue

        markdown = doc._markdown  # type: ignore[attr-defined]
        headings = doc._headings  # type: ignore[attr-defined]
        out_path = out_dir / f"{output_stem(doc.source)}.md"
        corrections: list[dict] = []
        if doc.extractor == "pdftotext-layout":
            markdown, corrections = apply_contextual_ocr_fixes(markdown, out_path.name)
        ocr_corrections.extend(corrections)
        out_path.write_text(markdown, encoding="utf-8", newline="\n")
        processed_count += 1

        review = build_accent_review(markdown, out_path.name)
        if review["entries"] or review["omitted_after_limit"]:
            accent_review.append(review)

        manifest_entries.append(
            {
                "source": str(doc.source),
                "output": str(out_path),
                "status": "processed",
                "extractor": doc.extractor,
                "doc_number": doc.doc_number,
                "title": doc.title,
                "line_count": len(markdown.splitlines()),
                "char_count": len(markdown),
                "heading_count": len(headings),
                "ocr_correction_count": len(corrections),
                "headings_sample": headings[:12],
                "warnings": doc.warnings,
            }
        )

    for raw_path in raw_files:
        if raw_path in skipped_by_hash:
            info = skipped_by_hash[raw_path]
            manifest_entries.append(
                {
                    "source": str(raw_path),
                    "status": info["status"],
                    "duplicate_of": info["duplicate_of"],
                    "sha256": info["sha256"],
                    "warnings": [],
                }
            )

    manifest = {
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
        "raw_file_count": len(raw_files),
        "processed_markdown_count": processed_count,
        "duplicate_hash_group_count": len(duplicate_report),
        "metadata_duplicate_skipped_count": len(metadata_skipped),
        "ocr_correction_count": len(ocr_corrections),
        "entries": sorted(manifest_entries, key=lambda item: item["source"].lower()),
    }

    (reports_dir / "duplicate_hashes.json").write_text(
        json.dumps(duplicate_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    (reports_dir / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    (reports_dir / "accent_review.json").write_text(
        json.dumps(accent_review, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    (reports_dir / "ocr_corrections.json").write_text(
        json.dumps(ocr_corrections, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    print(f"Raw files: {len(raw_files)}")
    print(f"Markdown files written: {processed_count}")
    print(f"Duplicate hash groups: {len(duplicate_report)}")
    print(f"OCR corrections: {len(ocr_corrections)}")
    print(f"Reports: {reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
