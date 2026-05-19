import uuid

import streamlit as st

from main import run_agent

st.set_page_config(page_title="Career Intelligence Agent", layout="wide")
st.title("Career Intelligence Agent")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"web-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask your career agent..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = run_agent(prompt, st.session_state.thread_id)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
