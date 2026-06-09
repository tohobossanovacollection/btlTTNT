# """
# evaluate_ragas.py — Đánh giá hệ thống RAG TaxBot bằng RAGAS framework
# ======================================================================
# Sử dụng Groq làm evaluator LLM (Tốc độ cao, tối ưu chi phí).

# Cài đặt:
#     pip install ragas datasets langchain-groq requests --break-system-packages
# """

# import os
# import json
# import time
# from pathlib import Path
# from typing import Any

# # ─── Cấu hình ──────────────────────────────────────────────────────────────
# GROQ_API_KEY = os.getenv("GROQ_API_KEY", "ĐIỀN_KEY_CỦA_BẠN_VÀO_ĐÂY")
# GROQ_MODEL   = os.getenv("GROQ_MODEL_NAME", "llama3-70b-8192")

# # Endpoint FastAPI backend
# BACKEND_URL  = "http://127.0.0.1:8000/api/v1/chat/"

# # Bộ câu hỏi thử nghiệm
# TEST_QUESTIONS = [
#     # Nhóm 1: Đơn giản
#     {
#         "group": "simple",
#         "question": "Thuế thu nhập doanh nghiệp là gì?",
#         "ground_truth": (
#             "Thuế thu nhập doanh nghiệp (TNDN) là loại thuế trực thu đánh vào phần thu nhập "
#             "chịu thuế của doanh nghiệp sau khi trừ các chi phí hợp lý, hợp lệ."
#         ),
#     },
#     {
#         "group": "simple",
#         "question": "Thuế suất thuế thu nhập doanh nghiệp phổ thông hiện hành là bao nhiêu phần trăm?",
#         "ground_truth": (
#             "Thuế suất thuế TNDN phổ thông hiện hành là 20% áp dụng cho đa số doanh nghiệp."
#         ),
#     },
#     {
#         "group": "simple",
#         "question": "Doanh nghiệp nhỏ và vừa có được ưu đãi thuế suất TNDN không?",
#         "ground_truth": (
#             "Có. Doanh nghiệp nhỏ và vừa đáp ứng điều kiện theo quy định có thể được áp dụng "
#             "thuế suất ưu đãi thấp hơn thuế suất phổ thông 20%."
#         ),
#     },
#     {
#         "group": "simple",
#         "question": "Những khoản chi nào không được trừ khi tính thuế thu nhập doanh nghiệp?",
#         "ground_truth": (
#             "Các khoản chi không được trừ gồm: chi không có hóa đơn chứng từ hợp lệ, "
#             "chi phạt vi phạm hành chính, chi không liên quan đến hoạt động sản xuất kinh doanh."
#         ),
#     },
#     # Nhóm 2: Phức tạp
#     {
#         "group": "complex",
#         "question": (
#             "Doanh nghiệp thành lập mới tại khu kinh tế nếu đồng thời có dự án đầu tư "
#             "vào lĩnh vực ưu đãi thì được hưởng những ưu đãi thuế TNDN nào và trong bao lâu?"
#         ),
#         "ground_truth": (
#             "Doanh nghiệp mới thành lập tại khu kinh tế, đầu tư vào lĩnh vực ưu đãi có thể "
#             "được miễn thuế TNDN trong thời gian nhất định, sau đó giảm thuế suất. Điều kiện, "
#             "thời hạn và mức ưu đãi cụ thể phụ thuộc vào quy định của từng khu kinh tế và "
#             "lĩnh vực đầu tư theo luật thuế TNDN và các nghị định hướng dẫn."
#         ),
#     },
#     {
#         "group": "complex",
#         "question": (
#             "Nếu doanh nghiệp vừa có thu nhập từ sản xuất trong nước, vừa có thu nhập từ "
#             "chuyển nhượng bất động sản, thì cách tính thuế TNDN cho từng phần thu nhập "
#             "như thế nào? Có được bù trừ lỗ giữa hai hoạt động không?"
#         ),
#         "ground_truth": (
#             "Thu nhập từ chuyển nhượng bất động sản phải hạch toán riêng, không được bù trừ "
#             "lỗ với thu nhập từ hoạt động sản xuất kinh doanh thông thường. Mỗi phần thu nhập "
#             "tính thuế theo quy định riêng."
#         ),
#     },
#     {
#         "group": "complex",
#         "question": (
#             "Doanh nghiệp có doanh thu dưới 20 tỷ nhưng hoạt động trong lĩnh vực không được "
#             "ưu đãi, đồng thời nộp chậm thuế 3 tháng. Thuế suất áp dụng là bao nhiêu và "
#             "mức phạt chậm nộp tính thế nào?"
#         ),
#         "ground_truth": (
#             "Doanh nghiệp có doanh thu dưới 20 tỷ thuộc diện doanh nghiệp nhỏ và vừa nhưng "
#             "nếu không thuộc lĩnh vực ưu đãi thì áp dụng thuế suất 20%. Tiền chậm nộp thuế "
#             "tính theo mức 0,03%/ngày trên số tiền thuế chậm nộp theo Luật Quản lý thuế."
#         ),
#     },
#     # Nhóm 3: Ngoài phạm vi
#     {
#         "group": "out_of_scope",
#         "question": (
#             "Quy định về thuế tối thiểu toàn cầu Pillar 2 áp dụng cho tập đoàn đa quốc gia "
#             "tại Việt Nam năm 2026 như thế nào?"
#         ),
#         "ground_truth": (
#             "Thuế tối thiểu toàn cầu Pillar 2 là nội dung mới, hệ thống cần thông báo "
#             "không đủ dữ liệu thay vì tự ý trả lời."
#         ),
#     },
#     {
#         "group": "out_of_scope",
#         "question": "Quy định thuế carbon tại Việt Nam hiện nay ra sao?",
#         "ground_truth": (
#             "Thuế carbon chưa được quy định rõ trong hệ thống thuế hiện hành của Việt Nam, "
#             "hệ thống nên thông báo không đủ dữ liệu."
#         ),
#     },
# ]

