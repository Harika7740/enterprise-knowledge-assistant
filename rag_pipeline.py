from groq import Groq
import streamlit as st 
import re
from vector_store import create_index, retrieve_chunks


client = Groq(api_key=st.secrets["GROQ_API_KEY"])

INDEX = None
CHUNKS = None

def build_index(doc_data):
    global INDEX, CHUNKS
    INDEX, CHUNKS = create_index(doc_data)

def get_answer(query, full_text, metadata, image_base64=None):
    query_lower = query.lower()

    # ==================== LEAVE POLICY LOGIC  ====================
    if "sick" in query_lower or "medical" in query_lower:
        matches = re.findall(r'(sick|medical|illness|sickness).*?(\d+)', full_text, re.IGNORECASE | re.DOTALL)
        if matches:
            return f"Sick/Medical Leave: {matches[-1][1]} days per year."
        return "Sick leave entitlement not mentioned."

    if "casual" in query_lower:
        matches = re.findall(r'casual.*?(\d+)', full_text, re.IGNORECASE)
        if matches:
            return f"Casual Leave: {matches[-1]} days per year."
        return "Casual leave entitlement not mentioned."

    if "annual" in query_lower or "earned" in query_lower or "privilege" in query_lower:
        matches = re.findall(r'(annual|earned|privilege).*?(\d+)', full_text, re.IGNORECASE)
        if matches:
            return f"Annual/Earned Leave: {matches[-1][1]} days per year."
        return "Annual leave entitlement not mentioned."

   
    if any(w in query_lower for w in ["page", "pages", "slide"]) and any(w in query_lower for w in ["count", "number", "how many"]):
        pages = metadata.get("pages", metadata.get("slides", 0))
        return f"{pages} pages." if pages else "Page count unknown."

    if any(w in query_lower for w in ["word", "words"]) and any(w in query_lower for w in ["count", "number", "how many"]):
        words = len(re.findall(r'\w+', full_text))
        return f"{words} words approx."

    if "row" in query_lower and any(w in query_lower for w in ["count", "number", "how many", "total"]):
        lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
        total_lines = len(lines)
        if total_lines == 0:
            return "No rows found."
        return f"Total rows: {total_lines}"

    
    if any(word in query_lower for word in ["present", "absent", "holiday", "leave", "status"]) and \
       any(count_word in query_lower for count_word in ["how many", "number", "count", "total", "howmuch"]):
        counts = {"Present": 0, "Absent": 0, "Holiday": 0, "Leave": 0}
        names_dict = {"Present": [], "Absent": [], "Holiday": [], "Leave": []}
        lines = full_text.splitlines()
        status_col = None
        name_col = None
        headers_found = False

        for line in lines:
            cells = [c.strip() for c in re.split(r'\s{2,}|\t|,', line) if c.strip()]
            if len(cells) < 2:
                continue
            if not headers_found:
                for i, cell in enumerate(cells):
                    lc = cell.lower()
                    if "status" in lc or "stat" in lc:
                        status_col = i
                    if "name" in lc or "emp" in lc or "employee" in lc:
                        name_col = i
                if status_col is not None:
                    headers_found = True
                continue
            if status_col is not None and len(cells) > status_col:
                raw = cells[status_col]
                status = raw.capitalize()
                if status.startswith("Pres"):
                    status = "Present"
                elif status.startswith("Abs"):
                    status = "Absent"
                elif "hol" in raw.lower():
                    status = "Holiday"
                elif "lea" in raw.lower() or "lv" in raw.lower():
                    status = "Leave"

                if status in counts:
                    counts[status] += 1
                    name = cells[name_col] if name_col is not None and len(cells) > name_col else "Unknown"
                    names_dict[status].append(name)

        if any(w in query_lower for w in ["who", "name", "which", "list"]):
            for key in ["Present", "Absent", "Holiday", "Leave"]:
                if key.lower() in query_lower and names_dict[key]:
                    names = ", ".join(names_dict[key][:8])
                    return f"{key}: {names}" + (" and more." if len(names_dict[key]) > 8 else ".")

        if "present" in query_lower:
            return f"Present: {counts['Present']}"
        if "absent" in query_lower:
            return f"Absent: {counts['Absent']}"
        if "holiday" in query_lower:
            return f"Holiday: {counts['Holiday']}"
        if "leave" in query_lower:
            return f"Leave: {counts['Leave']}"

        parts = [f"{k}: {v}" for k, v in counts.items() if v > 0]
        return "; ".join(parts) if parts else "No attendance data."

    # ==================== RAG ====================
    if INDEX is None or not CHUNKS:
        return "Upload and index a document first."

    try:
        retrieved = retrieve_chunks(INDEX, CHUNKS, query, top_k=4)
        context = "\n\n".join(retrieved) if retrieved else full_text[:8000]
        if len(context) > 12000:
            context = context[:12000] + "..."

        prompt = f"""You are a precise document assistant. Use ONLY the context below to answer. Be direct and concise. Use bullet points for lists.
Context: {context}
Question: {query}
Answer:"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)[:60]}. Try again."