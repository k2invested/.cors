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
    ".docx": "tools/doc_edit.py",
    ".pdf": "tools/pdf_fill.py",
    ".pptx": "tools/office_manifest.py",
    ".xlsx": "tools/office_manifest.py",
}

HASH_RESOLVE_ROUTES = {
    ".docx": "tools/doc_read.py",
    ".pdf": "tools/pdf_read.py",
    ".pptx": "tools/document_extract_marker.py",
    ".xlsx": "tools/document_extract_marker.py",
    ".html": "tools/document_extract_marker.py",
    ".epub": "tools/document_extract_marker.py",
    ".png": "tools/document_extract_marker.py",
    ".jpg": "tools/document_extract_marker.py",
    ".jpeg": "tools/document_extract_marker.py",
    ".webp": "tools/document_extract_marker.py",
    ".gif": "tools/document_extract_marker.py",
}

HASH_SUPPORT_TOOLS = (
    "tools/office_manifest.py",
    "tools/doc_read.py",
    "tools/pdf_read.py",
    "tools/document_extract_marker.py",
    "tools/st_builder.py",
    "tools/json_patch.py",
    "tools/doc_edit.py",
    "tools/pdf_fill.py",
    "tools/docx_unpack.py",
    "tools/docx_pack.py",
    "tools/pptx_add_slide.py",
    "tools/pptx_clean.py",
)
