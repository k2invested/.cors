#!/usr/bin/env python3
"""Canonical registry for the hash primitive tool family."""

from __future__ import annotations

HASH_CORE_TOOLS = (
    "tools/hash_resolve.py",
    "tools/hash_manifest.py",
)

HASH_MANIFEST_ROUTES = {
    ".st": "tools/st_builder.py",
    ".json": "tools/json_patch.py",
    ".docx": "tools/hash/doc_edit.py",
    ".pdf": "tools/hash/pdf_fill.py",
    ".pptx": "tools/hash/office_manifest.py",
    ".xlsx": "tools/hash/office_manifest.py",
}

HASH_RESOLVE_ROUTES = {
    ".docx": "tools/hash/doc_read.py",
    ".pdf": "tools/hash/pdf_read.py",
    ".pptx": "tools/hash/document_extract_marker.py",
    ".xlsx": "tools/hash/document_extract_marker.py",
    ".html": "tools/hash/document_extract_marker.py",
    ".epub": "tools/hash/document_extract_marker.py",
    ".png": "tools/hash/document_extract_marker.py",
    ".jpg": "tools/hash/document_extract_marker.py",
    ".jpeg": "tools/hash/document_extract_marker.py",
    ".webp": "tools/hash/document_extract_marker.py",
    ".gif": "tools/hash/document_extract_marker.py",
}

HASH_SUPPORT_TOOLS = (
    "tools/hash/office_manifest.py",
    "tools/hash/doc_read.py",
    "tools/hash/pdf_read.py",
    "tools/hash/document_extract_marker.py",
    "tools/st_builder.py",
    "tools/json_patch.py",
    "tools/hash/doc_edit.py",
    "tools/hash/pdf_fill.py",
    "tools/hash/docx_unpack.py",
    "tools/hash/docx_pack.py",
    "tools/hash/pptx_add_slide.py",
    "tools/hash/pptx_clean.py",
)
