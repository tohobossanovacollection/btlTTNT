import os
import re
import json

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../")
)

PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

RESOLUTION_DIR = os.path.join(PROCESSED_DIR, "resolutions", "nq_01_2024")
DECREE_DIR = os.path.join(PROCESSED_DIR, "decrees", "nd_82_2020")
DECREE_123_DIR = os.path.join(PROCESSED_DIR, "decrees", "nd_123_2015")
DECREE_126_DIR = os.path.join(PROCESSED_DIR, "decrees", "nd_126_2014")
DECREE_207_DIR = os.path.join(PROCESSED_DIR, "decrees", "nd_207_2025")
THONGTU_01_DIR = os.path.join(PROCESSED_DIR, "decrees", "ttlt_01_2016")

# REGEX TỔNG QUÁT: nhận diện dòng bắt đầu một Điều luật mới
# Khớp với tất cả các format phổ biến trong file .md luật VN:
#   #### Điều 1. ...
#   ## Điều 1. ...
#   **Điều 1.**  ...
#   Điều 1:  ...
#   Điều 1 -  ...
ARTICLE_PATTERN = re.compile(
    r'^(?:#{1,6}\s*)?(?:\*{1,2})?Điều\s+(\d+[a-z]?)(?:\*{1,2})?[.\-:–]?\s*(.*)',
    re.MULTILINE
)

def _split_md_into_articles(content: str, law_name: str, source_file: str) -> list:
    """
    Tách nội dung file .md thành danh sách các điều luật.
    Linh hoạt với mọi format heading markdown.
    """
    articles = []

    matches = list(ARTICLE_PATTERN.finditer(content))

    if not matches:
        # Không tìm thấy điều nào → log cảnh báo, đưa cả file vào 1 chunk
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
        # Loại bỏ markdown heading ký tự # và ** khỏi tiêu đề
        clean_title = re.sub(r'^#{1,6}\s*|\*{1,2}', '', first_line).strip()
        title = article_inline_title if article_inline_title else clean_title

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
    if not os.path.exists(PROCESSED_DIR):
        raise FileNotFoundError(f"❌ Không tìm thấy thư mục data: {PROCESSED_DIR}")

    laws = []

    # 1. ĐỌC TẤT CẢ FILE .MD (kể cả trong thư mục con)
    print(f"\n📂 Đang quét thư mục: {PROCESSED_DIR}")
    for root, dirs, files in os.walk(PROCESSED_DIR):
        # Bỏ qua thư mục _reports (chứa file báo cáo, không phải luật)
        dirs[:] = [d for d in dirs if not d.startswith('_')]

        for file in files:
            if not file.endswith(".md"):
                continue

            path = os.path.join(root, file)
            law_name = (
                file.replace(".md", "")
                    .replace("_", " ")
                    .replace("-", " ")
                    .title()
            )

            print(f"  📄 Đang đọc: {file}")

            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content.strip():
                    print(f"  ⚠️  File rỗng, bỏ qua: {file}")
                    continue

                articles = _split_md_into_articles(content, law_name, file)
                print(f"     → Tìm thấy {len(articles)} điều/chunk")
                laws.extend(articles)

            except Exception as e:
                print(f"  ❌ Lỗi đọc file {file}: {e}")
                continue

    # 2. ĐỌC CÁC FILE JSON TRONG THƯ MỤC CON
    additional_dirs = [
        (RESOLUTION_DIR,  "Văn bản"),
        (DECREE_DIR,      "Nghị định"),
        (DECREE_123_DIR,  "Nghị định"),
        (DECREE_126_DIR,  "Nghị định"),
        (DECREE_207_DIR,  "Nghị định"),
        (THONGTU_01_DIR,  "Thông tư"),
    ]

    for folder_path, prefix in additional_dirs:
        if not os.path.exists(folder_path):
            continue

        for file in os.listdir(folder_path):
            if not file.endswith(".json"):
                continue

            path = os.path.join(folder_path, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for art in data.get("articles", []):
                    full_text = (
                        f"{prefix}: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                    laws.append({
                        "source": file,
                        "law_name": data.get("law_name"),
                        "group": data.get("group"),
                        "article": art.get("article"),
                        "title": art.get("title"),
                        "content": art.get("content"),
                        "text": full_text
                    })

            except Exception as e:
                print(f"  ❌ Lỗi đọc JSON {file}: {e}")
                continue

    print(f"\n🚀 Tổng cộng nạp thành công: {len(laws)} phân đoạn dữ liệu pháp luật!\n")
    return laws
