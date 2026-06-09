from __future__ import annotations

import sys
import uuid
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


def default_messages() -> list[dict[str, Any]]:
    return [
        {
            "role": "assistant",
            "content": "Xin chao, toi la RAG TaxBot. Hay nhap cau hoi ve thue.",
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


def render_message_body(message: dict[str, Any]) -> None:
    if message.get("error"):
        st.error(message["error"])
    else:
        st.markdown(message.get("content") or "")

    sources = message.get("sources") or []
    if sources:
        st.subheader("Nguon truy xuat")
        for index, source in enumerate(sources, start=1):
            render_source(source, index)


def render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message["role"]):
        render_message_body(message)


st.set_page_config(page_title="RAG TaxBot", layout="wide")
init_state()

st.markdown(
    """
    <style>
      .block-container { max-width: 1180px; padding-top: 1.2rem; }
      [data-testid="stSidebar"] { min-width: 300px; }
      .stMetric { border: 1px solid #e3e8ef; border-radius: 8px; padding: 10px; }
      div[data-testid="stChatMessage"] { border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("RAG TaxBot")

    if st.button("Tao cuoc tro chuyen moi", use_container_width=True):
        start_new_conversation()
        st.rerun()

    if st.button("Xoa cuoc tro chuyen nay", use_container_width=True):
        chat_store.delete_conversation(st.session_state.conversation_id)
        conversations_after_delete = chat_store.list_conversations()
        if conversations_after_delete:
            open_conversation(conversations_after_delete[0]["id"])
        else:
            start_new_conversation()
        st.rerun()

    st.divider()
    st.subheader("Lich su cuoc tro chuyen")
    for conversation in chat_store.list_conversations():
        is_current = conversation["id"] == st.session_state.conversation_id
        if st.button(
            conversation["title"],
            key=f"conversation_{conversation['id']}",
            type="primary" if is_current else "secondary",
            use_container_width=True,
        ):
            open_conversation(conversation["id"])
            st.rerun()

st.title("RAG TaxBot")

for stored_message in st.session_state.messages:
    render_message(stored_message)

prompt = st.chat_input("Nhap cau hoi ve thue...")

if prompt:
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
        with st.spinner("Dang xu ly RAG local..."):
            try:
                data = run_chat(prompt)
                assistant_message = {
                    "role": "assistant",
                    "content": data.get("answer") or "Pipeline khong tra ve cau tra loi.",
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
                    "error": f"Pipeline gap loi: {exc}",
                }

        render_message_body(assistant_message)

    st.session_state.messages.append(assistant_message)
    chat_store.add_message(conversation_id, assistant_message)