# # ─── Gọi backend (Không delay) ─────────────────────────────────────────────
# def call_backend(question: str) -> dict[str, Any]:
#     import requests
#     try:
#         resp = requests.post(
#             BACKEND_URL,
#             json={"question": question},
#             timeout=60,
#         )
#         if resp.status_code == 200:
#             return resp.json()
#         else:
#             print(f"      [WARNING] Backend trả mã lỗi: {resp.status_code}")
#             return {"answer": "", "sources": [], "meta": {}}
#     except Exception as exc:
#         print(f"      [WARNING] Lỗi kết nối backend: {exc}")
#         return {"answer": "", "sources": [], "meta": {}}


# def extract_contexts(sources: list[dict]) -> list[str]:
#     contexts = []
#     for src in sources:
#         excerpt = (src.get("excerpt") or "").strip()
#         law     = src.get("law_name") or ""
#         article = src.get("article") or ""
#         if excerpt:
#             contexts.append(f"{law} — {article}\n{excerpt}")
#     return contexts if contexts else ["Không có nguồn truy xuất."]


# # ─── Thu thập kết quả liên tục ────────────────────────────────────────────
# def collect_results() -> list[dict]:
#     print("\n=== Gọi backend thu thập dữ liệu ===")
#     results = []

#     for i, item in enumerate(TEST_QUESTIONS, 1):
#         q = item["question"]
#         print(f"   [{i}/{len(TEST_QUESTIONS)}] {q[:60]}...")

#         t0 = time.perf_counter()
#         raw = call_backend(q)
#         elapsed = round((time.perf_counter() - t0) * 1000, 0)

#         answer   = raw.get("answer", "")
#         sources  = raw.get("sources", [])
#         meta     = raw.get("meta", {})
#         contexts = extract_contexts(sources)
#         status   = "✓ OK" if answer else "✗ TRỐNG"

#         results.append({
#             "group":        item["group"],
#             "question":     q,
#             "ground_truth": item["ground_truth"],
#             "answer":       answer,
#             "contexts":     contexts,
#             "meta":         meta,
#             "elapsed_ms":   elapsed,
#         })
#         print(f"      → {status} | {len(contexts)} context(s) | {elapsed:.0f}ms")

#         # 🔥 THÊM DÒNG NÀY VÀO ĐỂ KHÔNG BỊ SẬP GEMINI
#         # Nghỉ 5 giây giữa các câu để Backend giãn cách thời gian gọi sang Gemini API
#         if i < len(TEST_QUESTIONS):
#             time.sleep(20) 

#     return results

# # ─── RAGAS Evaluation bằng Groq ───────────────────────────────────────────
# def run_ragas(results: list[dict]) -> dict | None:
#     try:
#         from datasets import Dataset as HFDataset
#         from ragas import evaluate
#         from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
#         from langchain_groq import ChatGroq
#     except ImportError as exc:
#         print(f"\n[RAGAS NOT INSTALLED] {exc}")
#         return None

