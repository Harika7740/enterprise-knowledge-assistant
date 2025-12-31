import streamlit as st
import base64
from io import BytesIO
from PIL import Image
from document_loader import load_document
from rag_pipeline import build_index, get_answer

st.set_page_config(page_title="Enterprise Knowledge Assistant", layout="wide", initial_sidebar_state="collapsed")


st.markdown("""
<style>
    .main { background-color: #ffffff; padding: 0; }
    .stApp { background-color: #ffffff; }
    .title { 
        text-align: center; 
        font-size: 2.8rem; 
        font-weight: 700; 
        color: #1E293B; 
        margin: 3rem 0 1rem 0; 
        width: 100%;
        display: block;
    }
    .subtitle { text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 1.5rem; }
    .upload-box { max-width: 800px; margin: 0 auto 3rem auto; }
    .clear-chat-container { max-width: 800px; margin: 0 auto 1rem auto; text-align: right; }
</style>
""", unsafe_allow_html=True)

# Title 
st.markdown('<h1 class="title">Enterprise Knowledge Assistant</h1>', unsafe_allow_html=True)

st.markdown('<p class="subtitle">Upload a document and ask questions to get accurate insights from its content.</p>', unsafe_allow_html=True)

# Clear Chat button 
st.markdown('<div class="clear-chat-container">', unsafe_allow_html=True)
if st.button("Clear Chat", type="secondary"):
    st.session_state.chat_history = []
    st.session_state.greeted = False
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# Session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_file_name" not in st.session_state:
    st.session_state.current_file_name = None
if "greeted" not in st.session_state:
    st.session_state.greeted = False

# File uploader 
st.markdown('<div class="upload-box">', unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    "Upload document (PDF, DOCX, PPTX, XLSX, CSV, TXT, JPG, JPEG, PNG)",
    type=["pdf", "docx", "pptx", "xlsx", "csv", "txt", "jpg", "jpeg", "png"],
    label_visibility="collapsed"
)
st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    if st.session_state.current_file_name != uploaded_file.name:
        st.session_state.chat_history = []
        st.session_state.current_file_name = uploaded_file.name
        st.session_state.greeted = False

    with st.spinner("Loading and indexing document..."):
        text, meta = load_document(uploaded_file)
        image_base64_jpeg = None
        if uploaded_file.type.startswith('image/'):
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=95)
            image_base64_jpeg = base64.b64encode(buffered.getvalue()).decode('utf-8')
        if (text and text.strip()) or image_base64_jpeg:
            st.session_state.document_text = text
            st.session_state.meta = meta
            st.session_state.image_base64_jpeg = image_base64_jpeg
            build_index([(text, meta)])  # Single document list
            st.success(f"{uploaded_file.name} indexed successfully! Ask questions below.")
        else:
            st.error("No content extracted. Try another file.")

# Welcome message
if uploaded_file and not st.session_state.greeted:
    welcome_msg = "Your document is ready for analysis. Please feel free to ask any questions about its content."
    st.session_state.chat_history.append({"role": "assistant", "content": welcome_msg})
    st.session_state.greeted = True

# Chat container
chat_container = st.container(height=600)
with chat_container:
    MAX_MESSAGES = 50
    for message in st.session_state.chat_history[-MAX_MESSAGES:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# User input
user_query = st.chat_input("Ask a question about your document...")
if user_query:
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    with st.spinner("Analyzing document..."):
        answer = get_answer(
            user_query,
            st.session_state.document_text,
            st.session_state.meta,
            st.session_state.image_base64_jpeg
        )
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    if len(st.session_state.chat_history) > MAX_MESSAGES:
        st.session_state.chat_history = st.session_state.chat_history[-MAX_MESSAGES:]
    st.rerun()