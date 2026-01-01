import re
import os
import numpy as np
from groq import Groq
from dotenv import load_dotenv
from vector_store import embedder, create_vector_index
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
index = None
all_meta = []
def build_index(documents):
    global index, all_meta
    index, all_meta = create_vector_index(documents)
def retrieve_relevant_chunks(query, top_k=5):
    global index, all_meta
    if index is None or not all_meta:
        return []
    query_emb = embedder.encode([query], normalize_embeddings=True).astype('float32')
    D, I = index.search(query_emb, top_k)
    chunks = []
    for i, d in zip(I[0], D[0]):
        if i != -1 and d > 0.5:
            chunks.append(all_meta[i]["chunk_text"])
    return chunks
def get_answer(query, chat_history, documents):
    query_lower = query.lower().strip()
    full_text = ""
    meta = {}
    df = None
    if documents:
        first_doc = documents[0]
        full_text = first_doc[0]
        meta = first_doc[1]
        df = first_doc[2] if len(first_doc) > 2 else None
    is_image = meta.get("ocr", False) or "image" in meta.get("file_type", "")
    # Image block - unchanged
    if is_image and full_text.strip():
        context = full_text
        if "district" in query_lower:
            patterns = [
                r'(?:district|dist|DISTRICT)[\s\:–\-]*([A-Za-z\s&]+?)(?:\n|$|,|\.|Zone)',
                r'\b([A-Z][A-Za-z\s&]+)\s+District\b',
                r'District\s*[:\-–]\s*([A-Za-z\s&]+)',
                r'District Name[\s\:–\-]*([A-Za-z\s&]+)',
                r'(?:Dist\.?|District)[\s\:]*([A-Za-z\s&]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, context, re.IGNORECASE)
                if match:
                    district = match.group(1).strip().title()
                    district = re.sub(r'\s+Zone.*$', '', district, flags=re.IGNORECASE)
                    if len(district) > 2:
                        return f"The district name is **{district}**."
        if any(w in query_lower for w in ["person", "people", "persons", "how many"]):
            names = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b', context)
            exclude = {"The", "And", "For", "Date", "Signature", "Name", "District", "State", "Certificate", "Photo", "Office", "Form", "Application", "Id", "No", "Of", "In"}
            names = [n for n in names if n not in exclude]
            count = len(names)
            if count > 0:
                names_list = ', '.join(names[:6])
                extra = " and more" if count > 6 else ""
                return f"There are **{count} persons** in the image.\nNames found: {names_list}{extra}"
            return "No persons detected in the image."
        if any(w in query_lower for w in ["read", "text", "what is written", "describe", "image", "photo"]):
            lines = [line.strip() for line in context.split('\n') if line.strip()][:100]
            displayed = "\n".join(lines)
            return f"**Text from image:**\n\n{displayed}"
    # FINAL EXCEL TIMESHEET BLOCK - added Holiday count support
    if df is not None and any(word in query_lower for word in ["present", "leave", "absent", "holiday", "holidays", "attendance", "how many", "count", "on leave", "attended", "status"]):
        # Detect date/attendance columns
        date_cols = [col for col in df.columns if (str(col).strip().isdigit() or 
                                                   '/' in str(col) or 
                                                   '-' in str(col) or 
                                                   'unnamed' in str(col).lower())]
        if date_cols:
            attendance_data = df[date_cols].astype(str).stack()
            attendance_data = attendance_data.str.strip()
            attendance_data = attendance_data[attendance_data.str.lower() != 'nan']
            
            present_count = attendance_data.str.contains('present', case=False, na=False).sum() + \
                            attendance_data.str.upper().str.contains('^P$', na=False).sum()
            leave_count = attendance_data.str.contains('leave', case=False, na=False).sum() + \
                          attendance_data.str.upper().str.contains('^L$', na=False).sum()
            absent_count = attendance_data.str.contains('absent', case=False, na=False).sum() + \
                           attendance_data.str.upper().str.contains('^A$', na=False).sum()
            holiday_count = attendance_data.str.contains('holiday', case=False, na=False).sum() + \
                            attendance_data.str.upper().str.contains('^H$', na=False).sum()  # if 'H' used
            total_entries = len(attendance_data)
            
            if "present" in query_lower or "attended" in query_lower:
                return f"**{present_count} present entries found across the timesheet.**"
            elif "leave" in query_lower or "on leave" in query_lower:
                return f"**{leave_count} leave entries found across the timesheet.**"
            elif "absent" in query_lower:
                return f"**{absent_count} absent entries found.**"
            elif "holiday" in query_lower or "holidays" in query_lower:
                return f"**{holiday_count} holiday entries found across the timesheet.**"
            else:
                return f"**Timesheet Attendance Summary:**\n- Present: {present_count}\n- Leave: {leave_count}\n- Absent: {absent_count}\n- Holiday: {holiday_count}\n- Total Entries: {total_entries}\n- Total Employees: {len(df)}"
        return "No attendance columns detected."
    # FIXED: PDF - better title extraction from content, pages, leave policies
    if not is_image and df is None and full_text.strip():
        if any(w in query_lower for w in ["title", "main title", "name of the document"]):
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            if lines:
                potential_title = lines[0]
                title_match = re.search(r'^[A-Z][A-Z0-9\s&-]{5,}$', potential_title, re.MULTILINE)
                if title_match:
                    return f"The title of the document is **{title_match.group(0).title()}**."
                return f"The title of the document is **{potential_title.title()}**."
            file_name = meta.get("file_name", "Unknown").replace(".pdf", "").replace("_", " ").title()
            return f"The title of the document is **{file_name}**."
        if "how many pages" in query_lower or "number of pages" in query_lower:
            pages = meta.get("pages", len(full_text.split('\f')) if '\f' in full_text else "Unknown")
            return f"The document has **{pages} pages**."
        if "how many leave policies" in query_lower or "leave policies" in query_lower:
            leave_keywords = r'\b(sick|casual|annual|earned|maternity|paternity|bereavement|jury|unpaid|paid|compensatory|privilege|floating|sabbatical|study)\s*leave\b'
            leave_types = len(set(re.findall(leave_keywords, full_text, re.IGNORECASE)))
            return f"There are **{leave_types} unique leave policies** applicable in the document."
    # RAG fallback for other questions
    chunks = retrieve_relevant_chunks(query, top_k=5)
    context = "\n".join(chunks)
    if not context and full_text:
        context = full_text[:4000] + "..." if len(full_text) > 4000 else full_text
    history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[:-1]])
    system_prompt = "You are a helpful knowledge assistant. Answer based on the provided context accurately."
    user_prompt = f"Context: {context}\n\nHistory: {history_str}\n\nQuestion: {query}\n\nAnswer:"
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"