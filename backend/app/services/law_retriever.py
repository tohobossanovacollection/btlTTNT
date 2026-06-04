import os
import json

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../")
)

LAW_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "laws",
    "luat_hngd_2014"
)
RESOLUTION_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "resolutions",
    "nq_01_2024"
)
DECREE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "decrees",
    "nd_82_2020"
)
DECREE_123_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "decrees",
    "nd_123_2015"
)
DECREE_126_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "decrees",
    "nd_126_2014"
)
DECREE_207_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "decrees",
    "nd_207_2025"
)
THONGTU_01_DIR = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "decrees",
    "ttlt_01_2016"
)
def load_all_laws():
    #== load luật=#
    if not os.path.exists(LAW_DIR):
        raise FileNotFoundError(f"❌ Không tìm thấy thư mục luật: {LAW_DIR}")

    laws = []

    for file in os.listdir(LAW_DIR):
        if not file.endswith(".json"):
            continue

        path = os.path.join(LAW_DIR, file)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for art in data.get("articles", []):
            laws.append({
                "source": file,
                "law_name": data.get("law_name"),
                "group": data.get("group"),
                "article": art.get("article"),
                "title": art.get("title"),
                "content": art.get("content"),
                # 🔑 TEXT DÙNG CHO EMBEDDING / SEMANTIC SEARCH
                "text": (
                    f"Luật: {data.get('law_name')}\n"
                    f"Nhóm: {data.get('group')}\n"
                    f"Điều: {art.get('article')}\n"
                    f"Tiêu đề: {art.get('title')}\n"
                    f"Nội dung: {art.get('content')}"
                )
            })
        # ===== LOAD NGHỊ QUYẾT =====
    if os.path.exists(RESOLUTION_DIR):
        for file in os.listdir(RESOLUTION_DIR):
            if not file.endswith(".json"):
                continue

            path = os.path.join(RESOLUTION_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for art in data.get("articles", []):
                laws.append({
                    "source": file,
                    "law_name": data.get("law_name"),
                    "group": data.get("group"),
                    "article": art.get("article"),
                    "title": art.get("title"),
                    "content": art.get("content"),
                    "text": (
                        f"Văn bản: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                })
        # ===== LOAD NGHỊ ĐỊNH =====
    if os.path.exists(DECREE_DIR):
        for file in os.listdir(DECREE_DIR):
            if not file.endswith(".json"):
                continue

            path = os.path.join(DECREE_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for art in data.get("articles", []):
                laws.append({
                    "source": file,
                    "law_name": data.get("law_name"),
                    "group": data.get("group"),
                    "article": art.get("article"),
                    "title": art.get("title"),
                    "content": art.get("content"),

                    # 🔑 TEXT CHO EMBEDDING
                    "text": (
                        f"Nghị định: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                })
        # ===== LOAD NGHỊ ĐỊNH 123/2015 =====
    if os.path.exists(DECREE_123_DIR):
        for file in os.listdir(DECREE_123_DIR):
            if not file.endswith(".json"):
                continue

            path = os.path.join(DECREE_123_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for art in data.get("articles", []):
                laws.append({
                    "source": file,
                    "law_name": data.get("law_name"),
                    "group": data.get("group"),
                    "article": art.get("article"),
                    "title": art.get("title"),
                    "content": art.get("content"),

                    "text": (
                        f"Nghị định: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                })
            # ===== LOAD NGHỊ ĐỊNH 126/2014 =====
    if os.path.exists(DECREE_126_DIR):
        for file in os.listdir(DECREE_126_DIR):
            if not file.endswith(".json"):
                continue

            path = os.path.join(DECREE_126_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for art in data.get("articles", []):
                laws.append({
                    "source": file,
                    "law_name": data.get("law_name"),
                    "group": data.get("group"),
                    "article": art.get("article"),
                    "title": art.get("title"),
                    "content": art.get("content"),

                    "text": (
                        f"Nghị định: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                })
                # ===== LOAD NGHỊ ĐỊNH 207/2025 =====
    if os.path.exists(DECREE_207_DIR):
        for file in os.listdir(DECREE_207_DIR):
            if not file.endswith(".json"):
                continue

            path = os.path.join(DECREE_207_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for art in data.get("articles", []):
                laws.append({
                    "source": file,
                    "law_name": data.get("law_name"),
                    "group": data.get("group"),
                    "article": art.get("article"),
                    "title": art.get("title"),
                    "content": art.get("content"),

                    "text": (
                        f"Nghị định: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                })
                    # ===== LOAD thongtu 01/2016 =====
    if os.path.exists(THONGTU_01_DIR):
        for file in os.listdir(THONGTU_01_DIR):
            if not file.endswith(".json"):
                continue

            path = os.path.join(THONGTU_01_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for art in data.get("articles", []):
                laws.append({
                    "source": file,
                    "law_name": data.get("law_name"),
                    "group": data.get("group"),
                    "article": art.get("article"),
                    "title": art.get("title"),
                    "content": art.get("content"),

                    "text": (
                        f"Nghị định: {data.get('law_name')}\n"
                        f"Nhóm: {data.get('group')}\n"
                        f"Điều: {art.get('article')}\n"
                        f"Tiêu đề: {art.get('title')}\n"
                        f"Nội dung: {art.get('content')}"
                    )
                })
    return laws
