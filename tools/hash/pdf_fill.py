#!/usr/bin/env python3
"""pdf_fill — Fill fillable form fields in a PDF.

Input JSON: {"path": "<relative path to input PDF>",
             "output": "<relative path to output PDF>",
             "fields": [{"field_id": "name", "page": 1, "value": "John"}]}
Env: WORKSPACE — sandbox root.

Reads the PDF, extracts field info, validates the provided values,
and writes a new PDF with fields filled.
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.scan_tree import sandbox_path


def get_full_annotation_field_id(annotation):
    """Get the full dotted field ID from a PDF annotation."""
    components = []
    while annotation:
        field_name = annotation.get('/T')
        if field_name:
            components.append(field_name)
        annotation = annotation.get('/Parent')
    return ".".join(reversed(components)) if components else None


def get_field_info(reader):
    """Extract field info from a PdfReader, returns list of field dicts."""
    from pypdf import PdfReader

    fields = reader.get_fields()
    if not fields:
        return []

    field_info_by_id = {}
    possible_radio_names = set()

    for field_id, field in fields.items():
        if field.get("/Kids"):
            if field.get("/FT") == "/Btn":
                possible_radio_names.add(field_id)
            continue

        field_dict = {"field_id": field_id}
        ft = field.get('/FT')
        if ft == "/Tx":
            field_dict["type"] = "text"
        elif ft == "/Btn":
            field_dict["type"] = "checkbox"
            states = field.get("/_States_", [])
            if len(states) == 2:
                if "/Off" in states:
                    field_dict["checked_value"] = states[0] if states[0] != "/Off" else states[1]
                    field_dict["unchecked_value"] = "/Off"
                else:
                    field_dict["checked_value"] = states[0]
                    field_dict["unchecked_value"] = states[1]
        elif ft == "/Ch":
            field_dict["type"] = "choice"
            states = field.get("/_States_", [])
            field_dict["choice_options"] = [{"value": s[0], "text": s[1]} for s in states]
        else:
            field_dict["type"] = f"unknown ({ft})"

        field_info_by_id[field_id] = field_dict

    radio_fields_by_id = {}

    for page_index, page in enumerate(reader.pages):
        annotations = page.get('/Annots', [])
        for ann in annotations:
            field_id = get_full_annotation_field_id(ann)
            if field_id in field_info_by_id:
                field_info_by_id[field_id]["page"] = page_index + 1
            elif field_id in possible_radio_names:
                try:
                    on_values = [v for v in ann["/AP"]["/N"] if v != "/Off"]
                except KeyError:
                    continue
                if len(on_values) == 1:
                    if field_id not in radio_fields_by_id:
                        radio_fields_by_id[field_id] = {
                            "field_id": field_id,
                            "type": "radio_group",
                            "page": page_index + 1,
                            "radio_options": [],
                        }
                    radio_fields_by_id[field_id]["radio_options"].append({
                        "value": on_values[0],
                    })

    fields_with_location = [f for f in field_info_by_id.values() if "page" in f]
    return fields_with_location + list(radio_fields_by_id.values())


def validation_error_for_field_value(field_info, field_value):
    """Validate a field value against its type constraints."""
    field_type = field_info["type"]
    field_id = field_info["field_id"]
    if field_type == "checkbox":
        checked_val = field_info.get("checked_value")
        unchecked_val = field_info.get("unchecked_value")
        if checked_val and field_value != checked_val and field_value != unchecked_val:
            return f'Invalid value "{field_value}" for checkbox "{field_id}". Use "{checked_val}" or "{unchecked_val}"'
    elif field_type == "radio_group":
        option_values = [opt["value"] for opt in field_info.get("radio_options", [])]
        if field_value not in option_values:
            return f'Invalid value "{field_value}" for radio "{field_id}". Valid: {option_values}'
    elif field_type == "choice":
        choice_values = [opt["value"] for opt in field_info.get("choice_options", [])]
        if field_value not in choice_values:
            return f'Invalid value "{field_value}" for choice "{field_id}". Valid: {choice_values}'
    return None


def fill_pdf_fields(input_path, output_path, field_values):
    """Fill PDF form fields and write to output.

    field_values: list of {"field_id": str, "page": int, "value": str}
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_path)
    field_info = get_field_info(reader)

    if not field_info:
        return "Error: PDF has no fillable form fields"

    fields_by_ids = {f["field_id"]: f for f in field_info}
    errors = []

    for field in field_values:
        existing = fields_by_ids.get(field["field_id"])
        if not existing:
            errors.append(f"'{field['field_id']}' is not a valid field ID")
        elif field.get("page") and field["page"] != existing.get("page"):
            errors.append(f"Wrong page for '{field['field_id']}' (got {field['page']}, expected {existing.get('page')})")
        elif "value" in field:
            err = validation_error_for_field_value(existing, field["value"])
            if err:
                errors.append(err)

    if errors:
        return "Errors:\n" + "\n".join(f"  - {e}" for e in errors)

    # Group by page
    fields_by_page = {}
    for field in field_values:
        if "value" in field:
            page = field.get("page", fields_by_ids[field["field_id"]].get("page", 1))
            if page not in fields_by_page:
                fields_by_page[page] = {}
            fields_by_page[page][field["field_id"]] = field["value"]

    # Apply monkeypatch for choice fields
    _monkeypatch_pypdf()

    writer = PdfWriter(clone_from=reader)
    for page, fv in fields_by_page.items():
        writer.update_page_form_field_values(writer.pages[page - 1], fv, auto_regenerate=False)

    writer.set_need_appearances_writer(True)

    with open(output_path, "wb") as f:
        writer.write(f)

    return f"Filled {sum(len(v) for v in fields_by_page.values())} fields, wrote to {output_path}"


def _monkeypatch_pypdf():
    """Workaround for pypdf bug with selection list fields."""
    try:
        from pypdf.generic import DictionaryObject
        from pypdf.constants import FieldDictionaryAttributes

        original = DictionaryObject.get_inherited

        def patched(self, key, default=None):
            result = original(self, key, default)
            if key == FieldDictionaryAttributes.Opt:
                if isinstance(result, list) and all(isinstance(v, list) and len(v) == 2 for v in result):
                    result = [r[0] for r in result]
            return result

        DictionaryObject.get_inherited = patched
    except (ImportError, AttributeError):
        pass


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    input_path = params.get("path", "")
    output_path = params.get("output", "")
    field_values = params.get("fields", [])

    if not input_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)
    if not output_path:
        print("Error: missing 'output' parameter", file=sys.stderr)
        sys.exit(1)
    if not field_values:
        print("Error: missing 'fields' parameter", file=sys.stderr)
        sys.exit(1)

    try:
        resolved_input = sandbox_path(input_path, workspace)
        resolved_output = sandbox_path(output_path, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(resolved_input):
        print(f"Error: '{input_path}' is not a file", file=sys.stderr)
        sys.exit(1)

    try:
        result = fill_pdf_fields(resolved_input, resolved_output, field_values)
        print(result)
        if result.startswith("Error"):
            sys.exit(1)
    except Exception as e:
        print(f"Error filling PDF: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
