# Add this summarization above the batch_extract_metadata function

# ============================================================
#                    SIMPLE TEXT SUMMARIZER
# ============================================================

import math
from collections import Counter

def summarize_text(text: str, max_sentences: int = 3) -> str:
    """
    Produces a lightweight extractive summary of the text.
    No external libraries required.
    """

    # Clean text
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    lines = [l for l in lines if not is_classification_line(l)]
    cleaned_text = " ".join(lines)

    # Split into sentences (simple heuristic)
    sentences = re.split(r'(?<=[\.\!\?])\s+', cleaned_text)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]

    if not sentences:
        return ""

    # Tokenize words
    words = re.findall(r"\b[A-Za-z]{3,}\b", cleaned_text.lower())
    if not words:
        return ""

    # Word frequencies
    freq = Counter(words)
    max_freq = max(freq.values())
    for k in freq:
        freq[k] /= max_freq

    # Score each sentence by avg keyword weight
    sentence_scores = {}
    for s in sentences:
        s_words = re.findall(r"\b[A-Za-z]{3,}\b", s.lower())
        if not s_words:
            continue
        score = sum(freq.get(w, 0) for w in s_words) / len(s_words)
        sentence_scores[s] = score

    # Select top N sentences in original order
    ranked = sorted(sentence_scores, key=sentence_scores.get, reverse=True)
    summary_sentences = ranked[:max_sentences]

    # Preserve original order in the text
    summary_sentences = sorted(summary_sentences, key=lambda s: sentences.index(s))

    return " ".join(summary_sentences)

# MODIFY THE BATCH DRIVER TO SAVE A SUMMARY FILE (ADD THIS INSIDE BATCH_EXTRACT_METADATA)

        # --- Generate summary ---
        summary = summarize_text(text)

        summary_path = output_dir / (txt_file.stem + "_summary.txt")
        summary_path.write_text(summary, encoding="utf-8")
        print(f"Summary for {txt_file.name} -> {summary_path.name}")


#UPDATED FUNCTION SHOULD LOOK LIKE THIS:

def batch_extract_metadata(parsed_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for txt_file in parsed_dir.glob("*.txt"):
        text = txt_file.read_text(encoding="utf-8")

        # Extract metadata
        meta = extract_metadata_from_text(text, txt_file.name)

        # Write metadata JSON
        out_path = output_dir / (txt_file.stem + "_metadata.json")
        out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"Metadata for {txt_file.name} -> {out_path.name}")

        # --- Generate summary ---
        summary = summarize_text(text)
        summary_path = output_dir / (txt_file.stem + "_summary.txt")
        summary_path.write_text(summary, encoding="utf-8")
        print(f"Summary for {txt_file.name} -> {summary_path.name}")
