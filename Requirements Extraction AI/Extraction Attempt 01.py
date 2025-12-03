import os
import PyPDF2
from transformers import pipeline

def extract_pdf_metadata(pdf_path):
    """Extract metadata from a PDF file."""
    metadata_info = {}

    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        metadata = reader.metadata

        if metadata:
            for key, value in metadata.items():
                # metadata keys come like '/Title', '/Author'; strip the '/'
                clean_key = key.lstrip("/")
                metadata_info[clean_key] = str(value)
    
    return metadata_info

def extract_text_from_pdf(pdf_path):
    """Extract text from all pages of a PDF."""
    text = ""
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text

def chunk_text(text, max_chars=2000):
    """Split text into smaller chunks for summarization."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks

def summarize_pdf_text(text, summarizer):
    """Summarize text by stitching summaries of individual chunks."""
    chunks = chunk_text(text)
    summaries = []

    for chunk in chunks:
        if chunk.strip():
            result = summarizer(
                chunk, max_length=130, min_length=40, do_sample=False
            )
            summaries.append(result[0]["summary_text"])

    return "\n\n".join(summaries)

def summarize_pdfs_in_folder(folder_path="pdfs"):
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(folder_path, filename)
            print(f"\n===== Processing: {filename} =====")

            # --- Metadata ---
            metadata = extract_pdf_metadata(pdf_path)
            print("\n--- METADATA ---")
            if metadata:
                for key, value in metadata.items():
                    print(f"{key}: {value}")
            else:
                print("No metadata found.")

            # --- Extract main text ---
            text = extract_text_from_pdf(pdf_path)

            # --- Summarize ---
            print("\n--- SUMMARY ---")
            summary = summarize_pdf_text(text, summarizer)
            print(summary)

            print("\n==============================\n")

if __name__ == "__main__":
    summarize_pdfs_in_folder("pdfs")

