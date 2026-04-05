#!/usr/bin/env python3
"""docx_unpack — Unpack Office files (DOCX, PPTX, XLSX) for editing.

Extracts the ZIP archive, pretty-prints XML files, and optionally:
- Merges adjacent runs with identical formatting (DOCX only)
- Simplifies adjacent tracked changes from same author (DOCX only)

Input JSON: {"path": "<relative path to office file>", "output": "<relative output dir>",
             "merge_runs": true, "simplify_redlines": true}
Env: WORKSPACE — sandbox root.

Can also be used via CLI:
    python docx_unpack.py <office_file> <output_dir> [--merge-runs true|false] [--simplify-redlines true|false]
"""
import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

import defusedxml.minidom

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.hash.office_helpers.merge_runs import merge_runs as do_merge_runs
from tools.hash.office_helpers.simplify_redlines import simplify_redlines as do_simplify_redlines

SMART_QUOTE_REPLACEMENTS = {
    "\u201c": "&#x201C;",
    "\u201d": "&#x201D;",
    "\u2018": "&#x2018;",
    "\u2019": "&#x2019;",
}


def unpack(
    input_file: str,
    output_directory: str,
    merge_runs: bool = True,
    simplify_redlines: bool = True,
) -> tuple[None, str]:
    input_path = Path(input_file)
    output_path = Path(output_directory)
    suffix = input_path.suffix.lower()

    if not input_path.exists():
        return None, f"Error: {input_file} does not exist"

    if suffix not in {".docx", ".pptx", ".xlsx"}:
        return None, f"Error: {input_file} must be a .docx, .pptx, or .xlsx file"

    try:
        output_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(output_path)

        xml_files = list(output_path.rglob("*.xml")) + list(output_path.rglob("*.rels"))
        for xml_file in xml_files:
            _pretty_print_xml(xml_file)

        message = f"Unpacked {input_file} ({len(xml_files)} XML files)"

        if suffix == ".docx":
            if simplify_redlines:
                simplify_count, _ = do_simplify_redlines(str(output_path))
                message += f", simplified {simplify_count} tracked changes"

            if merge_runs:
                merge_count, _ = do_merge_runs(str(output_path))
                message += f", merged {merge_count} runs"

        for xml_file in xml_files:
            _escape_smart_quotes(xml_file)

        return None, message

    except zipfile.BadZipFile:
        return None, f"Error: {input_file} is not a valid Office file"
    except Exception as e:
        return None, f"Error unpacking: {e}"


def _pretty_print_xml(xml_file: Path) -> None:
    try:
        content = xml_file.read_text(encoding="utf-8")
        dom = defusedxml.minidom.parseString(content)
        xml_file.write_bytes(dom.toprettyxml(indent="  ", encoding="utf-8"))
    except Exception:
        pass


def _escape_smart_quotes(xml_file: Path) -> None:
    try:
        content = xml_file.read_text(encoding="utf-8")
        for char, entity in SMART_QUOTE_REPLACEMENTS.items():
            content = content.replace(char, entity)
        xml_file.write_text(content, encoding="utf-8")
    except Exception:
        pass


def main_stdin():
    """JSON stdin interface for Step Kernel tool system."""
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    file_path = params.get("path", "")
    output_dir = params.get("output", "")
    merge = params.get("merge_runs", True)
    simplify = params.get("simplify_redlines", True)

    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)
    if not output_dir:
        print("Error: missing 'output' parameter", file=sys.stderr)
        sys.exit(1)

    # Resolve within workspace sandbox
    from tools.scan_tree import sandbox_path
    try:
        resolved_input = sandbox_path(file_path, workspace)
        resolved_output = sandbox_path(output_dir, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    _, message = unpack(resolved_input, resolved_output, merge_runs=merge, simplify_redlines=simplify)
    print(message)
    if "Error" in message:
        sys.exit(1)


def main_cli():
    """CLI interface for direct usage."""
    parser = argparse.ArgumentParser(
        description="Unpack an Office file (DOCX, PPTX, XLSX) for editing"
    )
    parser.add_argument("input_file", help="Office file to unpack")
    parser.add_argument("output_directory", help="Output directory")
    parser.add_argument(
        "--merge-runs",
        type=lambda x: x.lower() == "true",
        default=True,
        metavar="true|false",
        help="Merge adjacent runs with identical formatting (DOCX only, default: true)",
    )
    parser.add_argument(
        "--simplify-redlines",
        type=lambda x: x.lower() == "true",
        default=True,
        metavar="true|false",
        help="Merge adjacent tracked changes from same author (DOCX only, default: true)",
    )
    args = parser.parse_args()

    _, message = unpack(
        args.input_file,
        args.output_directory,
        merge_runs=args.merge_runs,
        simplify_redlines=args.simplify_redlines,
    )
    print(message)
    if "Error" in message:
        sys.exit(1)


if __name__ == "__main__":
    # If stdin has data, use JSON stdin interface; otherwise use CLI
    if not sys.stdin.isatty():
        main_stdin()
    else:
        main_cli()
