# 1. TIỀN XỬ LÝ DỮ LIỆU

## 1.1 Trích Xuất Text Từ PDF (pdfplumber)

> **Phương pháp này CHƯA học trên lớp**

**Mô tả:** `pdfplumber` là thư viện Python trích xuất text từ PDF với độ chính xác cao hơn PyPDF2, đặc biệt xử lý tốt các bảng biểu và layout phức tạp. Đây là bước đầu tiên bắt buộc trước khi áp dụng bất kỳ phương pháp NLP nào.

```python
import pdfplumber
import re

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Trích xuất text từ PDF văn bản pháp lý.
    Xử lý từng trang, bỏ qua trang trống.
    """
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text and text.strip():          # Bỏ qua trang trống
                full_text.append(text)
    return "\n\n".join(full_text)

# Áp dụng cho tất cả văn bản
from pathlib import Path

extracted = {}
for pdf_file in Path("data/raw").rglob("*.pdf"):
    text = extract_text_from_pdf(str(pdf_file))
    out_path = Path("data/extracted") / (pdf_file.stem + ".txt")
    out_path.write_text(text, encoding="utf-8")
    extracted[pdf_file.name] = len(text.split())
    print(f"✅ {pdf_file.name}: {len(text.split()):,} từ")
```

**So sánh Trước – Sau:**

```
TRƯỚC (PDF binary): %PDF-1.4 1 0 obj << /Type /Catalog ... >>
SAU  (text thuần): "Điều 55. Thời hạn nộp thuế
                    Khoản 1. Trường hợp người nộp thuế tính thuế..."
```

> **Nguồn:** pdfplumber – https://github.com/jsvine/pdfplumber

---

## 1.2 Sửa Lỗi Encoding với ftfy

> **Phương pháp này CHƯA học trên lớp**

**Mô tả:** `ftfy` (Fixes Text For You) tự động phát hiện và sửa các lỗi encoding phổ biến xảy ra khi PDF dùng encoding không chuẩn. Tiếng Việt đặc biệt dễ bị lỗi này do có nhiều ký tự có dấu phức tạp.

```python
import ftfy

def fix_encoding(text: str) -> str:
    return ftfy.fix_text(text)

# Ví dụ thực tế từ dữ liệu
loi_1 = "Doanh nghiá»‡p phải nộp thuáº¿"
sau_1 = ftfy.fix_text(loi_1)
# → "Doanh nghiệp phải nộp thuế"

loi_2 = "thá»i háº¡n náº¡p thuáº¿ GTGT"
sau_2 = ftfy.fix_text(loi_2)
# → "thời hạn nạp thuế GTGT"
```

**So sánh Trước – Sau:**

| Trạng Thái | Văn Bản |
|-----------|---------|
| TRƯỚC | `"Doanh nghiá»‡p phải nộp thuáº¿ thu nháº­p"` |
| SAU | `"Doanh nghiệp phải nộp thuế thu nhập"` |
| TRƯỚC | `"Ä\x90iá»\x81u 55. Thá»\x9di háº¡n náº\x99p thuáº¿"` |
| SAU | `"Điều 55. Thời hạn nộp thuế"` |

> **Nguồn:** Benoit Sagot. *ftfy – fixes text for you*. https://ftfy.readthedocs.io

---

## 1.3 Làm Sạch Văn Bản Pháp Lý (Legal Text Cleaning)

> **Phương pháp này CHƯA học trên lớp**

**Mô tả:** Pipeline làm sạch 6 bước đặc thù cho văn bản pháp lý Việt Nam, loại bỏ các phần tử không mang thông tin pháp lý (số trang, header, ký tự lỗi) mà vẫn giữ nguyên nội dung điều khoản.

```python
import re

def clean_legal_text(text: str) -> str:
    """
    Pipeline làm sạch văn bản pháp lý thuế — 6 bước tuần tự
    """
    # BƯỚC 1: Loại bỏ số trang (Trang 1/98, -5-, Page 3)
    text = re.sub(r'(Trang|Page)\s*\d+\s*/?\s*\d*', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\-\s*\d+\s*\-', ' ', text)

    # BƯỚC 2: Loại bỏ header/footer lặp lại mỗi trang
    headers = [
        r'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM',
        r'Độc lập\s*[–-]\s*Tự do\s*[–-]\s*Hạnh phúc',
        r'BỘ TÀI CHÍNH\s*[\n\r]',
        r'TỔNG CỤC THUẾ\s*[\n\r]',
        r'QUỐC HỘI\s*[\n\r]',
    ]
    for h in headers:
        text = re.sub(h, '\n', text, flags=re.IGNORECASE)

    # BƯỚC 3: Loại bỏ ký tự điều khiển và OCR lỗi
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', ' ', text)
    text = re.sub(r'[■□▪▫◆◇●○]', ' ', text)

    # BƯỚC 4: Chuẩn hóa dấu câu typography → ASCII
    text = text.replace('\u2013', '-').replace('\u2014', '-')   # em dash, en dash
    text = text.replace('\u2018', "'").replace('\u2019', "'")   # smart quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2026', '...')                        # ellipsis

    # BƯỚC 5: Chuẩn hóa khoảng trắng và dòng trống
    text = re.sub(r'[ \t]+', ' ', text)        # nhiều space → 1 space
    text = re.sub(r'\n{3,}', '\n\n', text)     # nhiều dòng trống → 2

    # BƯỚC 6: Loại bỏ dòng quá ngắn (<10 ký tự, thường là header vỡ)
    lines = text.split('\n')
    lines = [l for l in lines if len(l.strip()) > 10 or l.strip() == '']
    text = '\n'.join(lines)

    return text.strip()
```

