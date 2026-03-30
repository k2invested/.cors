#!/usr/bin/env python3
"""pdf_check_fields — Check if a PDF has fillable form fields.

Input JSON: {"path": "<relative path to PDF file>"}
Env: WORKSPACE — sandbox root.

Returns whether the PDF has fillable form fields.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path


def check_fields(filepath):
    """Check if a PDF has fillable form fields and return field info."""
    from pypdf import PdfReader

    reader = PdfReader(filepath)
    fields = reader.get_fields()

    if not fields:
        return "This PDF does not have fillable form fields."

    # Count field types
    type_counts = {}
    for field_name, field in fields.items():
        ft = field.get('/FT', 'unknown')
        type_map = {'/Tx': 'text', '/Btn': 'checkbox/radio', '/Ch': 'choice'}
        ftype = type_map.get(ft, f'unknown ({ft})')
        type_counts[ftype] = type_counts.get(ftype, 0) + 1

    summary_parts = [f"This PDF has {len(fields)} fillable form fields:"]
    for ftype, count in sorted(type_counts.items()):
        summary_parts.append(f"  {ftype}: {count}")

    return "\n".join(summary_parts)


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

    try:
        result = check_fields(resolved)
        print(result)
    except Exception as e:
        print(f"Error checking PDF fields: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
