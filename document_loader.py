import pandas as pd
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from PIL import Image
import pytesseract
import io

def load_document(file):
    file_name = file.name.lower()
    ext = file_name.split('.')[-1]
    metadata = {"file_name": file.name, "file_type": ext}

    try:
        if ext == "pdf":
            reader = PdfReader(file)
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            metadata["pages"] = len(reader.pages)

        elif ext == "docx":
            doc = Document(file)
            text_parts = []

            # Extract paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text.strip())

            # Extract tables (THIS WAS MISSING – main fix!)
            for table in doc.tables:
                for row in table.rows:
                    row_text = "\t".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text_parts.append(row_text)

            # Optional: headers/footers (rare but good)
            for section in doc.sections:
                header = section.header
                for para in header.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text.strip())
                footer = section.footer
                for para in footer.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text.strip())

            text = "\n\n".join(text_parts)
            metadata["paragraphs"] = len(doc.paragraphs)

        elif ext == "pptx":
            prs = Presentation(file)
            text_parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_parts.append(shape.text)
            text = "\n\n".join(text_parts)
            metadata["slides"] = len(prs.slides)

        elif ext in ["xlsx", "csv"]:
            text_parts = []
            if ext == "xlsx":
                xls = pd.ExcelFile(file)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    text_parts.append(f"Sheet: {sheet_name}\n{df.to_string(index=False)}")
            else:  # csv
                df = pd.read_csv(file)
                text_parts.append(df.to_string(index=False))
            text = "\n\n".join(text_parts)

        elif ext == "txt":
            text = file.read().decode("utf-8")

        elif ext in ["jpg", "jpeg", "png"]:
            image = Image.open(io.BytesIO(file.read()))
            text = pytesseract.image_to_string(image)
            metadata["ocr"] = True

        else:
            return "", metadata

        return text.strip(), metadata

    except Exception as e:
        return f"Error processing {file.name}: {str(e)}", metadata