**So sánh Trước – Sau (đoạn thực tế):**

```
╔══════════════════════════════════════════════════════════╗
║ TRƯỚC (text thô từ PDF)                                  ║
╠══════════════════════════════════════════════════════════╣
║ QUỐC HỘI                                                 ║
║ -------                                                  ║
║ CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM                      ║
║ Độc lập – Tự do – Hạnh phúc                              ║
║ ————————————                                             ║
║ Luật số: 38/2019/QH14                                    ║
║                                                          ║
║ Trang 45/98                                              ║
║                                                          ║
║ Điều 55. Thá»ˆi hạn nộp thuáº¿                           ║
║ Khoản 1. Trường hợp người nộp thuế tính thuế, thời       ║
║ hạn nộp thuế chậm  nhất là  ngày  cuối cùng của thời    ║
║ hạn nộp hồ sơ khai thuế■                                ║
╚══════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════╗
║ SAU (đã làm sạch)                                        ║
╠══════════════════════════════════════════════════════════╣
║ Điều 55. Thời hạn nộp thuế                               ║
║ Khoản 1. Trường hợp người nộp thuế tính thuế, thời       ║
║ hạn nộp thuế chậm nhất là ngày cuối cùng của thời        ║
║ hạn nộp hồ sơ khai thuế.                                 ║
╚══════════════════════════════════════════════════════════╝
```

---

## 1.4 Chuẩn Hóa Từ Viết Tắt Chuyên Ngành

> **Phương pháp này CHƯA học trên lớp**

**Mô tả:** Các văn bản pháp lý khác nhau dùng cách viết tắt không nhất quán cho cùng một khái niệm. Ví dụ: "thuế GTGT", "thuế giá trị gia tăng", "VAT" đều chỉ cùng một loại thuế. Chuẩn hóa về một dạng thống nhất giúp embedding nhận diện đúng cùng khái niệm.

```python
TAX_ABBR = {
    # Loại thuế — chuẩn hóa về dạng viết đầy đủ
    r'\bGTGT\b':  'giá trị gia tăng',
    r'\bTNDN\b':  'thu nhập doanh nghiệp',
    r'\bTNCN\b':  'thu nhập cá nhân',
    r'\bXNK\b':   'xuất nhập khẩu',
    r'\bTTĐB\b':  'tiêu thụ đặc biệt',
    r'\bVAT\b':   'giá trị gia tăng',     # Từ tiếng Anh → Việt

    # Tổ chức
    r'\bTCT\b':   'Tổng cục Thuế',
    r'\bCQT\b':   'cơ quan thuế',
    r'\bBTC\b':   'Bộ Tài chính',
    r'\bNNT\b':   'người nộp thuế',
    r'\bDN\b':    'doanh nghiệp',

    # Văn bản pháp lý
    r'\bNĐ\b':    'Nghị định',
    r'\bTT\b(?!\s*\d{1,2}:\d{2})': 'Thông tư',   # Không nhầm với giờ (TT 14:30)
    r'\bQĐ\b':    'Quyết định',
    r'\bCV\b':    'Công văn',
}

def expand_abbreviations(text: str) -> str:
    for pattern, replacement in TAX_ABBR.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
```

**So sánh Trước – Sau:**

| TRƯỚC | SAU |
|-------|-----|
| `"DN phải nộp thuế GTGT hàng quý"` | `"doanh nghiệp phải nộp thuế giá trị gia tăng hàng quý"` |
| `"CQT ban hành NĐ hướng dẫn"` | `"cơ quan thuế ban hành Nghị định hướng dẫn"` |
| `"thuế VAT và TNDN"` | `"thuế giá trị gia tăng và thu nhập doanh nghiệp"` |

---

## 1.5 Bổ Sung Metadata Tự Động (Metadata Enrichment)

> **Phương pháp này CHƯA học trên lớp — quan trọng cho filtered retrieval**

