#!/usr/bin/env python3
"""json_patch — surgical in-place JSON mutation.

Input JSON: {
  "path": "<relative file path>",
  "op": "append_array | set_key | delete_key",
  "pointer": "<JSON Pointer e.g. '' for root, '/0/key' for nested>",
  "value": <any JSON value, required for append_array and set_key>
}
Env: WORKSPACE — sandbox root.

Operations:
  append_array  — append value to the array at pointer (root array if pointer is '' or '/')
  set_key       — set key at the object addressed by pointer to value
  delete_key    — delete key at the object addressed by pointer (value unused)

JSON Pointer follows RFC 6901: '' = root, '/0' = first element, '/key' = object key.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

MAX_FILE_SIZE = 500_000


def resolve_pointer(doc, pointer):
    """Walk a JSON Pointer string and return (parent, key, node) at that location.
    pointer='' or pointer='/' both address the root.
    pointer='/-' addresses end-of-array (for append).
    Returns (None, None, doc) for the root itself.
    Raises KeyError/IndexError/ValueError on bad pointer."""
    if pointer in ("", "/"):
        return None, None, doc

    # Handle /-  (RFC 6901 "append to array" — special case)
    if pointer == "/-":
        if isinstance(doc, list):
            return None, "-", doc
        raise ValueError("'/-' pointer requires root to be an array")

    # Strip leading slash, split on '/'
    parts = pointer.lstrip("/").split("/")
    # Unescape RFC 6901 tokens (~1 -> '/', ~0 -> '~')
    parts = [p.replace("~1", "/").replace("~0", "~") for p in parts]

    # Check if last segment is '-' (append target within nested path)
    append_mode = parts[-1] == "-"

    node = doc
    parent = None
    key = None
    for i, part in enumerate(parts):
        parent = node
        key = part
        # Last segment '-' means "end of array" — don't descend
        if append_mode and i == len(parts) - 1:
            if not isinstance(node, list):
                raise ValueError(f"'-' pointer segment requires array, got {type(node).__name__}")
            break
        if isinstance(node, list):
            try:
                idx = int(part)
            except ValueError:
                raise ValueError(f"Expected integer index for list, got '{part}'")
            node = node[idx]
        elif isinstance(node, dict):
            node = node[part]
        else:
            raise ValueError(f"Cannot descend into {type(node).__name__} with key '{part}'")
    return parent, key, node


def apply_op(doc, op, pointer, value):
    """Apply op to doc in-place. Returns modified doc."""
    parent, key, node = resolve_pointer(doc, pointer)

    if op == "append_array":
        if not isinstance(node, list):
            raise ValueError(
                f"append_array requires an array at pointer '{pointer}', "
                f"got {type(node).__name__}"
            )
        node.append(value)

    elif op == "set_key":
        if isinstance(node, dict):
            # Standard: pointer targets an object, value is {"key": val}
            if not isinstance(value, dict) or len(value) != 1:
                raise ValueError(
                    "set_key value must be a single-key dict: {\"<key>\": <val>}"
                )
            k, v = next(iter(value.items()))
            node[k] = v
        elif parent is not None:
            # Pointer targets a scalar — update the key on the parent directly
            if isinstance(parent, dict):
                parent[key] = value
            elif isinstance(parent, list):
                parent[int(key)] = value
            else:
                raise ValueError(
                    f"set_key: cannot update parent of type {type(parent).__name__}"
                )
        else:
            raise ValueError(
                f"set_key requires an object at pointer '{pointer}', "
                f"got {type(node).__name__}"
            )

    elif op == "delete_key":
        if not isinstance(node, dict):
            raise ValueError(
                f"delete_key requires an object at pointer '{pointer}', "
                f"got {type(node).__name__}"
            )
        if not isinstance(value, str):
            raise ValueError("delete_key value must be the key name (string)")
        if value not in node:
            raise KeyError(f"Key '{value}' not found at pointer '{pointer}'")
        del node[value]

    else:
        raise ValueError(f"Unknown op '{op}'. Must be: append_array, set_key, delete_key")

    return doc


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    file_path = params.get("path", "")
    op = params.get("op", "")
    pointer = params.get("pointer", "")
    value = params.get("value")  # None is valid sentinel — checked per-op

    # Validate required params
    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)
    if not op:
        print("Error: missing 'op' parameter", file=sys.stderr)
        sys.exit(1)
    if op in ("append_array", "set_key") and value is None:
        print(f"Error: 'value' is required for op '{op}'", file=sys.stderr)
        sys.exit(1)
    if op == "delete_key" and value is None:
        print("Error: 'value' (key name string) is required for op 'delete_key'", file=sys.stderr)
        sys.exit(1)

    # Resolve and guard path
    try:
        resolved = sandbox_path(file_path, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(resolved):
        print(f"Error: '{file_path}' is not a file", file=sys.stderr)
        sys.exit(1)

    if os.path.getsize(resolved) > MAX_FILE_SIZE:
        print(f"Error: file exceeds {MAX_FILE_SIZE} byte limit", file=sys.stderr)
        sys.exit(1)

    # Read
    try:
        with open(resolved) as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except (UnicodeDecodeError, PermissionError) as e:
        print(f"Error: cannot read '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Apply mutation
    try:
        doc = apply_op(doc, op, pointer, value)
    except (ValueError, KeyError, IndexError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Write back (atomic via temp file)
    tmp_path = resolved + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
        os.replace(tmp_path, resolved)
    except Exception as e:
        print(f"Error: failed to write '{file_path}': {e}", file=sys.stderr)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        sys.exit(1)

    # Report result
    if op == "append_array":
        summary = f"appended element to array at pointer '{pointer}' — array now has {len(doc) if pointer in ('', '/') else '?'} elements"
    elif op == "set_key":
        k = next(iter(value.items()))[0] if isinstance(value, dict) else str(value)
        summary = f"set key '{k}' at pointer '{pointer}'"
    else:
        summary = f"deleted key '{value}' at pointer '{pointer}'"

    print(f"ok: {file_path} — {op} applied — {summary}")


if __name__ == "__main__":
    main()
