import os
import json
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

# REGEX CẢI TIẾN: Nhận diện tốt hơn Điều 15a, Điều 15B, Điều 3-1, v.v.
ARTICLE_PATTERN = re.compile(
    r'^(?:#{1,6}\s*)?(?:\*{1,2})?Điều\s+(\d+[A-Za-z]?(?:-\d+)?)(?:\*{1,2})?[.\-:–]?\s*(.*)',
    re.MULTILINE
)

# REGEX PHỤ: Dùng để chia nhỏ theo Khoản nếu Điều quá dài (Ví dụ: "1. ", "2. ")
CLAUSE_PATTERN = re.compile(r'^\s*(\d+)\.\s+(.*)', re.MULTILINE)

def _split_md_into_articles(content: str, law_name: str, source_file: str) -> list:
    """
    Tách nội dung file .md thành danh sách các điều luật.
    Linh hoạt với mọi format heading markdown và tự động chia khoản nếu điều quá dài.
    """
    articles = []
    matches = list(ARTICLE_PATTERN.finditer(content))

    if not matches:
        print(f"  ⚠️  Không tìm thấy 'Điều X' nào trong {source_file} — đưa toàn bộ làm 1 chunk")
        articles.append({
            "source": source_file,
            "law_name": law_name,
            "group": "Luật Thuế Việt Nam",
            "article": "Toàn văn",
            "title": law_name,
            "content": content.strip(),
            "text": f"Văn bản pháp luật: {law_name}\nNội dung:\n{content.strip()}"
        })
        return articles

    for idx, match in enumerate(matches):
        article_number = match.group(1)        # "1", "2", "10", "15a"...
        article_inline_title = match.group(2).strip()  # tiêu đề ngay trên cùng dòng

        # Nội dung từ điểm match này đến trước match kế tiếp
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        article_body = content[start:end].strip()

        # Lấy dòng đầu làm tiêu đề nếu không có trên cùng dòng
        first_line = article_body.split('\n')[0].strip()
        clean_title = re.sub(r'^#{1,6}\s*|\*{1,2}', '', first_line).strip()
        title = article_inline_title if article_inline_title else clean_title

        # TỐI ƯU CHUNK SIZE: Nếu điều luật quá dài (> 2000 ký tự), tự động chia nhỏ theo Khoản
        if len(article_body) > 2000:
            clauses = list(CLAUSE_PATTERN.finditer(article_body))
            if clauses:
                for c_idx, c_match in enumerate(clauses):
                    c_start = c_match.start()
                    c_end = clauses[c_idx + 1].start() if c_idx + 1 < len(clauses) else len(article_body)
                    clause_body = article_body[c_start:c_end].strip()
                    
                    full_text = (
                        f"Văn bản pháp luật: {law_name}\n"
                        f"Vị trí: Điều {article_number} - {title} (Khoản {c_match.group(1)})\n"
                        f"Nội dung:\n{clause_body}"
                    )
                    articles.append({
                        "source": source_file,
                        "law_name": law_name,
                        "group": "Luật Thuế Việt Nam",
                        "article": f"Điều {article_number} Khoản {c_match.group(1)}",
                        "title": title,
                        "content": clause_body,
                        "text": full_text
                    })
                continue # Bỏ qua việc lưu cả Điều to nếu đã chia nhỏ thành công

        full_text = (
            f"Văn bản pháp luật: {law_name}\n"
            f"Vị trí trích dẫn: Điều {article_number} - {title}\n"
            f"Nội dung:\n{article_body}"
        )

        articles.append({
            "source": source_file,
            "law_name": law_name,
            "group": "Luật Thuế Việt Nam",
            "article": f"Điều {article_number}",
            "title": title,
            "content": article_body,
            "text": full_text
        })

    return articles

def load_all_laws() -> list:
    """
    Quét tự động toàn bộ thư mục data/processed, tự nhận diện file .md và .json 
    để nạp vào hệ thống mà không cần khai báo thủ công từng thư mục con.
    """
    if not os.path.exists(PROCESSED_DIR):
        raise FileNotFoundError(f"❌ Không tìm thấy thư mục data: {PROCESSED_DIR}")

    laws = []
    print(f"\n📂 Đang quét tự động toàn bộ dữ liệu: {PROCESSED_DIR}")
    
    for root, dirs, files in os.walk(PROCESSED_DIR):
        # Bỏ qua các thư mục ẩn hoặc báo cáo
        dirs[:] = [d for d in dirs if not d.startswith('_')]

        for file in files:
            path = os.path.join(root, file)
            
            # 1. XỬ LÝ FILE MARKDOWN (.md)
            if file.endswith(".md"):
                law_name = file.replace(".md", "").replace("_", " ").replace("-", " ").title()
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if not content.strip(): 
                        continue
                    
                    articles = _split_md_into_articles(content, law_name, file)
                    laws.extend(articles)
                except Exception as e:
                    print(f"  ❌ Lỗi đọc file MD {file}: {e}")

            # 2. XỬ LÝ FILE JSON (.json)
            elif file.endswith(".json"):
                # Tự định nghĩa loại văn bản thông minh dựa theo tên thư mục cha (root)
                prefix = "Văn bản"
                root_lower = root.lower()
                if "decree" in root_lower or "nghi_dinh" in root_lower: 
                    prefix = "Nghị định"
                elif "resolution" in root_lower or "nghi_quyet" in root_lower: 
                    prefix = "Nghị quyết"
                elif "circular" in root_lower or "thong_tu" in root_lower or "tt" in root_lower: 
                    prefix = "Thông tư"

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    for art in data.get("articles", []):
                        full_text = (
                            f"{prefix}: {data.get('law_name', 'Không rõ')}\n"
                            f"Nhóm: {data.get('group', 'Luật Thuế Việt Nam')}\n"
                            f"Điều: {art.get('article', '')}\n"
                            f"Tiêu đề: {art.get('title', '')}\n"
                            f"Nội dung: {art.get('content', '')}"
                        )
                        laws.append({
                            "source": file,
                            "law_name": data.get("law_name"),
                            "group": data.get("group", "Luật Thuế Việt Nam"),
                            "article": art.get("article"),
                            "title": art.get("title"),
                            "content": art.get("content"),
                            "text": full_text
                        })
                except Exception as e:
                    print(f"  ❌ Lỗi đọc JSON {file}: {e}")

    print(f"\n🚀 Tổng cộng nạp thành công: {len(laws)} phân đoạn dữ liệu pháp luật!\n")
    return laws