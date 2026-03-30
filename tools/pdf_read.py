#!/usr/bin/env python3
"""pdf_read — extract text content from PDF files.

Input JSON: {"path": "<relative path to PDF file>"}
Env: WORKSPACE — sandbox root.

Reads .pdf files using pdfplumber (with pypdf fallback), returns text with structure.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

MAX_OUTPUT = 32_000


def read_pdf(filepath):
    """Extract text from a PDF file, preserving page structure."""
    sections = []

    # Try pdfplumber first (better table/layout extraction)
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                page_parts = []

                # Extract text
                text = page.extract_text()
                if text and text.strip():
                    page_parts.append(text.strip())

                # Extract tables
                tables = page.extract_tables()
                for t_idx, table in enumerate(tables):
                    if not table:
                        continue
                    rows = []
                    for row in table:
                        cells = [str(cell).strip() if cell else "" for cell in row]
                        rows.append(" | ".join(cells))
                    if rows:
                        page_parts.append(f"[Table {t_idx + 1}]\n" + "\n".join(rows))

                if page_parts:
                    sections.append(f"## Page {i + 1}\n" + "\n\n".join(page_parts))

        if sections:
            return "\n\n".join(sections)
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback to pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(filepath)

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                sections.append(f"## Page {i + 1}\n" + text.strip())

        if sections:
            return "\n\n".join(sections)
    except ImportError:
        pass
    except Exception as e:
        print(f"Error reading PDF with pypdf: {e}", file=sys.stderr)
        sys.exit(1)

    # If both fail
    if not sections:
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            return f"(PDF has {len(reader.pages)} pages but no extractable text)"
        except Exception:
            return "(PDF could not be read — install pdfplumber or pypdf)"

    return "\n\n".join(sections)


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    file_path = params.get("path", "")
    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)

    try:
        resolved = sandbox_path(file_path, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(resolved):
        print(f"Error: '{file_path}' is not a file", file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(resolved)[1].lower()

    if ext == ".pdf":
        try:
            content = read_pdf(resolved)
        except Exception as e:
            print(f"Error reading PDF: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Error: unsupported format '{ext}'. Supported: .pdf", file=sys.stderr)
        sys.exit(1)

    if not content.strip():
        print(f"(document is empty: {file_path})")
    else:
        # Output with line numbers (matches scan_tree format for batch compatibility)
        lines = content.split("\n")
        numbered = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        output = "\n".join(numbered)
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + f"\n... (truncated, {len(lines)} lines total)"
        print(output)


if __name__ == "__main__":
    main()
