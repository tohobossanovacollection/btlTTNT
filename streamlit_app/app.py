from __future__ import annotations

import html
import sys
import uuid
import random
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

import chat_store


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app.services.chat_orchestrator import handle_chat  # noqa: E402
from app.config import settings  # noqa: E402


SUGGESTED_QUESTIONS = [
    "Lương 10 triệu một tháng có phải nộp thuế TNCN không?",
    "Hộ kinh doanh có bắt buộc xuất hóa đơn không?",
    "Chậm nộp thuế 20 ngày bị tính tiền chậm nộp thế nào?",
    "Điều kiện khấu trừ thuế GTGT đầu vào là gì?",
    "Khi nào doanh nghiệp được tính chi phí hợp lệ khi tính thuế TNDN?",
    "Cá nhân có nhiều nguồn thu nhập thì quyết toán thuế TNCN ra sao?",
    "Không xuất hóa đơn khi bán hàng bị xử phạt như thế nào?",
    "Đăng ký thuế lần đầu cần lưu ý những gì?",
    "Thuế GTGT đầu ra và đầu vào khác nhau thế nào?",
    "Hàng hóa xuất nhập khẩu áp dụng thuế theo văn bản nào?",
]

TOPIC_QUESTIONS = {
    "Tất cả": SUGGESTED_QUESTIONS,
    "TNCN": [
        "Lương 10 triệu một tháng có phải nộp thuế TNCN không?",
        "Cá nhân có nhiều nguồn thu nhập thì quyết toán thuế TNCN ra sao?",
        "Người phụ thuộc ảnh hưởng thế nào đến thuế TNCN?",
        "Thu nhập vãng lai có phải khấu trừ thuế TNCN không?",
    ],
    "GTGT": [
        "Điều kiện khấu trừ thuế GTGT đầu vào là gì?",
        "Thuế GTGT đầu ra và đầu vào khác nhau thế nào?",
        "Khi nào áp dụng thuế suất GTGT 0%?",
        "Hóa đơn đầu vào sai thông tin thì xử lý thế nào?",
    ],
    "Hóa đơn": [
        "Hộ kinh doanh có bắt buộc xuất hóa đơn không?",
        "Không xuất hóa đơn khi bán hàng bị xử phạt như thế nào?",
        "Hóa đơn điện tử sai ngày lập có xử lý được không?",
        "Bán hàng dưới 200 nghìn có cần xuất hóa đơn không?",
    ],
    "TNDN": [
        "Khi nào doanh nghiệp được tính chi phí hợp lệ khi tính thuế TNDN?",
        "Điều kiện hưởng ưu đãi thuế TNDN là gì?",
        "Chi phí không có hóa đơn có được tính vào chi phí hợp lệ không?",
        "Lỗ năm trước được chuyển khi tính thuế TNDN thế nào?",
    ],
    "Xử phạt": [
        "Chậm nộp thuế 20 ngày bị tính tiền chậm nộp thế nào?",
        "Nộp tờ khai thuế trễ hạn bị phạt ra sao?",
        "Không xuất hóa đơn khi bán hàng bị xử phạt như thế nào?",
        "Khai sai làm thiếu tiền thuế bị xử lý thế nào?",
    ],
}


def default_messages() -> list[dict[str, Any]]:
    return [
        {
            "role": "assistant",
            "content": "Xin chào, tôi là RAG TaxBot. Hãy nhập câu hỏi về thuế.",
            "sources": [],
            "meta": {},
            "error": None,
        }
    ]


def init_state() -> None:
    chat_store.init_db()
    conversations = chat_store.list_conversations()
    conversation_ids = {conversation["id"] for conversation in conversations}

    if not conversations:
        st.session_state.conversation_id = chat_store.create_conversation()
    elif "conversation_id" not in st.session_state:
        if conversations:
            st.session_state.conversation_id = conversations[0]["id"]

    if st.session_state.conversation_id not in conversation_ids and conversations:
        st.session_state.conversation_id = conversations[0]["id"]

    if "messages" not in st.session_state or st.session_state.get(
        "loaded_conversation_id"
    ) != st.session_state.conversation_id:
        stored_messages = chat_store.get_messages(st.session_state.conversation_id)
        st.session_state.messages = stored_messages or default_messages()
        st.session_state.loaded_conversation_id = st.session_state.conversation_id


