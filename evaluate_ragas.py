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
import hashlib
import math
import re
from pathlib import Path
from typing import Any


from dotenv import load_dotenv
try:
    from ragas.embeddings.base import BaseRagasEmbedding
except ImportError:
    BaseRagasEmbedding = object
load_dotenv("backend/.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("RAGAS_GROQ_MODEL_NAME") or os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
if not os.getenv("RAGAS_GROQ_MODEL_NAME") and GROQ_MODEL in {"groq/compound", "groq/compound-mini"}:
    GROQ_MODEL = "llama-3.3-70b-versatile"
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1/chat/")
# ─── Cấu hình ──────────────────────────────────────────────────────────────
# GROQ_API_KEY = os.getenv("GROQ_API_KEY", "ĐIỀN_KEY_CỦA_BẠN_VÀO_ĐÂY")
# GROQ_MODEL   = os.getenv("GROQ_MODEL_NAME", "llama3-70b-8192")
# BACKEND_URL  = "http://127.0.0.1:8000/api/v1/chat/"


class HashingRagasEmbedding(BaseRagasEmbedding):
    """Embedding local toi gian de RAGAS tinh answer_relevancy khong can API embedding."""

    def __init__(self, dim: int = 512):
        super().__init__()
        self.dim = dim

    def embed_text(self, text: str, **kwargs: Any) -> list[float]:
        vector = [0.0] * self.dim
        tokens = re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed_text(text, **kwargs)

    def embed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [self.embed_text(text, **kwargs) for text in texts]

    async def aembed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return self.embed_texts(texts, **kwargs)

    def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed_text(text, **kwargs)

    def embed_documents(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return self.embed_texts(texts, **kwargs)

    async def aembed_query(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed_text(text, **kwargs)

    async def aembed_documents(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return self.embed_texts(texts, **kwargs)


CHECKPOINT_PATH = Path("evaluation_checkpoint.json")
RAW_RESULTS_PATH = Path("evaluation_results_raw.json")
RAGAS_RESULTS_CSV_PATH = Path("evaluation_results.csv")
RAGAS_RESULTS_JSON_PATH = Path("evaluation_results.json")
RAGAS_SUMMARY_PATH = Path("evaluation_summary.json")
METRIC_COLUMNS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

# Bộ câu hỏi thử nghiệm 30 câu, chia đa dạng nhóm để đánh giá RAG.
TEST_QUESTIONS = [
    {"group": "simple", "question": "Thuế thu nhập doanh nghiệp là gì?", "ground_truth": "Thuế thu nhập doanh nghiệp là loại thuế trực thu tính trên phần thu nhập chịu thuế của doanh nghiệp sau khi trừ các khoản chi phí được trừ và các khoản miễn giảm theo quy định."},
    {"group": "simple", "question": "Thuế suất thuế thu nhập doanh nghiệp phổ thông hiện hành là bao nhiêu?", "ground_truth": "Thuế suất thuế thu nhập doanh nghiệp phổ thông hiện hành thường là 20%, trừ trường hợp được áp dụng thuế suất ưu đãi hoặc mức thuế suất riêng theo quy định."},
    {"group": "simple", "question": "Căn cứ tính thuế thu nhập doanh nghiệp gồm những yếu tố nào?", "ground_truth": "Căn cứ tính thuế thu nhập doanh nghiệp gồm thu nhập tính thuế và thuế suất thuế thu nhập doanh nghiệp áp dụng cho kỳ tính thuế."},
    {"group": "simple", "question": "Kỳ tính thuế thu nhập doanh nghiệp thông thường là gì?", "ground_truth": "Kỳ tính thuế thu nhập doanh nghiệp thông thường được xác định theo năm dương lịch hoặc năm tài chính của doanh nghiệp."},
    {"group": "simple", "question": "Khoản chi được trừ khi tính thuế TNDN cần đáp ứng điều kiện gì?", "ground_truth": "Khoản chi được trừ khi tính thuế TNDN cần liên quan đến hoạt động sản xuất kinh doanh, có hóa đơn chứng từ hợp pháp và đáp ứng điều kiện thanh toán theo quy định."},
    {"group": "simple", "question": "Khoản chi không có hóa đơn chứng từ hợp lệ có được trừ khi tính thuế TNDN không?", "ground_truth": "Khoản chi không có hóa đơn chứng từ hợp lệ thường không được tính vào chi phí được trừ khi xác định thu nhập chịu thuế TNDN."},
    {"group": "simple", "question": "Thuế giá trị gia tăng là gì?", "ground_truth": "Thuế giá trị gia tăng là thuế tính trên phần giá trị tăng thêm của hàng hóa, dịch vụ phát sinh trong quá trình sản xuất, lưu thông và tiêu dùng."},
    {"group": "simple", "question": "Đối tượng chịu thuế giá trị gia tăng là gì?", "ground_truth": "Đối tượng chịu thuế giá trị gia tăng là hàng hóa, dịch vụ dùng cho sản xuất, kinh doanh và tiêu dùng tại Việt Nam, trừ các trường hợp không chịu thuế theo quy định."},
    {"group": "simple", "question": "Thuế suất GTGT phổ thông hiện nay là bao nhiêu?", "ground_truth": "Thuế suất GTGT phổ thông thường là 10%, trừ các trường hợp áp dụng thuế suất 0%, 5% hoặc chính sách giảm thuế theo từng thời kỳ."},
    {"group": "simple", "question": "Hàng hóa, dịch vụ xuất khẩu thường áp dụng thuế suất GTGT nào?", "ground_truth": "Hàng hóa, dịch vụ xuất khẩu thường áp dụng thuế suất GTGT 0% nếu đáp ứng đầy đủ điều kiện về hợp đồng, thanh toán và hồ sơ theo quy định."},
    {"group": "simple", "question": "Phương pháp khấu trừ thuế GTGT là gì?", "ground_truth": "Phương pháp khấu trừ thuế GTGT là phương pháp xác định số thuế phải nộp bằng thuế GTGT đầu ra trừ thuế GTGT đầu vào được khấu trừ."},
    {"group": "simple", "question": "Hóa đơn điện tử là gì?", "ground_truth": "Hóa đơn điện tử là hóa đơn được lập, gửi, nhận, lưu trữ và quản lý bằng phương tiện điện tử theo quy định về hóa đơn, chứng từ."},
    {"group": "simple", "question": "Hóa đơn GTGT dùng để làm gì?", "ground_truth": "Hóa đơn GTGT dùng để ghi nhận việc bán hàng hóa, cung cấp dịch vụ và là căn cứ kê khai thuế, hạch toán doanh thu, chi phí và khấu trừ thuế nếu đủ điều kiện."},
    {"group": "simple", "question": "Thuế thu nhập cá nhân là gì?", "ground_truth": "Thuế thu nhập cá nhân là thuế trực thu đánh vào thu nhập chịu thuế của cá nhân theo quy định của pháp luật thuế thu nhập cá nhân."},
    {"group": "simple", "question": "Ai là người nộp thuế thu nhập cá nhân?", "ground_truth": "Người nộp thuế thu nhập cá nhân gồm cá nhân cư trú có thu nhập chịu thuế phát sinh trong và ngoài Việt Nam và cá nhân không cư trú có thu nhập chịu thuế phát sinh tại Việt Nam."},
    {"group": "simple", "question": "Thu nhập từ tiền lương, tiền công có chịu thuế TNCN không?", "ground_truth": "Thu nhập từ tiền lương, tiền công là một loại thu nhập chịu thuế TNCN, sau khi trừ các khoản miễn thuế và giảm trừ theo quy định."},
    {"group": "simple", "question": "Giảm trừ gia cảnh dùng để làm gì khi tính thuế TNCN?", "ground_truth": "Giảm trừ gia cảnh dùng để trừ khỏi thu nhập chịu thuế trước khi tính thuế TNCN đối với cá nhân cư trú có thu nhập từ tiền lương, tiền công hoặc kinh doanh."},
    {"group": "simple", "question": "Đăng ký thuế là gì?", "ground_truth": "Đăng ký thuế là việc người nộp thuế kê khai thông tin với cơ quan thuế để được cấp mã số thuế và quản lý nghĩa vụ thuế theo quy định."},
    {"group": "complex", "question": "Doanh nghiệp có hóa đơn hợp lệ nhưng khoản chi không phục vụ hoạt động kinh doanh thì có được trừ khi tính thuế TNDN không?", "ground_truth": "Không. Khoản chi dù có hóa đơn hợp lệ nhưng không liên quan đến hoạt động sản xuất kinh doanh thì thường không được tính vào chi phí được trừ khi xác định thu nhập chịu thuế TNDN."},
    {"group": "complex", "question": "Doanh nghiệp vừa có thu nhập từ kinh doanh thông thường vừa có thu nhập chuyển nhượng bất động sản thì có cần hạch toán riêng không?", "ground_truth": "Có. Thu nhập từ chuyển nhượng bất động sản cần được hạch toán riêng và xác định nghĩa vụ thuế theo quy định riêng, không gộp tùy tiện với thu nhập kinh doanh thông thường."},
    {"group": "complex", "question": "Hàng hóa xuất khẩu có hợp đồng, chứng từ thanh toán qua ngân hàng và hồ sơ hải quan đầy đủ thì thường áp dụng thuế suất GTGT nào?", "ground_truth": "Hàng hóa xuất khẩu có đủ hợp đồng, chứng từ thanh toán qua ngân hàng và hồ sơ hải quan theo quy định thường được áp dụng thuế suất GTGT 0%."},
    {"group": "complex", "question": "Cá nhân vừa có tiền lương vừa có thu nhập kinh doanh thì khi quyết toán thuế TNCN cần lưu ý gì?", "ground_truth": "Cá nhân cần xác định từng loại thu nhập chịu thuế, các khoản giảm trừ, số thuế đã khấu trừ hoặc tạm nộp để kê khai, quyết toán theo quy định nếu thuộc diện phải quyết toán."},
    {"group": "complex", "question": "Doanh nghiệp lập hóa đơn điện tử sai mã số thuế của người mua nhưng đã gửi cho người mua thì cần xử lý như thế nào?", "ground_truth": "Doanh nghiệp cần xử lý hóa đơn sai sót theo quy định về hóa đơn điện tử, thường là lập thông báo, điều chỉnh hoặc thay thế hóa đơn tùy trường hợp sai sót."},
    {"group": "complex", "question": "Người nộp thuế nộp hồ sơ khai thuế đúng hạn nhưng nộp tiền thuế chậm thì có phát sinh tiền chậm nộp không?", "ground_truth": "Có. Việc nộp hồ sơ đúng hạn không loại trừ nghĩa vụ nộp tiền thuế đúng hạn; nếu nộp tiền thuế chậm thì có thể phát sinh tiền chậm nộp theo quy định."},
    {"group": "complex", "question": "Tài sản cố định dùng cho hoạt động kinh doanh và có đủ hồ sơ quản lý thì chi phí khấu hao có được tính vào chi phí được trừ không?", "ground_truth": "Chi phí khấu hao tài sản cố định dùng cho hoạt động sản xuất kinh doanh, có đủ hồ sơ và trích khấu hao đúng quy định thường được tính vào chi phí được trừ."},
    {"group": "complex", "question": "Hàng nhập khẩu vừa chịu thuế nhập khẩu vừa chịu thuế GTGT thì doanh nghiệp cần kê khai những loại thuế nào?", "ground_truth": "Doanh nghiệp cần thực hiện nghĩa vụ thuế nhập khẩu và kê khai, nộp thuế GTGT khâu nhập khẩu theo quy định đối với hàng hóa nhập khẩu chịu thuế."},
    {"group": "out_of_scope", "question": "Thuế carbon tại Việt Nam hiện nay được tính như thế nào?", "ground_truth": "Dữ liệu hiện tại chưa đủ căn cứ để xác định cách tính thuế carbon tại Việt Nam; hệ thống nên thông báo không đủ dữ liệu thay vì tự suy diễn."},
    {"group": "out_of_scope", "question": "Quy định thuế tối thiểu toàn cầu Pillar 2 áp dụng cho từng doanh nghiệp nhỏ tại Việt Nam ra sao?", "ground_truth": "Dữ liệu hiện tại chưa đủ thông tin để trả lời chi tiết về Pillar 2 cho từng doanh nghiệp nhỏ; hệ thống nên thông báo không đủ dữ liệu."},
    {"group": "out_of_scope", "question": "Thuế tài sản đối với nhà ở cá nhân tại Việt Nam hiện được tính theo biểu nào?", "ground_truth": "Dữ liệu hiện tại chưa có đủ căn cứ về biểu thuế tài sản đối với nhà ở cá nhân; hệ thống nên thông báo không đủ dữ liệu."},
    {"group": "out_of_scope", "question": "Chính sách thuế với giao dịch tiền mã hóa tại Việt Nam được áp dụng cụ thể thế nào?", "ground_truth": "Dữ liệu hiện tại chưa đủ thông tin về chính sách thuế cụ thể đối với giao dịch tiền mã hóa; hệ thống nên thông báo không đủ dữ liệu."},
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


def save_raw_results(results: list[dict]) -> None:
    RAW_RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n[SAVED] Raw backend results -> {RAW_RESULTS_PATH}")


def save_ragas_outputs(ragas_scores: Any, results: list[dict], score_dict: dict[str, float]) -> bool:
    df = ragas_scores.to_pandas()

    df.to_csv(RAGAS_RESULTS_CSV_PATH, index=False, encoding="utf-8-sig")
    df.to_json(RAGAS_RESULTS_JSON_PATH, orient="records", force_ascii=False, indent=2)

    missing_scores = False
    for column in METRIC_COLUMNS:
        if column not in df.columns or df[column].dropna().empty or df[column].isna().any():
            missing_scores = True

    report = {
        "summary": score_dict,
        "ragas_model": GROQ_MODEL,
        "backend_url": BACKEND_URL,
        "has_missing_ragas_scores": missing_scores,
        "ragas_rows": json.loads(df.to_json(orient="records", force_ascii=False)),
        "backend_results": results,
    }
    RAGAS_SUMMARY_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"[SAVED] RAGAS table CSV   -> {RAGAS_RESULTS_CSV_PATH}")
    print(f"[SAVED] RAGAS table JSON  -> {RAGAS_RESULTS_JSON_PATH}")
    print(f"[SAVED] Summary report    -> {RAGAS_SUMMARY_PATH}")
    return missing_scores

# ─── RAGAS Evaluation bằng Groq ───────────────────────────────────────────
def run_ragas(results: list[dict]) -> dict | None:
    try:
        from datasets import Dataset as HFDataset
        from ragas import evaluate
        from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
        import instructor
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
    except ImportError as exc:
        print(f"\n[RAGAS NOT INSTALLED] Thiếu thư viện chấm điểm: {exc}")
        return None

    if not GROQ_API_KEY:
        print("\n[SKIP RAGAS] Chưa cấu hình GROQ_API_KEY để chấm điểm.")
        return None

    valid = [r for r in results if r["answer"].strip() and "LỖI" not in r["answer"]]
    if not valid:
        print("\n[ERROR] Không có câu trả lời sạch nào để RAGAS chấm điểm.")
        return None

    print(f"\n=== Khởi chạy RAGAS Judge (Groq chấm điểm: {GROQ_MODEL}) ===")
    try:
        groq_client = instructor.from_openai(
            AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1"),
            mode=instructor.Mode.JSON,
        )
        evaluator_llm = llm_factory(
            GROQ_MODEL,
            provider="groq",
            client=groq_client,
            adapter="litellm",
            temperature=0,
        )
        evaluator_embeddings = HashingRagasEmbedding()
        dataset = HFDataset.from_list([
            {"user_input": r["question"], "retrieved_contexts": r["contexts"], "response": r["answer"], "reference": r["ground_truth"]}
            for r in valid
        ])
        metrics = [
            Faithfulness(llm=evaluator_llm),
            AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings, strictness=1),
            ContextPrecision(llm=evaluator_llm),
            ContextRecall(llm=evaluator_llm),
        ]
        return evaluate(
            dataset=dataset,
            metrics=metrics,
            batch_size=1,
            raise_exceptions=False,
        )
    except Exception as exc:
        print(f"[ERROR] RAGAS evaluate thất bại: {exc}")
        return None

# ─── Main ─────────────────────────────────────────────────────────────────
def main() -> None:
    # 1. Thu thập dữ liệu từng câu (An toàn + Checkpoint)
    results = collect_results_one_by_one()
    save_raw_results(results)
    
    # 2. In bảng thống kê ra màn hình terminal cuối code
    print_manual_table(results)
    
    # 3. Tiến hành chấm điểm RAGAS tổng kết bằng Groq
    ragas_scores = run_ragas(results)

    if ragas_scores is not None:
        print("\n=== ĐIỂM SỐ RAGAS CUỐI CÙNG ===")
        try:
            df = ragas_scores.to_pandas()
            score_dict = {
                column: float(df[column].dropna().mean())
                for column in METRIC_COLUMNS
                if column in df.columns and not df[column].dropna().empty
            }
        except Exception:
            score_dict = {}

        for k, v in score_dict.items():
            bar = "█" * int(float(v or 0) * 20)
            print(f"  {k:<22}: {float(v or 0):.4f}  {bar}")

        missing_scores = save_ragas_outputs(ragas_scores, results, score_dict)

        if missing_scores:
            print(
                "\n[WARN] Một số điểm RAGAS bị thiếu/NaN. "
                "Thường là do Groq rate limit hoặc quota. Checkpoint được giữ lại để chạy tiếp sau."
            )
        elif CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()
            print("\n[HOÀN THÀNH] Quá trình test kết thúc thành công!")
        else:
            print("\n[HOÀN THÀNH] Quá trình test kết thúc thành công!")

if __name__ == "__main__":
    main()
