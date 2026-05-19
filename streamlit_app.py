import uuid

import streamlit as st

from main import run_agent

st.set_page_config(
    page_title="Career Intelligence",
    page_icon="💼",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 1rem;
        max-width: 760px;
    }

    .app-header { margin-bottom: 0.25rem; }
    .app-subhead {
        color: rgba(232, 234, 240, 0.38);
        font-size: 0.8rem;
        margin-top: -0.75rem;
        margin-bottom: 1.25rem;
        letter-spacing: 0.03em;
    }

    .stChatMessage {
        border-radius: 10px;
        padding: 0.25rem 0.5rem;
    }

    .new-chat-btn {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 0.5rem;
    }

    div[data-testid="stChatInput"] textarea {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h3 class="app-header">Career Intelligence</h3>', unsafe_allow_html=True)
st.markdown('<p class="app-subhead">Job search &nbsp;·&nbsp; Scoring &nbsp;·&nbsp; Interview prep</p>', unsafe_allow_html=True)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"web-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []

_, btn_col = st.columns([5, 1])
with btn_col:
    if st.button("New chat", use_container_width=True):
        st.session_state.thread_id = f"web-{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.rerun()

st.divider()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask your career agent..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner(""):
            response = run_agent(prompt, st.session_state.thread_id)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