#     if not GROQ_API_KEY or GROQ_API_KEY == "ĐIỀN_KEY_CỦA_BẠN_VÀO_ĐÂY":
#         print("\n[SKIP RAGAS] Chưa cấu hình GROQ_API_KEY.")
#         return None

#     valid = [r for r in results if r["answer"].strip()]
#     if not valid:
#         print("\n[ERROR] Không có câu trả lời nào hợp lệ để chấm điểm.")
#         return None

#     print(f"\n=== Khởi chạy RAGAS Judge (Groq: {GROQ_MODEL}) ===")

#     try:
#         evaluator_llm = ChatGroq(
#             api_key=GROQ_API_KEY,
#             model_name=GROQ_MODEL,
#             temperature=0,
#             max_retries=3
#         )
#     except Exception as exc:
#         print(f"[ERROR] Không tạo được client Groq: {exc}")
#         return None

#     dataset = HFDataset.from_list([
#         {
#             "user_input":         r["question"],
#             "retrieved_contexts": r["contexts"],
#             "response":           r["answer"],
#             "reference":          r["ground_truth"],
#         }
#         for r in valid
#     ])

#     metrics = [Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()]

#     try:
#         score = evaluate(dataset=dataset, metrics=metrics, llm=evaluator_llm)
#         return score
#     except Exception as exc:
#         print(f"[ERROR] RAGAS evaluate thất bại: {exc}")
#         return None


# # ─── In bảng thủ công ─────────────────────────────────────────────────────
# def print_manual_table(results: list[dict]) -> None:
#     print("\n=== Bảng kết quả tổng hợp từ Backend ===")
#     header = (f"{'#':<3} {'Nhóm':<12} {'Reasoning':<14} {'Intent':<8} "
#               f"{'is_rel':<7} {'is_sup':<7} {'is_use':<7} {'#src':<5} {'ms':<6} {'Answer?'}")
#     print(header)
#     print("-" * len(header))

#     for i, r in enumerate(results, 1):
#         meta    = r["meta"]
#         mode    = (meta.get("reasoning_mode") or "—")[:13]
#         intent  = ((meta.get("intent_router") or {}).get("label") or "—")[:7]
#         sr      = meta.get("self_reflection") or {}
#         is_rel  = "✓" if sr.get("is_relevant") else "✗"
#         is_sup  = "✓" if sr.get("is_supported") else "✗"
#         is_use  = "✓" if sr.get("is_useful") else "✗"
#         nsrc    = len(r["contexts"])
#         ms      = int(r["elapsed_ms"])
#         has_ans = "✓" if r["answer"] else "✗ TRỐNG"
#         print(f"{i:<3} {r['group']:<12} {mode:<14} {intent:<8} "
#               f"{is_rel:<7} {is_sup:<7} {is_use:<7} {nsrc:<5} {ms:<6} {has_ans}")


# # ─── Main ─────────────────────────────────────────────────────────────────
# def main() -> None:
#     results = collect_results()
    
#     # Lưu file raw JSON
#     Path("evaluation_results_raw.json").write_text(
#         json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
#     )

#     print_manual_table(results)
#     ragas_scores = run_ragas(results)

#     if ragas_scores is not None:
#         print("\n=== RAGAS Scores ===")
#         try:
#             score_dict = dict(ragas_scores)
#         except Exception:
#             score_dict = {}

#         for k, v in score_dict.items():
#             bar = "█" * int(float(v or 0) * 20)
#             print(f"  {k:<22}: {float(v or 0):.4f}  {bar}")

#         # Lưu JSON đầy đủ
#         output = {"ragas_scores": score_dict, "per_question": results}
#         Path("evaluation_results.json").write_text(
#             json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
#         )

