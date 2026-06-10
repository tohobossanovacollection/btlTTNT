"""
evaluate_ragas.py - Danh gia he thong RAG TaxBot bang RAGAS
Luu checkpoint sau moi cau hoi va su dung Groq lam evaluator LLM.
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

# Bộ câu hỏi thử nghiệm để đánh giá pipeline RAG.
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

# Goi backend
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

# Tai va luu checkpoint
def load_checkpoint() -> list[dict]:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except:
            return []
    return []

def save_checkpoint(results: list[dict]):
    CHECKPOINT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

# Thu thap du lieu tung cau
def collect_results_one_by_one() -> list[dict]:
    print("\n=== Bắt đầu gọi Backend từng câu một ===")
    completed_results = load_checkpoint()
    
    # Xac dinh nhung cau da co checkpoint hop le
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

        # Cap nhat hoac them moi vao mang ket qua
        res_entry = {
            "group":        item["group"],
            "question":     q,
            "ground_truth": item["ground_truth"],
            "answer":       answer,
            "contexts":     contexts,
            "meta":         meta,
            "elapsed_ms":   elapsed,
        }
        
        # Xoa ban ghi cu neu co, sau do ghi de ket qua moi
        completed_results = [r for r in completed_results if r["question"] != q]
        completed_results.append(res_entry)
        
        # Luu ngay sau moi cau de co the resume
        save_checkpoint(completed_results)
        print(f"      → {status} | Đã lưu checkpoint câu {i} | {elapsed:.0f}ms")

        # Gian cach ngan giua cac cau de tranh don request len Groq
        if i < len(TEST_QUESTIONS):
            time.sleep(3)

    return completed_results

# In bang tong hop
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

# RAGAS evaluation bang Groq
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

# Main
def main() -> None:
    # 1. Thu thap du lieu tung cau va luu checkpoint
    results = collect_results_one_by_one()
    save_raw_results(results)
    
    # 2. In bang thong ke tong hop
    print_manual_table(results)
    
    # 3. Cham diem RAGAS bang Groq
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
