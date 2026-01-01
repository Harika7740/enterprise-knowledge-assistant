# app.py - FIXED: Replace old docs on new upload (no more old answers)
import streamlit as st
from document_loader import load_document
from rag_pipeline import build_index, get_answer

st.set_page_config(page_title="Knowledge Assistant", layout="wide")

# Center the title and caption
st.markdown(
    """
    <h1 style="text-align: center;">Enterprise Knowledge Assistant</h1>
    <p style="text-align: center; color: #666;">
    Upload a document and ask questions to get accurate insights from its content.
    </p>
    <br><br>
    """,
    unsafe_allow_html=True
)

# Session state
if "docs" not in st.session_state:
    st.session_state.docs = []          # list of (text, meta, df)
if "history" not in st.session_state:
    st.session_state.history = []
if "indexed" not in st.session_state:
    st.session_state.indexed = False

# Layout: Clear Chat button and uploader
col_clear, col_spacer = st.columns([1, 5])

with col_clear:
    if st.session_state.indexed:
        if st.button("Clear Chat"):
            st.session_state.history = []   # Clears conversation
            st.rerun()                      # Immediate refresh

# Left-aligned uploader
st.markdown(
    """
    <div style="max-width: 600px;">
    """,
    unsafe_allow_html=True
)

files = st.file_uploader(
    "Drag and drop file here",
    type=["pdf", "docx", "pptx", "xlsx", "xls", "csv", "txt", "jpg", "jpeg", "png"],
    accept_multiple_files=False,
    help="Limit 200MB per file • PDF, DOCX, PPTX, XLSX, CSV, TXT, JPG, JPEG, PNG",
    label_visibility="collapsed"
)

st.markdown("</div>", unsafe_allow_html=True)

# Spacing after uploader
st.markdown("<br><br>", unsafe_allow_html=True)

# Process uploaded file (clean UI - no success message)
if files:
    new_docs = []
    with st.spinner("Processing file..."):
        for f in [files]:
            text, meta, df = load_document(f)
            if text and not text.startswith("[ERROR]") and not text.startswith("Excel/CSV loading failed"):
                new_docs.append((text, meta, df))
            else:
                st.error(f"Failed to process {f.name}")

    if new_docs:
        st.session_state.docs = new_docs  # ← FIXED: Replace old docs (no extend)
        build_index([(t, m) for t, m, _ in new_docs])
        st.session_state.indexed = True

# Chat history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
prompt = st.chat_input("Ask a question about your document..." if st.session_state.indexed else "Upload a document first...")

if prompt and st.session_state.indexed:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = get_answer(prompt, st.session_state.history, st.session_state.docs)
        st.markdown(answer)

    st.session_state.history.append({"role": "assistant", "content": answer})