#         # Xuất CSV chuẩn hóa tránh lệch dòng do câu trống
#         try:
#             import csv
#             csv_path = Path("evaluation_results.csv")
#             with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
#                 writer = csv.writer(f)
#                 writer.writerow([
#                     "STT", "Nhóm", "Câu hỏi", "Reasoning mode", "Intent",
#                     "is_relevant", "is_supported", "is_useful",
#                     "Số nguồn", "Thời gian (ms)",
#                     "faithfulness", "answer_relevancy", "context_precision", "context_recall"
#                 ])
#                 df = ragas_scores.to_pandas()
#                 valid_results = [r for r in results if r["answer"].strip()]
#                 for i, (r, row) in enumerate(zip(valid_results, df.itertuples()), 1):
#                     meta = r["meta"]
#                     sr   = meta.get("self_reflection") or {}
#                     writer.writerow([
#                         i, r["group"], r["question"][:80],
#                         meta.get("reasoning_mode", ""),
#                         (meta.get("intent_router") or {}).get("label", ""),
#                         sr.get("is_relevant", ""), sr.get("is_supported", ""), sr.get("is_useful", ""),
#                         len(r["contexts"]), int(r["elapsed_ms"]),
#                         getattr(row, "faithfulness", ""),
#                         getattr(row, "answer_relevancy", ""),
#                         getattr(row, "context_precision", ""),
#                         getattr(row, "context_recall", "")
#                     ])
#             print(f"\n[SUCCESS] Đã xuất báo cáo CSV → {csv_path}")
#         except Exception as exc:
#             print(f"[WARN] Lỗi ghi file CSV: {exc}")


# if __name__ == "__main__":
#     main()



"""
evaluate_ragas.py — Đánh giá từng câu một (Có Checkpoint lưu dữ liệu liên tục)
======================================================================
"""

import os
import json
import time
from pathlib import Path
from typing import Any

# ─── Cấu hình ──────────────────────────────────────────────────────────────
# GROQ_API_KEY = os.getenv("GROQ_API_KEY", "ĐIỀN_KEY_CỦA_BẠN_VÀO_ĐÂY")
# GROQ_MODEL   = os.getenv("GROQ_MODEL_NAME", "llama3-70b-8192")
# BACKEND_URL  = "http://127.0.0.1:8000/api/v1/chat/"

CHECKPOINT_PATH = Path("evaluation_checkpoint.json")

# Bộ câu hỏi thử nghiệm (Giữ nguyên 9 câu của bạn)
TEST_QUESTIONS = [
    {"group": "simple", "question": "Thuế thu nhập doanh nghiệp là gì?", "ground_truth": "Thuế thu nhập doanh nghiệp (TNDN) là loại thuế trực thu đánh vào phần thu nhập chịu thuế của doanh nghiệp sau khi trừ các chi phí hợp lý, hợp lệ."},
    {"group": "simple", "question": "Thuế suất thuế thu nhập doanh nghiệp phổ thông hiện hành là bao nhiêu phần trăm?", "ground_truth": "Thuế suất thuế TNDN phổ thông hiện hành là 20% áp dụng cho đa số doanh nghiệp."},
    {"group": "simple", "question": "Doanh nghiệp nhỏ và vừa có được ưu đãi thuế suất TNDN không?", "ground_truth": "Có. Doanh nghiệp nhỏ và vừa đáp ứng điều kiện theo quy định có thể được áp dụng thuế suất ưu đãi thấp hơn thuế suất phổ thông 20%."},
    {"group": "simple", "question": "Những khoản chi nào không được trừ khi tính thuế thu nhập doanh nghiệp?", "ground_truth": "Các khoản chi không được trừ gồm: chi không có hóa đơn chứng từ hợp lệ, chi phạt vi phạm hành chính, chi không liên quan đến hoạt động sản xuất kinh doanh."},
    {"group": "complex", "question": "Doanh nghiệp thành lập mới tại khu kinh tế nếu đồng thời có dự án đầu tư vào lĩnh vực ưu đãi thì được hưởng những ưu đãi thuế TNDN nào và trong bao lâu?", "ground_truth": "Doanh nghiệp mới thành lập tại khu kinh tế, đầu tư vào lĩnh vực ưu đãi có thể được miễn thuế TNDN trong thời gian nhất định, sau đó giảm thuế suất. Điều kiện, thời hạn và mức ưu đãi cụ thể phụ thuộc vào quy định của từng khu kinh tế và lĩnh vực đầu tư theo luật thuế TNDN và các nghị định hướng dẫn."},
    {"group": "complex", "question": "If doanh nghiệp vừa có thu nhập từ sản xuất trong nước, vừa có thu nhập từ chuyển nhượng bất động sản, thì cách tính thuế TNDN cho từng phần thu nhập như thế nào? Có được bù trừ lỗ giữa hai hoạt động không?", "ground_truth": "Thu nhập từ chuyển nhượng bất động sản phải hạch toán riêng, không được bù trừ lỗ với thu nhập từ hoạt động sản xuất kinh doanh thông thường. Mỗi phần thu nhập tính thuế theo quy định riêng."},
    {"group": "complex", "question": "Doanh nghiệp có doanh thu dưới 20 tỷ nhưng hoạt động trong lĩnh vực không được ưu đãi, đồng thời nộp chậm thuế 3 tháng. Thuế suất áp dụng là bao nhiêu và mức phạt chậm nộp tính thế nào?", "ground_truth": "Doanh nghiệp có doanh thu dưới 20 tỷ thuộc diện doanh nghiệp nhỏ và vừa nhưng nếu không thuộc lĩnh vực ưu đãi thì áp dụng thuế suất 20%. Tiền chậm nộp thuế tính theo mức 0,03%/ngày trên số tiền thuế chậm nộp theo Luật Quản lý thuế."},
    {"group": "out_of_scope", "question": "Quy định về thuế tối thiểu toàn cầu Pillar 2 áp dụng cho tập đoàn đa quốc gia tại Việt Nam năm 2026 như thế nào?", "ground_truth": "Thuế tối thiểu toàn cầu Pillar 2 là nội dung mới, hệ thống cần thông báo không đủ dữ liệu thay vì tự ý trả lời."},
    {"group": "out_of_scope", "question": "Quy định thuế carbon tại Việt Nam hiện nay ra sao?", "ground_truth": "Thuế carbon chưa được quy định rõ trong hệ thống thuế hiện hành của Việt Nam, hệ thống nên thông báo không đủ dữ liệu."},
]

