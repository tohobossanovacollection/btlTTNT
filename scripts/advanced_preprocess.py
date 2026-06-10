import pdfplumber
import ftfy
import re
import json
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer

# --- CONFIG PATHS ---
RAW_DIR = Path("data/raw")
EXTRACTED_DIR = Path("data/extracted")
PROCESSED_DIR = Path("data/processed")
EMBED_DIR = Path("data/embeddings")

for d in [EXTRACTED_DIR, PROCESSED_DIR, EMBED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- 1.1 & 1.2: Extraction & Encoding Fix ---
def process_extraction():
    print("--- Đang trích xuất text từ PDF ---")
    count = 0
    for pdf_file in RAW_DIR.rglob("*.pdf"): 
        full_text = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(ftfy.fix_text(text))
        
        out_path = EXTRACTED_DIR / (pdf_file.stem + ".txt")
        out_path.write_text("\n\n".join(full_text), encoding="utf-8")
        if not any(len(ftfy.fix_text(t or '').strip()) > 0 for t in full_text):
            count += 1
            continue
        print(f"   [+] Thuật toán PDFPlumber: Trích xuất thành công {pdf_file.name}")
    print(f"✅ Giai đoạn 1 Hoàn tất: Đã chuyển đổi {count} file sang text thô.")
    return count

# --- 1.3: Legal Text Cleaning ---
def clean_legal_text(text: str) -> str:
    # BƯỚC 1: Loại bỏ số trang (Trang 1/98, -5-, Page 3)
    text = re.sub(r'(Trang|Page)\s*\d+\s*/?\s*\d*', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\-\s*\d+\s*\-', ' ', text)
    
    # BƯỚC 2: Loại bỏ các header/footer lặp lại (CỘNG HÒA XHCN VN, BỘ TÀI CHÍNH, QUỐC HỘI)
    headers = [r'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', r'Độc lập\s*[–-]\s*Tự do\s*[–-]\s*Hạnh phúc', r'BỘ TÀI CHÍNH\s*[\n\r]', r'TỔNG CỤC THUẾ\s*[\n\r]', r'QUỐC HỘI\s*[\n\r]']
    for h in headers:
        text = re.sub(h, '\n', text, flags=re.IGNORECASE)
    # BƯỚC 3: Loại bỏ ký tự điều khiển và OCR lỗi
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', ' ', text)
    text = re.sub(r'[■□▪▫◆◇●○]', ' ', text)
    # BƯỚC 4: Chuẩn hóa dấu câu typography → ASCII
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")   # smart quotes
    text = text.replace('\u2026', '...')                        # ellipsis
    # BƯỚC 5: Chuẩn hóa khoảng trắng và dòng trống
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # BƯỚC 6: Loại bỏ dòng quá ngắn (<10 ký tự, thường là header vỡ)
    lines = text.split('\n')
    lines = [l for l in lines if len(l.strip()) > 10 or l.strip() == '']
    text = '\n'.join(lines)
    return text.strip()

# --- 1.4: Abbreviations ---
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

# --- 1.5: Metadata Enrichment ---
def extract_metadata(text: str, filename: str) -> dict:
    meta = {"source": filename} # Tên file gốc

    # Xác định loại văn bản
    fname = filename.lower()
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
    yr = re.search(r'(20\d{2})', filename)
    if yr: meta["year"] = int(yr.group(1))
    return meta

# --- EXECUTION ---
def main():
    # Bước 1: Trích xuất
    extracted_count = process_extraction()
    if extracted_count == 0:
        print("⚠️ Không tìm thấy file PDF nào trong thư mục data/raw để xử lý.")
        return

    # Bước 2: Làm sạch và chuẩn hóa
    print("\n--- Đang làm sạch và Enrichment ---")
    print(f"   [~] Bắt đầu xử lý {len(list(EXTRACTED_DIR.glob('*.txt')))} file text thô...")
    enriched_records = []
    for txt_file in EXTRACTED_DIR.glob("*.txt"):
        print(f"      [+] Xử lý file: {txt_file.name}")
        raw_text = txt_file.read_text(encoding="utf-8")
        cleaned = clean_legal_text(raw_text)
        print(f"         [+] Thuật toán Clean Legal Text: Đã loại bỏ nhiễu và chuẩn hóa.")
        final_text = expand_abbreviations(cleaned)
        print(f"         [+] Thuật toán Expand Abbreviations: Đã mở rộng từ viết tắt.")
        
        # Lưu file md kết quả
        (PROCESSED_DIR / (txt_file.stem + ".md")).write_text(final_text, encoding="utf-8")
        
        enriched_records.append({
            "document_id": txt_file.stem,
            "text": final_text,
            "metadata": extract_metadata(final_text, txt_file.name)
        })
        print(f"         [+] Thuật toán Metadata Enrichment: Đã trích xuất metadata (doc_type: {enriched_records[-1]['metadata'].get('doc_type')}, topic: {enriched_records[-1]['metadata'].get('topic')}).")
        print(f"         [+] Đã lưu file Markdown sạch tại: {PROCESSED_DIR / (txt_file.stem + '.md')}")

    print(f"✅ Giai đoạn 2 Hoàn tất: Đã làm sạch và chuẩn hóa {len(enriched_records)} văn bản.")
    # Lưu manifest
    with open(PROCESSED_DIR / "enriched_documents.jsonl", "w", encoding="utf-8") as f:
        for record in enriched_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"   [+] Metadata Manifest: Đã lưu hồ sơ tại {PROCESSED_DIR / 'enriched_documents.jsonl'}")

    # Bước 3: Vectorization (1.6)
    if enriched_records:
        print("\n--- Giai đoạn 3: Chạy thuật toán Vectorization ---")
        texts = [r['text'] for r in enriched_records]
        
        # 3.2: Sparse Vector (TF-IDF)
        print("   [~] Đang chạy thuật toán Sparse Vector (TF-IDF)...")
        tfidf = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=30000,
            sublinear_tf=True,
            min_df=2,
        )
        X_tfidf = tfidf.fit_transform(texts)
        print(f"   [+] Thành công: Ma trận TF-IDF tạo ra với kích thước {X_tfidf.shape}")
        
        print(f"\n--- TỔNG KẾT QUY TRÌNH ---")
        print(f"🏁 Trạng thái: THÀNH CÔNG")
        print(f"📦 Tổng số lượng Chunks: {len(enriched_records)}")
        print(f"📂 Thư mục kết quả: {PROCESSED_DIR}")
        print(f"🚀 Hệ thống RAG đã sẵn sàng sử dụng dữ liệu mới.")
    else:
        print("⚠️ Cảnh báo: Không có dữ liệu để xử lý Vector.")

if __name__ == "__main__":
    main()