def open_conversation(conversation_id: str) -> None:
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = chat_store.get_messages(conversation_id) or default_messages()
    st.session_state.loaded_conversation_id = conversation_id


def start_new_conversation() -> None:
    conversation_id = chat_store.create_conversation()
    open_conversation(conversation_id)


def run_chat(question: str) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    return handle_chat(question, request_id=request_id)


def clamp_percent(value: Any, default: float = 0.0) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if number <= 1.0:
        number *= 100.0
    return int(round(max(0.0, min(100.0, number))))


def format_seconds(milliseconds: Any) -> str:
    try:
        return f"{float(milliseconds) / 1000.0:.1f}s"
    except (TypeError, ValueError):
        return "-"


def score_percent(source: dict[str, Any]) -> int:
    score = source.get("score") or {}
    return clamp_percent(score.get("final_score"))


def source_label(source: dict[str, Any], index: int) -> str:
    law_name = source.get("law_name") or source.get("source") or "Nguồn pháp lý"
    article = source.get("article") or ""
    title = source.get("title") or ""
    compact_title = title[:80].rstrip() + "..." if len(title) > 80 else title
    pieces = [law_name, article, compact_title]
    label = " - ".join(piece for piece in pieces if piece)
    score = score_percent(source)
    return f"{index}. {label} ({score}%)"