# ─── Gọi backend ───────────────────────────────────────────────────────────
def call_backend(question: str) -> dict[str, Any]:
    import requests
    try:
        resp = requests.post(BACKEND_URL, json={"question": question}, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"      [WARNING] Backend lỗi HTTP {resp.status_code}")
            return {"answer": f"LỖI HTTP {resp.status_code}", "sources": [], "meta": {}}
    except Exception as exc:
        print(f"      [WARNING] Lỗi kết nối backend: {exc}")
        return {"answer": f"LỖI KẾT NỐI: {exc}", "sources": [], "meta": {}}

def extract_contexts(sources: list[dict]) -> list[str]:
    contexts = []
    for src in sources:
        excerpt = (src.get("excerpt") or "").strip()
        law = src.get("law_name") or ""
        article = src.get("article") or ""
        if excerpt:
            contexts.append(f"{law} — {article}\n{excerpt}")
    return contexts if contexts else ["Không có nguồn truy xuất."]

# ─── Tải và lưu Checkpoint (Chạy từng câu một) ─────────────────────────────
def load_checkpoint() -> list[dict]:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except:
            return []
    return []

def save_checkpoint(results: list[dict]):
    CHECKPOINT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

# ─── Thu thập dữ liệu từng câu một ─────────────────────────────────────────
def collect_results_one_by_one() -> list[dict]:
    print("\n=== Bắt đầu gọi Backend từng câu một ===")
    completed_results = load_checkpoint()
    
    # Xác định xem những câu nào đã chạy thành công trước đó rồi
    runned_questions = {r["question"] for r in completed_results if "LỖI" not in r["answer"]}

    for i, item in enumerate(TEST_QUESTIONS, 1):
        q = item["question"]
        
        if q in runned_questions:
            print(f"   [{i}/{len(TEST_QUESTIONS)}] Đã có dữ liệu checkpoint câu này. Bỏ qua.")
            continue

        print(f"   [{i}/{len(TEST_QUESTIONS)}] Đang test: {q[:50]}...")
        
        t0 = time.perf_counter()
        raw = call_backend(q)
        elapsed = round((time.perf_counter() - t0) * 1000, 0)

        answer   = raw.get("answer", "")
        sources  = raw.get("sources", [])
        meta     = raw.get("meta", {})
        contexts = extract_contexts(sources)
        status   = "✓ OK" if answer and "LỖI" not in answer else "✗ LỖI/TRỐNG"

        # Cập nhật hoặc thêm mới vào mảng kết quả
        res_entry = {
            "group":        item["group"],
            "question":     q,
            "ground_truth": item["ground_truth"],
            "answer":       answer,
            "contexts":     contexts,
            "meta":         meta,
            "elapsed_ms":   elapsed,
        }
        
        # Xóa bản ghi cũ lỗi nếu có, nạp bản ghi mới vào
        completed_results = [r for r in completed_results if r["question"] != q]
        completed_results.append(res_entry)
        
        # Lưu đè vào file ngay lập tức sau mỗi câu
        save_checkpoint(completed_results)
        print(f"      → {status} | Đã lưu checkpoint câu {i} | {elapsed:.0f}ms")

        # Giãn cách 3 giây để Gemini Free Tier không bị quá tải đột ngột
        if i < len(TEST_QUESTIONS):
            time.sleep(3)

    return completed_results