**Mô tả:** Sau khi trích xuất, sửa lỗi encoding, làm sạch và chuẩn hóa, mỗi văn bản được gắn thêm metadata tự động bằng regex. Metadata cho phép **filtered retrieval**: khi người dùng hỏi về thuế GTGT, hệ thống ưu tiên tìm trong các văn bản liên quan đến GTGT thay vì toàn bộ corpus → nhanh hơn và chính xác hơn.

```python
import json
import re
from pathlib import Path

def extract_metadata(text: str, source_file: str) -> dict:
    meta = {"source": source_file}

    # Xác định loại văn bản
    fname = source_file.lower()
    if "luat" in fname:          meta["doc_type"] = "luat"
    elif "nd_" in fname:         meta["doc_type"] = "nghi_dinh"
    elif "tt_" in fname:         meta["doc_type"] = "thong_tu"
    elif "cv_" in fname:         meta["doc_type"] = "cong_van"

    # Trích số Điều
    m = re.search(r'Điều\s+(\d+)', text)
    if m: meta["article"] = int(m.group(1))

    # Trích loại thuế được đề cập
    tax_map = {
        "GTGT":  r'giá trị gia tăng|GTGT',
        "TNDN":  r'thu nhập doanh nghiệp|TNDN',
        "TNCN":  r'thu nhập cá nhân|TNCN',
        "XNK":   r'xuất nhập khẩu|XNK',
        "TTDB":  r'tiêu thụ đặc biệt|TTĐB',
    }
    meta["tax_types"] = [k for k, p in tax_map.items()
                         if re.search(p, text, re.IGNORECASE)]

    # Xác định chủ đề nội dung
    if re.search(r'thời hạn|kỳ hạn|hạn nộp', text, re.I):
        meta["topic"] = "deadline"
    elif re.search(r'thuế suất|mức thuế', text, re.I):
        meta["topic"] = "tax_rate"
    elif re.search(r'xử phạt|phạt|vi phạm', text, re.I):
        meta["topic"] = "penalty"
    elif re.search(r'hoàn thuế|khấu trừ', text, re.I):
        meta["topic"] = "refund"
    elif re.search(r'miễn thuế|giảm thuế', text, re.I):
        meta["topic"] = "exemption"
    else:
        meta["topic"] = "general"

    # Trích năm văn bản từ tên file
    yr = re.search(r'(20\d{2})', source_file)
    if yr: meta["year"] = int(yr.group(1))

    return meta

# Áp dụng cho các văn bản đã xử lý và lưu lại
enriched_records = []
for txt_file in Path("data/processed").glob("*.txt"):
    text = txt_file.read_text(encoding="utf-8")
    enriched_records.append({
        "document_id": txt_file.stem,
        "text": text,
        "metadata": extract_metadata(text, txt_file.name),
    })

with open("data/processed/enriched_documents.jsonl", "w", encoding="utf-8") as f:
    for record in enriched_records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

**Cấu trúc văn bản hoàn chỉnh sau enrichment:**

```json
{
  "document_id": "luat_quan_ly_thue_38_2019",
  "text": "Điều 55. Thời hạn nộp thuế\nKhoản 1. Trường hợp người nộp thuế tính thuế, thời hạn nộp thuế chậm nhất là ngày cuối cùng của thời hạn nộp hồ sơ khai thuế...",
  "metadata": {
    "source":    "luat_quan_ly_thue_38_2019.txt",
    "doc_type":  "luat",
    "article":   55,
    "tax_types": ["GTGT", "TNDN", "TNCN"],
    "topic":     "deadline",
    "year":      2019
  }
}
```

---

## 1.6 Phương Pháp Đã Học Trên Lớp (Áp Dụng Trong Dự Án)

### a) Vectorization — Word Embeddings (Sentence Transformers)

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# Đây là bước vectorization CHÍNH trong RAG
model = SentenceTransformer('dangvantuan/vietnamese-embedding')

texts = [record['text'] for record in enriched_records]
embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True    # Chuẩn hóa để dùng cosine similarity
)
# Shape: (số văn bản, 768) — mỗi văn bản = vector 768 chiều

np.save('data/embeddings/law_embeddings.npy', embeddings)
print(f"Đã embed {len(embeddings)} văn bản → shape {embeddings.shape}")
```

### b) Vectorization — TF-IDF (dùng cho BM25 hybrid search)

```python
from sklearn.feature_extraction.text import TfidfVectorizer

# Dùng song song với embedding cho hybrid retrieval (dense + sparse)
tfidf = TfidfVectorizer(
    ngram_range=(1, 2),
    max_features=30000,
    sublinear_tf=True,
    min_df=2,
)
X_tfidf = tfidf.fit_transform(texts)
print(f"TF-IDF matrix: {X_tfidf.shape}")  # (số văn bản, 30000)
```