def calculate_trust(meta: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    reflection = meta.get("self_reflection") or {}
    timings = meta.get("timings_ms") or {}
    relevance = clamp_percent(reflection.get("relevance_score"))

    if not relevance and sources:
        relevance = max(score_percent(source) for source in sources)

    has_sources = bool(sources)
    supported = reflection.get("is_supported")
    useful = reflection.get("is_useful")
    citation_valid = 100 if has_sources and supported is not False else 0

    confidence = round((relevance * 0.75) + (citation_valid * 0.25))
    if supported is False:
        confidence = min(confidence, 60)
    if useful is False:
        confidence = min(confidence, 70)

    if confidence >= 85:
        label = "CAO"
    elif confidence >= 60:
        label = "TRUNG BÌNH"
    else:
        label = "THẤP"

    return {
        "confidence": int(confidence),
        "label": label,
        "relevance": relevance,
        "response_time": format_seconds(timings.get("total")),
        "citation_valid": citation_valid,
    }


def refresh_suggestions() -> None:
    topic = st.session_state.get("suggestion_topic", "Tất cả")
    pool = TOPIC_QUESTIONS.get(topic, SUGGESTED_QUESTIONS)
    st.session_state.suggestions = random.sample(pool, k=min(4, len(pool)))


def current_suggestions() -> list[str]:
    if "suggestions" not in st.session_state:
        refresh_suggestions()
    return st.session_state.get("suggestions", [])


def processed_document_count() -> int:
    return len(list((PROJECT_ROOT / "data" / "processed").glob("*.md")))


def truncate_label(value: str, max_length: int = 38) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def normalize_conversation_title(title: str | None) -> str:
    normalizer = getattr(chat_store, "normalize_title", None)
    if callable(normalizer):
        return normalizer(title)

    text = " ".join(str(title or "").split())
    if not text or text.lower() in {"cuoc tro chuyen moi", "cuộc trò chuyện mới"}:
        return "Cuộc trò chuyện mới"
    return text


def compact_text(value: Any, max_length: int = 96) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def infer_tax_topic(sources: list[dict[str, Any]]) -> str:
    text = " ".join(
        str(source.get(key) or "")
        for source in sources
        for key in ["law_name", "title", "source", "excerpt"]
    ).lower()
    topics = [
        ("GTGT", ["gtgt", "giá trị gia tăng", "gia tri gia tang"]),
        ("TNCN", ["tncn", "thu nhập cá nhân", "thu nhap ca nhan"]),
        ("TNDN", ["tndn", "thu nhập doanh nghiệp", "thu nhap doanh nghiep"]),
        ("Hóa đơn", ["hóa đơn", "hoa don", "chứng từ", "chung tu"]),
        ("Xử phạt", ["xử phạt", "xu phat", "chậm nộp", "cham nop"]),
        ("Xuất nhập khẩu", ["xuất khẩu", "nhập khẩu", "xuat khau", "nhap khau"]),
    ]
    for topic, keywords in topics:
        if any(keyword in text for keyword in keywords):
            return topic
    return "Thuế doanh nghiệp"


def primary_document_name(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "Kho văn bản thuế nội bộ"
    first = sources[0]
    return compact_text(
        first.get("law_name") or first.get("source") or first.get("title") or "Nguồn pháp lý",
        72,
    )


def source_title(source: dict[str, Any], index: int) -> str:
    law_name = source.get("law_name") or "Nguon luat"
    article = source.get("article") or ""
    title = source.get("title") or ""
    pieces = [piece for piece in [law_name, article, title] if piece]
    return f"{index}. " + " - ".join(pieces)


def render_source(source: dict[str, Any], index: int) -> None:
    with st.expander(source_title(source, index), expanded=index == 1):
        score = source.get("score") or {}
        cols = st.columns(3)
        cols[0].metric("Semantic", score.get("semantic_score") if score else "-")
        cols[1].metric("Keyword", score.get("keyword_score") if score else "-")
        cols[2].metric("Final", score.get("final_score") if score else "-")

        matched_steps = source.get("matched_steps") or []
        if matched_steps:
            st.caption(" | ".join(matched_steps))

        excerpt = source.get("excerpt") or ""
        if excerpt:
            st.write(excerpt)


def render_evidence_summary(meta: dict[str, Any], sources: list[dict[str, Any]]) -> None:
    trust = calculate_trust(meta, sources)
    topic = infer_tax_topic(sources)
    document = primary_document_name(sources)
    st.markdown(
        f"""
        <div class="evidence-card">
          <div class="evidence-metrics">
            <span>Độ tin cậy: <strong class="metric-pill">{trust["confidence"]}% ({trust["label"]})</strong></span>
            <span>Độ liên quan nguồn: <strong>{trust["relevance"]}%</strong></span>
            <span>Thời gian phản hồi: <strong>{trust["response_time"]}</strong></span>
            <span>Trích dẫn hợp lệ: <strong>{trust["citation_valid"]}%</strong></span>
          </div>
          <div class="evidence-chips">
            <span class="evidence-chip chip-blue">Chủ đề: {html.escape(topic)}</span>
            <span class="evidence-chip chip-orange">Văn bản chính: {html.escape(document)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_source_table(sources: list[dict[str, Any]]) -> None:
    max_sources = int(st.session_state.get("max_sources", 4))
    rows: list[str] = []
    for index, source in enumerate(sources[:max_sources], start=1):
        law_name = compact_text(
            source.get("law_name") or source.get("source") or "Nguồn pháp lý",
            76,
        )
        article = compact_text(source.get("article") or source.get("title") or "-", 58)
        rows.append(
            "<tr>"
            f"<td>S{index}</td>"
            f"<td>{html.escape(law_name)}</td>"
            f"<td>{html.escape(article)}</td>"
            f"<td><strong>{score_percent(source)}%</strong></td>"
            "</tr>"
        )

    st.markdown(
        """
        <table class="source-table">
          <thead>
            <tr>
              <th>Mã</th>
              <th>Văn bản</th>
              <th>Điều / mục</th>
              <th>Khớp</th>
            </tr>
          </thead>
          <tbody>
        """
        + "".join(rows)
        + """
          </tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def render_source_excerpts(sources: list[dict[str, Any]]) -> None:
    max_sources = int(st.session_state.get("max_sources", 4))
    blocks: list[str] = []
    for index, source in enumerate(sources[:max_sources], start=1):
        title = compact_text(
            source.get("law_name") or source.get("source") or "Nguồn pháp lý",
            72,
        )
        excerpt = compact_text(source.get("excerpt") or "Không có đoạn trích ngắn.", 420)
        blocks.append(
            f"""
            <div class="excerpt-card">
              <strong>S{index}. {html.escape(title)}</strong>
              <p>{html.escape(excerpt)}</p>
            </div>
            """
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)


def render_citation_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        return

    with st.expander("🔎 Xem nguồn trích dẫn pháp lý (rất ngắn gọn)", expanded=False):
        tab_list, tab_excerpt = st.tabs(["Danh sách văn bản", "Đoạn trích tiêu biểu"])
        with tab_list:
            render_source_table(sources)
        with tab_excerpt:
            render_source_excerpts(sources)


def render_debug_meta(meta: dict[str, Any]) -> None:
    if not meta or not st.session_state.get("show_runtime", True):
        return

    timings = meta.get("timings_ms") or {}
    rag = meta.get("rag") or {}
    router = meta.get("intent_router") or {}
    reasoning = meta.get("reasoning") or {}
    reflection = meta.get("self_reflection") or {}

    with st.expander("Chi tiết xử lý", expanded=False):
        cols = st.columns(4)
        cols[0].metric("Mode", meta.get("reasoning_mode") or "-")
        cols[1].metric("Nguồn", f"{rag.get('retrieved_count', '-')}/{rag.get('top_k', '-')}")
        cols[2].metric("Retrieval", format_seconds(timings.get("retrieval")))
        cols[3].metric("LLM", format_seconds(timings.get("llm")))

        if router:
            st.caption(
                f"Router: {router.get('label', '-')} / {router.get('provider', '-')}"
            )
        if reasoning.get("steps"):
            st.caption("Bước suy luận: " + " | ".join(str(step) for step in reasoning["steps"][:4]))
        if reflection:
            st.caption(
                "Self-check: "
                f"relevant={reflection.get('is_relevant', '-')}, "
                f"supported={reflection.get('is_supported', '-')}, "
                f"useful={reflection.get('is_useful', '-')}"
            )


def render_message_body(message: dict[str, Any]) -> None:
    if message.get("error"):
        st.warning(message["error"])
    else:
        st.markdown('<div class="answer-panel">', unsafe_allow_html=True)
        st.markdown(message.get("content") or "")
        st.markdown("</div>", unsafe_allow_html=True)

    sources = message.get("sources") or []
    if message.get("role") == "assistant" and (sources or message.get("meta")):
        render_evidence_summary(message.get("meta") or {}, sources)
        render_citation_sources(sources)
        render_debug_meta(message.get("meta") or {})


def submit_prompt(prompt: str) -> None:
    conversation_id = st.session_state.conversation_id
    is_first_saved_message = chat_store.message_count(conversation_id) == 0
    user_message = {
        "role": "user",
        "content": prompt,
        "sources": [],
        "meta": {},
        "error": None,
    }
    st.session_state.messages.append(user_message)
    chat_store.add_message(conversation_id, user_message)
    if is_first_saved_message:
        chat_store.rename_conversation(conversation_id, prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang xử lý RAG local..."):
            try:
                data = run_chat(prompt)
                assistant_message = {
                    "role": "assistant",
                    "content": data.get("answer") or "Pipeline không trả về câu trả lời.",
                    "sources": data.get("sources") or [],
                    "meta": data.get("meta") or {},
                    "error": None,
                }
            except Exception as exc:
                assistant_message = {
                    "role": "assistant",
                    "content": "",
                    "sources": [],
                    "meta": {},
                    "error": f"Pipeline gặp lỗi: {exc}",
                }

        render_message_body(assistant_message)

    st.session_state.messages.append(assistant_message)
    chat_store.add_message(conversation_id, assistant_message)


def render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message["role"]):
        render_message_body(message)


def render_hero() -> None:
    doc_count = processed_document_count()
    conversation_count = len(chat_store.list_conversations())
    max_sources = st.session_state.get("max_sources", 4)
    st.markdown(
        f"""
        <section class="hero-panel">
          <div class="hero-strip"></div>
          <div class="hero-kicker">Streamlit RAG TaxBot</div>
          <h1>Trợ lý pháp lý thuế doanh nghiệp.</h1>
          <p>Hỏi tình huống thuế, nhận câu trả lời ngắn gọn kèm căn cứ pháp lý, độ tin cậy và runtime để demo pipeline AI rõ ràng.</p>
          <div class="hero-stats">
            <span><strong>{doc_count}</strong> văn bản</span>
            <span><strong>{conversation_count}</strong> cuộc trò chuyện</span>
            <span><strong>{settings.MODEL_NAME}</strong> model</span>
            <span><strong>{max_sources}</strong> nguồn hiển thị</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="RAG TaxBot", layout="wide")
init_state()
st.session_state.setdefault("suggestion_topic", "Tất cả")
st.session_state.setdefault("max_sources", 4)
st.session_state.setdefault("show_runtime", True)

st.markdown(
    """
    <style>
      :root {
        --taxbot-sidebar-width: 336px;
        --taxbot-primary: #0b63ce;
        --taxbot-primary-strong: #084b9c;
        --taxbot-orange: #f97316;
        --taxbot-orange-strong: #c2410c;
        --taxbot-bg-start: #f7fbff;
        --taxbot-bg-mid: #eef7ff;
        --taxbot-bg-end: #fff7ed;
        --taxbot-surface: rgba(255, 255, 255, 0.92);
        --taxbot-surface-strong: #ffffff;
        --taxbot-primary-soft: #eaf3ff;
        --taxbot-orange-soft: #fff7ed;
        --taxbot-line: #d6e3f3;
        --taxbot-text: #10233f;
        --taxbot-muted: #667892;
        --taxbot-border: rgba(11, 99, 206, 0.18);
        --primary-color: #0b63ce;
        --primary-color-dark: #084b9c;
        --primary-color-light: #eaf3ff;
      }
      * {
        accent-color: var(--taxbot-primary);
      }
      .stApp {
        background:
          linear-gradient(135deg, var(--taxbot-bg-start) 0%, var(--taxbot-bg-mid) 52%, var(--taxbot-bg-end) 100%);
      }
      .block-container { max-width: 1160px; padding-top: 1.15rem; padding-bottom: 5rem; }
      [data-testid="stSidebar"] {
        width: var(--taxbot-sidebar-width) !important;
        min-width: var(--taxbot-sidebar-width) !important;
        max-width: var(--taxbot-sidebar-width) !important;
        background:
          linear-gradient(135deg, var(--taxbot-bg-start) 0%, var(--taxbot-bg-mid) 52%, var(--taxbot-bg-end) 100%);
        border-right: 1px solid var(--taxbot-border);
      }
      [data-testid="stSidebar"] > div {
        width: var(--taxbot-sidebar-width) !important;
      }
      [data-testid="stSidebar"] h1 { color: var(--taxbot-text); }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: var(--taxbot-muted);
      }
      .hero-panel {
        position: relative;
        overflow: hidden;
        margin-bottom: 18px;
        border: 1px solid rgba(255, 255, 255, 0.7);
        border-radius: 8px;
        background:
          linear-gradient(135deg, var(--taxbot-primary) 0%, #1d4ed8 48%, var(--taxbot-orange) 100%);
        color: #ffffff;
        box-shadow: 0 18px 40px rgba(11, 99, 206, 0.18);
      }
      .hero-strip {
        height: 7px;
        background: linear-gradient(90deg, #38bdf8, #0b63ce, #facc15, #f97316);
      }
      .hero-panel h1 {
        max-width: 820px;
        margin: 0;
        padding: 18px 22px 0;
        color: #ffffff;
        font-size: 30px;
        line-height: 1.18;
        letter-spacing: 0;
      }
      .hero-panel p {
        max-width: 780px;
        margin: 0;
        padding: 10px 22px 0;
        color: rgba(255, 255, 255, 0.9);
        line-height: 1.55;
      }
      .hero-kicker {
        padding: 18px 22px 0;
        color: rgba(255, 255, 255, 0.86);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }
      .hero-stats {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        padding: 18px 22px 22px;
      }
      .hero-stats span {
        min-width: 0;
        border: 1px solid rgba(255, 255, 255, 0.35);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.14);
        padding: 10px 11px;
        color: rgba(255, 255, 255, 0.86);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .hero-stats strong {
        display: block;
        color: #ffffff;
        font-size: 17px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .stMetric {
        border: 1px solid var(--taxbot-line);
        border-radius: 8px;
        padding: 10px;
        background: var(--taxbot-surface-strong);
      }
      div[data-testid="stChatMessage"] {
        border-radius: 8px;
        border: 1px solid var(--taxbot-border);
        background: var(--taxbot-surface);
        box-shadow: 0 10px 24px rgba(16, 35, 63, 0.06);
      }
      .answer-panel {
        border-left: 4px solid var(--taxbot-primary);
        padding: 2px 0 2px 14px;
      }
      .source-panel {
        margin-top: 12px;
        padding: 12px 14px;
        border: 1px solid var(--taxbot-border);
        border-radius: 8px;
        background: linear-gradient(135deg, var(--taxbot-primary-soft) 0%, var(--taxbot-surface-strong) 100%);
      }
      .evidence-card {
        margin: 12px 0 10px;
        border: 1px solid var(--taxbot-border);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.74);
        padding: 12px 14px;
      }
      .evidence-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 18px;
        align-items: center;
        color: var(--taxbot-muted);
        font-size: 14px;
      }
      .evidence-metrics strong {
        color: var(--taxbot-text);
      }
      .metric-pill {
        display: inline-block;
        border: 1px solid rgba(249, 115, 22, 0.34);
        border-radius: 8px;
        background: var(--taxbot-orange-soft);
        color: var(--taxbot-orange-strong) !important;
        padding: 3px 9px;
      }
      .evidence-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }
      .evidence-chip {
        display: inline-flex;
        max-width: 100%;
        align-items: center;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 13px;
        font-weight: 650;
        line-height: 1.25;
      }
      .chip-blue {
        border: 1px solid rgba(11, 99, 206, 0.24);
        background: var(--taxbot-primary-soft);
        color: var(--taxbot-primary-strong);
      }
      .chip-orange {
        border: 1px solid rgba(249, 115, 22, 0.28);
        background: var(--taxbot-orange-soft);
        color: var(--taxbot-orange-strong);
      }
      .source-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 4px;
        font-size: 14px;
      }
      .source-table th,
      .source-table td {
        border-bottom: 1px solid var(--taxbot-line);
        padding: 10px 12px;
        text-align: left;
        vertical-align: top;
      }
      .source-table th {
        color: var(--taxbot-text);
        background: #f7fbff;
        font-weight: 800;
      }
      .source-table td:first-child,
      .source-table td:last-child {
        white-space: nowrap;
      }
      .source-table td:last-child strong {
        color: var(--taxbot-primary);
      }
      .excerpt-card {
        border-left: 4px solid var(--taxbot-orange);
        border-radius: 8px;
        background: var(--taxbot-orange-soft);
        margin-bottom: 10px;
        padding: 10px 12px;
      }
      .excerpt-card p {
        margin: 6px 0 0;
        color: var(--taxbot-muted);
        line-height: 1.55;
      }
      .trust-row {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
        margin: 12px 0 4px;
      }
      .trust-row > div {
        border: 1px solid var(--taxbot-line);
        border-radius: 8px;
        background: var(--taxbot-surface-strong);
        padding: 10px 11px;
      }
      .trust-row > div:nth-child(1) { border-color: rgba(11, 99, 206, 0.28); background: #eff6ff; }
      .trust-row > div:nth-child(2) { border-color: rgba(249, 115, 22, 0.25); background: var(--taxbot-orange-soft); }
      .trust-row > div:nth-child(3) { border-color: rgba(11, 99, 206, 0.24); background: #f7fbff; }
      .trust-row > div:nth-child(4) { border-color: rgba(249, 115, 22, 0.25); background: var(--taxbot-orange-soft); }
      .trust-row strong {
        display: block;
        color: var(--taxbot-primary);
        font-size: 18px;
        line-height: 1.15;
      }
      .trust-row > div:nth-child(2) strong { color: var(--taxbot-orange); }
      .trust-row > div:nth-child(3) strong { color: var(--taxbot-primary-strong); }
      .trust-row > div:nth-child(4) strong { color: var(--taxbot-orange-strong); }
      .trust-row span {
        display: block;
        margin-top: 3px;
        color: var(--taxbot-muted);
        font-size: 12px;
      }
      div[data-testid="stButton"] > button {
        border-radius: 8px;
        border-color: rgba(11, 99, 206, 0.22);
        background: var(--taxbot-surface-strong);
        color: var(--taxbot-text);
        transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
      }
      div[data-testid="stButton"] > button:hover {
        border-color: rgba(249, 115, 22, 0.55);
        color: var(--taxbot-primary);
        box-shadow: 0 8px 20px rgba(11, 99, 206, 0.12);
        transform: translateY(-1px);
      }
      button[kind="primary"],
      [data-testid="stBaseButton-primary"] {
        border-color: var(--taxbot-primary) !important;
        background: var(--taxbot-primary) !important;
        color: #ffffff !important;
      }
      button[kind="primary"]:hover,
      [data-testid="stBaseButton-primary"]:hover {
        border-color: var(--taxbot-orange) !important;
        background: var(--taxbot-orange) !important;
        color: #ffffff !important;
      }
      [data-testid="stCheckbox"] input:checked,
      [data-testid="stCheckbox"] input:focus {
        accent-color: var(--taxbot-primary) !important;
      }
      [data-testid="stCheckbox"] svg,
      [data-testid="stCheckbox"] [data-baseweb="checkbox"] svg {
        color: #ffffff !important;
        fill: #ffffff !important;
      }
      [data-testid="stCheckbox"] [data-baseweb="checkbox"] span:first-child {
        border-color: var(--taxbot-primary) !important;
      }
      [data-testid="stSlider"] {
        accent-color: var(--taxbot-primary) !important;
      }
      [data-testid="stSlider"] [role="slider"] {
        background: var(--taxbot-primary) !important;
        border-color: var(--taxbot-primary) !important;
        box-shadow: 0 0 0 2px rgba(11, 99, 206, 0.18) !important;
      }
      [data-testid="stSlider"] [data-baseweb="slider"] div {
        border-color: rgba(11, 99, 206, 0.18);
      }
      [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(2) div[data-testid="stButton"] {
        opacity: 0;
        transition: opacity 120ms ease;
      }
      [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:hover div[data-testid="column"]:nth-of-type(2) div[data-testid="stButton"],
      [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(2) div[data-testid="stButton"]:focus-within {
        opacity: 1;
      }
      [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(2) button {
        min-width: 42px;
        padding-left: 6px;
        padding-right: 6px;
        white-space: nowrap;
      }
      [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(1) button {
        justify-content: flex-start;
        min-height: 44px;
        padding: 9px 10px;
        text-align: left;
        overflow: hidden;
      }
      [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(1) button p {
        width: 100%;
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        text-align: left;
        white-space: nowrap;
        line-height: 1.25;
      }
      .legal-note {
        color: var(--taxbot-muted);
        font-size: 12px;
        line-height: 1.45;
      }
      .sidebar-note {
        border: 1px solid var(--taxbot-border);
        border-radius: 8px;
        background: linear-gradient(135deg, var(--taxbot-primary-soft) 0%, var(--taxbot-surface-strong) 100%);
        padding: 10px 12px;
        color: var(--taxbot-text);
        font-size: 13px;
        line-height: 1.45;
      }
      [data-testid="stChatInput"] {
        border-top-color: var(--taxbot-border);
      }
      [data-testid="stChatInputSubmitButton"],
      [data-testid="stChatInput"] button {
        border-color: var(--taxbot-primary) !important;
        background: var(--taxbot-primary) !important;
        color: #ffffff !important;
      }
      [data-testid="stChatInputSubmitButton"]:hover,
      [data-testid="stChatInput"] button:hover {
        border-color: var(--taxbot-orange) !important;
        background: var(--taxbot-orange) !important;
        color: #ffffff !important;
      }
      [data-testid="stChatInputSubmitButton"] svg,
      [data-testid="stChatInput"] button svg {
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
      }
      [data-testid="stChatInput"] textarea,
      [data-testid="stChatInput"] div[contenteditable="true"] {
        border-color: var(--taxbot-border) !important;
        background: var(--taxbot-surface-strong) !important;
        color: var(--taxbot-text) !important;
      }
      [data-testid="stChatInput"] textarea:focus,
      [data-testid="stChatInput"] div[contenteditable="true"]:focus {
        border-color: var(--taxbot-primary) !important;
        box-shadow: 0 0 0 3px rgba(11, 99, 206, 0.14) !important;
      }
      [data-testid="stChatMessageAvatarUser"],
      [data-testid="stChatMessageAvatarUser"] > div,
      [data-testid="stChatMessageAvatarUser"] span {
        border-color: var(--taxbot-primary) !important;
        background: var(--taxbot-primary) !important;
        color: #ffffff !important;
      }
      [data-testid="stChatMessageAvatarAssistant"],
      [data-testid="stChatMessageAvatarAssistant"] > div,
      [data-testid="stChatMessageAvatarAssistant"] span {
        border-color: var(--taxbot-orange) !important;
        background: var(--taxbot-orange) !important;
        color: #ffffff !important;
      }
      [data-testid="stChatMessageAvatarUser"] svg,
      [data-testid="stChatMessageAvatarAssistant"] svg {
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
      }
      [data-testid="stAlert"] {
        border-color: rgba(249, 115, 22, 0.24) !important;
        background: var(--taxbot-orange-soft) !important;
        color: var(--taxbot-text) !important;
      }
      [data-testid="stAlert"] svg {
        color: var(--taxbot-orange) !important;
        fill: var(--taxbot-orange) !important;
      }
      @media (max-width: 760px) {
        .hero-panel h1 { font-size: 24px; padding-left: 14px; padding-right: 14px; }
        .hero-kicker,
        .hero-panel p,
        .hero-stats { padding-left: 14px; padding-right: 14px; }
        .hero-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .evidence-metrics { display: grid; grid-template-columns: 1fr; }
        .source-table { font-size: 13px; }
        .source-table th,
        .source-table td { padding: 8px; }
        .trust-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 460px) {
        .hero-stats,
        .trust-row { grid-template-columns: 1fr; }
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("RAG TaxBot")
    st.caption("Tự động lưu lịch sử hỏi đáp trên máy này.")

    if st.button("Tạo cuộc trò chuyện mới", use_container_width=True):
        start_new_conversation()
        st.rerun()

    st.divider()
    st.subheader("Cuộc trò chuyện")
    for conversation in chat_store.list_conversations():
        is_current = conversation["id"] == st.session_state.conversation_id
        title = normalize_conversation_title(conversation["title"])
        row = st.columns([0.84, 0.16], gap="small")
        with row[0]:
            if st.button(
                ("● " if is_current else "") + truncate_label(title),
                key=f"conversation_{conversation['id']}",
                help=title,
                type="secondary",
                use_container_width=True,
            ):
                open_conversation(conversation["id"])
                st.rerun()
        with row[1]:
            if st.button(
                "🗑",
                key=f"delete_{conversation['id']}",
                help="Xóa cuộc trò chuyện này",
                use_container_width=True,
            ):
                chat_store.delete_conversation(conversation["id"])
                conversations_after_delete = chat_store.list_conversations()
                if conversations_after_delete:
                    open_conversation(conversations_after_delete[0]["id"])
                else:
                    start_new_conversation()
                st.rerun()

    st.divider()
    st.subheader("Bảng điều khiển")
    st.selectbox(
        "Chủ đề gợi ý",
        options=list(TOPIC_QUESTIONS.keys()),
        key="suggestion_topic",
        help="Chọn chủ đề rồi bấm nút đổi bộ câu hỏi gợi ý ở sidebar.",
    )
    st.slider(
        "Số căn cứ pháp lý hiển thị",
        min_value=2,
        max_value=6,
        key="max_sources",
        help="Giữ phần căn cứ ngắn gọn nhưng vẫn đủ để demo.",
    )
    st.checkbox(
        "Hiện chi tiết xử lý",
        key="show_runtime",
        help="Bật để xem mode RAG, router, số nguồn và thời gian xử lý.",
    )
    if st.button("Đổi bộ câu hỏi gợi ý", use_container_width=True):
        refresh_suggestions()
        st.rerun()

    st.markdown(
        f"""
        <div class="sidebar-note">
          <strong>Trạng thái</strong><br>
          {processed_document_count()} văn bản đã xử lý · Retrieval local TF-IDF<br>
          Model: {settings.MODEL_NAME}<br>
          Lưu lịch sử: SQLite local
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="legal-note">Thông tin chỉ hỗ trợ tra cứu quy định thuế, không thay thế tư vấn pháp lý hoặc ý kiến của chuyên gia thuế.</p>',
        unsafe_allow_html=True,
    )

render_hero()

for stored_message in st.session_state.messages:
    render_message(stored_message)

if chat_store.message_count(st.session_state.conversation_id) == 0:
    st.info("Chọn một câu hỏi gợi ý hoặc nhập tình huống thuế của bạn để bắt đầu.")

st.markdown("**Câu hỏi phổ biến**")
suggestion_cols = st.columns(4)
for index, question in enumerate(current_suggestions()):
    with suggestion_cols[index % 4]:
        if st.button(question, key=f"suggest_{index}_{question}", use_container_width=True):
            st.session_state.pending_prompt = question
            st.rerun()

pending_prompt = st.session_state.pop("pending_prompt", None)
typed_prompt = st.chat_input("Nhập câu hỏi về thuế...")
prompt = pending_prompt or typed_prompt

if prompt:
    submit_prompt(prompt)