# ─── In bảng thủ công ─────────────────────────────────────────────────────
def print_manual_table(results: list[dict]) -> None:
    print("\n=== BẢNG THỐNG KÊ TỔNG HỢP (CUỐI CODE) ===")
    header = (f"{'STT':<4} {'Nhóm':<12} {'Reasoning':<14} {'Intent':<8} "
              f"{'is_rel':<7} {'is_sup':<7} {'is_use':<7} {'#src':<5} {'ms':<6} {'Kết quả'}")
    print(header)
    print("-" * len(header))

    for i, r in enumerate(results, 1):
        meta    = r.get("meta", {})
        mode    = (meta.get("reasoning_mode") or "—")[:13]
        intent  = ((meta.get("intent_router") or {}).get("label") or "—")[:7]
        sr      = meta.get("self_reflection") or {}
        is_rel  = "✓" if sr.get("is_relevant") else "✗"
        is_sup  = "✓" if sr.get("is_supported") else "✗"
        is_use  = "✓" if sr.get("is_useful") else "✗"
        nsrc    = len(r["contexts"])
        ms      = int(r["elapsed_ms"])
        
        has_ans = "✓ OK"
        if not r["answer"]: has_ans = "✗ TRỐNG"
        elif "LỖI" in r["answer"]: has_ans = "✗ LỖI API"

        print(f"{i:<4} {r['group']:<12} {mode:<14} {intent:<8} "
              f"{is_rel:<7} {is_sup:<7} {is_use:<7} {nsrc:<5} {ms:<6} {has_ans}")

# ─── RAGAS Evaluation bằng Groq ───────────────────────────────────────────
def run_ragas(results: list[dict]) -> dict | None:
    try:
        from datasets import Dataset as HFDataset
        from ragas import evaluate
        from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
        from langchain_groq import ChatGroq
    except ImportError:
        print("\n[RAGAS NOT INSTALLED] Thiếu thư viện chấm điểm.")
        return None

    if not GROQ_API_KEY or GROQ_API_KEY == "ĐIỀN_KEY_CỦA_BẠN_VÀO_ĐÂY":
        print("\n[SKIP RAGAS] Chưa cấu hình GROQ_API_KEY để chấm điểm.")
        return None

    valid = [r for r in results if r["answer"].strip() and "LỖI" not in r["answer"]]
    if not valid:
        print("\n[ERROR] Không có câu trả lời sạch nào để RAGAS chấm điểm.")
        return None

    print(f"\n=== Khởi chạy RAGAS Judge (Groq chấm điểm: {GROQ_MODEL}) ===")
    try:
        evaluator_llm = ChatGroq(api_key=GROQ_API_KEY, model_name=GROQ_MODEL, temperature=0, max_retries=3)
        dataset = HFDataset.from_list([
            {"user_input": r["question"], "retrieved_contexts": r["contexts"], "response": r["answer"], "reference": r["ground_truth"]}
            for r in valid
        ])
        metrics = [Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()]
        return evaluate(dataset=dataset, metrics=metrics, llm=evaluator_llm)
    except Exception as exc:
        print(f"[ERROR] RAGAS evaluate thất bại: {exc}")
        return None

# ─── Main ─────────────────────────────────────────────────────────────────
def main() -> None:
    # 1. Thu thập dữ liệu từng câu (An toàn + Checkpoint)
    results = collect_results_one_by_one()
    
    # 2. In bảng thống kê ra màn hình terminal cuối code
    print_manual_table(results)
    
    # 3. Tiến hành chấm điểm RAGAS tổng kết bằng Groq
    ragas_scores = run_ragas(results)

    if ragas_scores is not None:
        print("\n=== ĐIỂM SỐ RAGAS CUỐI CÙNG ===")
        try:
            score_dict = dict(ragas_scores)
        except:
            score_dict = {}

        for k, v in score_dict.items():
            bar = "█" * int(float(v or 0) * 20)
            print(f"  {k:<22}: {float(v or 0):.4f}  {bar}")
            
        # Xóa file checkpoint sau khi đã hoàn thành toàn bộ bài test sạch sẽ
        if CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()
        print("\n[HOÀN THÀNH] Quá trình test kết thúc thành công!")

if __name__ == "__main__":
    main()