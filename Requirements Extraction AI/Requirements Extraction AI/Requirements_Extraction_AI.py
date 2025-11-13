import os
import pdfplumber
import docx
from PIL import Image
import pytesseract

def extract_from_pdf(file_path):
    """Extract text from PDF file."""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_from_docx(file_path):
    """Extract text from Word (.docx) file."""
    doc = docx.Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def extract_from_image(file_path):
    """Extract text from image using OCR."""
    img = Image.open(file_path)
    text = pytesseract.image_to_string(img)
    return text

def extract_text(file_path):
    """Main function to extract text from different document types."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        return extract_from_pdf(file_path)
    elif ext == ".docx":
        return extract_from_docx(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        return extract_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

if __name__ == "__main__":
    file_path = input("Enter the path to your document: ").strip()
    try:
        extracted_text = extract_text(file_path)
        print("\n===== Extracted Text =====\n")
        print(extracted_text[:2000])  # Print first 2000 characters for preview
    except Exception as e:
        print(f"Error: {e}")

