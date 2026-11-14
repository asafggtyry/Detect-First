from __future__ import annotations

import html
import json
from pathlib import Path
from textwrap import dedent

import streamlit as st

from detect_first.model import MODEL_PATH, predict_scam, load_pipeline
from detect_first.state import Conversation, ConversationStore, create_demo_store


ROOT = Path(__file__).resolve().parent


@st.cache_resource
def get_model():
    return load_pipeline(ROOT / MODEL_PATH)


def initialize_store() -> ConversationStore:
    pipeline = get_model()
    return create_demo_store(lambda text: predict_scam(text, pipeline))


def _render_message(text: str, direction: str, time: str, synthetic: bool) -> str:
    safe_text = html.escape(text).replace("\n", "<br>")
    alignment = "outgoing" if direction == "outgoing" else "incoming"
    label = (
        '<span class="synthetic-tag">synthetic</span>'
        if synthetic
        else ""
    )
    return dedent(f"""
        <div class="message-row {alignment}">
          <div class="message-bubble {alignment}">
            <div>{safe_text}</div>
            <div class="message-meta">{label}{html.escape(time)}</div>
          </div>
        </div>
        """).strip()


def _render_warning(conversation: Conversation) -> None:
    with st.container(border=True):
        st.markdown("### Potential job scam detected")
        if conversation.model_flagged:
            st.markdown(
                "The machine-learning model found wording similar to fraudulent "
                "job postings in its training data."
            )
        else:
            st.markdown(
                "The classifier did not flag this message, but multiple concrete "
                "message patterns still deserve a second look."
            )
        st.caption(
            "A warning is not proof of fraud. The model learned from job postings, "
            "not first-contact texts."
        )
        for item in conversation.evidence:
            st.markdown(f"- **{html.escape(item.category)}:** "
                        f"{html.escape(item.explanation)}")
        block_col, accept_col = st.columns(2)
        if block_col.button(
            "Block sender",
            key=f"block-{conversation.sender_id}",
            use_container_width=True,
        ):
            st.session_state.store.block(conversation.sender_id)
            st.rerun()
        if accept_col.button(
            "Accept anyway",
            key=f"accept-{conversation.sender_id}",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.store.accept_anyway(conversation.sender_id)
            st.rerun()


def _render_conversation_list(store: ConversationStore, selected_id: str) -> None:
    st.markdown("#### Chats")
    st.caption("Simulated conversations · no real messages are accessed")
    for conversation in store.conversations.values():
        avatar = "M" if conversation.sender_id == "mom" else conversation.name[-2:]
        status = " · Blocked" if conversation.blocked else ""
        if conversation.should_warn:
            status += " · Review"
        preview = conversation.preview.replace("\n", " ")
        if len(preview) > 48:
            preview = preview[:45] + "..."
        avatar_col, details_col = st.columns([1, 5])
        with avatar_col:
            st.markdown(
                f'<div class="list-avatar">{html.escape(avatar)}</div>',
                unsafe_allow_html=True,
            )
        with details_col:
            label = f"{conversation.name} · {conversation.messages[-1].time}{status}\n{preview}"
            if st.button(
                label,
                key=f"conversation-{conversation.sender_id}",
                type="primary" if conversation.sender_id == selected_id else "secondary",
                use_container_width=True,
            ):
                st.session_state.selected_id = conversation.sender_id
                st.rerun()


def _render_chat(conversation: Conversation) -> None:
    saved_status = "Saved contact" if conversation.saved_contact else "New number"
    if conversation.blocked:
        saved_status += " · Blocked"
    st.markdown(
        f'<div class="chat-header"><div class="chat-avatar">'
        f'{html.escape(conversation.name[:1])}</div><div>'
        f'<div class="chat-name">{html.escape(conversation.name)}</div>'
        f'<div class="chat-status">{html.escape(saved_status)}</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    if conversation.saved_contact:
        st.caption("Saved contact — automatic scanning is skipped.")
    elif conversation.scanned:
        model_text = (
            "scam-like wording found"
            if conversation.model_flagged
            else "no strong job-posting match"
        )
        st.caption(
            f"First-message scan complete · model: {model_text} · "
            "later messages from this sender are not rescanned"
        )

    message_markup = "".join(
        _render_message(
            message.text,
            message.direction,
            message.time,
            message.synthetic,
        )
        for message in conversation.messages
    )
    st.markdown(
        f'<div class="chat-wallpaper">{message_markup}</div>',
        unsafe_allow_html=True,
    )

    if conversation.blocked:
        st.warning("This simulated sender is blocked.")
    elif conversation.should_warn:
        _render_warning(conversation)
    elif conversation.accepted:
        st.info("You chose to accept this simulated chat. The warning is dismissed.")
    elif conversation.scanned and not conversation.saved_contact:
        st.success("No strong warning. Always use your judgment with unfamiliar senders.")

    outgoing_text = st.chat_input(
        "Message (simulation only)",
        key=f"chat-input-{conversation.sender_id}",
        disabled=conversation.blocked,
    )
    if outgoing_text:
        st.session_state.store.send_outgoing(
            conversation.sender_id, outgoing_text
        )
        st.rerun()


def _render_synthetic_test_panel(store: ConversationStore) -> None:
    with st.expander("Synthetic message testing (not model training)"):
        st.caption(
            "Add your own fictional first-contact message to a simulated number. "
            "The app scans only that sender's first incoming message."
        )
        with st.form("synthetic-test-form", clear_on_submit=False):
            sender_id = st.text_input(
                "Simulated sender ID",
                value="999-000-0000",
            )
            text = st.text_area(
                "Synthetic message",
                value="We are hiring for remote work. Reply now to learn more.",
            )
            submitted = st.form_submit_button(
                "Add and scan first message",
                type="primary",
            )
        if submitted:
            if not text.strip():
                st.error("Enter a message before scanning.")
            else:
                conversation = store.add_test_conversation(sender_id, text)
                st.session_state.selected_id = conversation.sender_id
                st.rerun()


def _render_model_info() -> None:
    with st.expander("About the prototype AI"):
        st.markdown(
            "The classifier is a locally trained TF-IDF + logistic regression "
            "model using public job-posting data. That source is not first-contact "
            "SMS, so a good-looking demo result is not proof of real-world accuracy."
        )
        report_path = ROOT / "reports" / "job_posting_metrics.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            metrics = report["model"]["metrics"]
            baseline = report["baselines"]["always_legitimate"]
            st.write(
                f"Job-posting holdout: precision {metrics['precision']:.3f}, "
                f"recall {metrics['recall']:.3f}, F1 {metrics['f1']:.3f}; "
                f"always-legitimate baseline F1 {baseline['f1']:.3f}."
            )
        else:
            st.caption("Run scripts/train_model.py to generate the report.")


def main() -> None:
    st.set_page_config(
        page_title="Detect First",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        .stApp { background: #f5f6f4; color: #17211f; }
        .block-container { max-width: 1180px; padding-top: 1.2rem; }
        div[data-testid="stHorizontalBlock"] { gap: 1rem; }
        .brand-bar {
          background: #075e54; color: white; border-radius: 16px 16px 0 0;
          padding: 18px 22px; margin-bottom: 12px;
        }
        .brand-title { font-size: 1.65rem; font-weight: 750; margin: 0; }
        .brand-subtitle { color: #d7eee9; font-size: .9rem; margin-top: 2px; }
        .chat-header {
          display: flex; align-items: center; gap: 12px; background: #075e54;
          color: white; border-radius: 12px 12px 0 0; padding: 12px 15px;
        }
        .chat-avatar {
          width: 42px; height: 42px; border-radius: 50%; display: grid;
          place-items: center; background: #c8e7dc; color: #075e54;
          font-weight: 700; font-size: 1.1rem;
        }
        .list-avatar {
          width: 42px; height: 42px; border-radius: 50%; display: grid;
          place-items: center; background: #d3e8df; color: #075e54;
          font-weight: 700; margin: 4px auto;
        }
        .chat-name { font-weight: 700; font-size: 1.05rem; }
        .chat-status { color: #d7eee9; font-size: .8rem; }
        .chat-wallpaper {
          background-color: #efe9df;
          background-image: radial-gradient(#dfd8cf 1px, transparent 1px);
          background-size: 16px 16px; padding: 12px 10px; min-height: 160px;
          border-radius: 0 0 12px 12px; margin-bottom: 10px;
        }
        .message-row { display: flex; margin: 7px 0; }
        .message-row.incoming { justify-content: flex-start; }
        .message-row.outgoing { justify-content: flex-end; }
        .message-bubble {
          max-width: 88%; padding: 9px 12px 6px; border-radius: 12px;
          box-shadow: 0 1px 2px #00000012; overflow-wrap: anywhere;
        }
        .message-bubble.incoming { background: white; border-top-left-radius: 4px; }
        .message-bubble.outgoing { background: #d9fdd3; border-top-right-radius: 4px; }
        .message-meta { color: #75827d; font-size: .72rem; text-align: right; margin-top: 3px; }
        .synthetic-tag { color: #075e54; font-weight: 700; margin-right: 6px; }
        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
          border-radius: 10px; text-align: left; background: #ffffff !important;
          color: #17211f !important; border: 1px solid #d2ddd7 !important;
        }
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
          background: #087f68 !important; color: #ffffff !important;
          border-color: #087f68 !important;
        }
        div[data-testid="stChatInput"] textarea {
          background: #ffffff !important; color: #17211f !important;
        }
        @media (max-width: 720px) {
          .block-container { padding: .6rem .5rem 1rem; }
          .message-bubble { max-width: 94%; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    title_col, reset_col = st.columns([5, 1])
    with title_col:
        st.markdown(
            """
            <div class="brand-bar">
              <div class="brand-title">Detect First</div>
              <div class="brand-subtitle">Pause before you reply to a job offer</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if reset_col.button("Reset demo", use_container_width=True):
        st.session_state.store = initialize_store()
        st.session_state.selected_id = "732-882-1944"
        st.rerun()

    if "store" not in st.session_state:
        st.session_state.store = initialize_store()
    store: ConversationStore = st.session_state.store
    if (
        "selected_id" not in st.session_state
        or st.session_state.selected_id not in store.conversations
    ):
        st.session_state.selected_id = "732-882-1944"

    list_col, chat_col = st.columns([1, 1.65])
    with list_col:
        _render_conversation_list(store, st.session_state.selected_id)
    with chat_col:
        _render_chat(store.get(st.session_state.selected_id))

    _render_synthetic_test_panel(store)
    _render_model_info()
    st.caption("This project is a prototype and is not financial advice.")


if __name__ == "__main__":
    main()
