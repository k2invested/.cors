"""Stateless step-note generation for artifact/entity observations.

This module is intentionally narrow in ownership, but not in note quality:

- input: one local resolved evidence pack for the current gap
- output: a structured StepNote, or None on failure

It is designed to enrich observation steps without changing the main
reasoning loop. Callers should always fall back to derived notes when
generation fails or is disabled.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from step import RelationNote, StepNote


DEFAULT_NOTE_MODEL = os.environ.get("NOTE_MODEL", "gpt-5.4-mini")
ENABLE_STATELESS_NOTES = os.environ.get("ENABLE_STATELESS_NOTES", "1").strip().lower() not in {"0", "false", "no"}


def build_note_context(*, gap_desc: str, resolved_data: str, step_refs: list[str], content_refs: list[str]) -> str:
    return (
        "Write a rich structured note for a single observation step.\n"
        "The note should be comprehensive enough that a later reasoning step can read this note and understand what the artifact or entity is, what it contains, what matters in it, and how it compares to directly referenced context without reopening the raw source unless necessary.\n"
        "The note must be grounded only in the provided resolved evidence.\n"
        "You may make careful comparative inferences only when they are directly supported by the resolved evidence and cited refs.\n"
        "When multiple content refs are present, compare them explicitly and use `deltas`, `drift`, and `relations` to explain the semantic differences, agreements, dependencies, and tensions between them.\n"
        "Summarize the artifact or entity itself, not just the workflow step around it.\n"
        "Do not propose edits unless the evidence directly supports them, but do surface precise mutation implications when the evidence supports a concrete follow-on change, clarification, or preservation constraint.\n"
        "Use `salient_observations` for the most important contents and claims inside the artifact.\n"
        "Use `material_points` for the details a later model would need in order to reason about this artifact without rereading the whole resolved block.\n"
        "Use `deltas` for changes in emphasis, scope, implementation detail, or wording between referenced artifacts.\n"
        "Use `drift` for mismatches, incompleteness, partial implementation, ambiguity, or places where one artifact is more or less specific than another in a way that may matter later.\n"
        "Use `relations` liberally when the evidence supports clear links such as supports, conflicts, depends_on, updates, aliases, or references.\n"
        "Use `open_questions` only for real unresolved issues that remain after reading the evidence, not generic future work.\n"
        "Return JSON only with this shape:\n"
        '{'
        '"summary":"...",'
        '"salient_observations":["..."],'
        '"material_points":["..."],'
        '"deltas":["..."],'
        '"relations":[{"type":"supports|conflicts|depends_on|updates|aliases|references","from_ref":"...","to_ref":"...","note":"..."}],'
        '"drift":["..."],'
        '"mutation_implications":["..."],'
        '"open_questions":["..."]'
        '}\n\n'
        f"Gap description:\n{gap_desc}\n\n"
        f"Step refs:\n{step_refs}\n\n"
        f"Content refs:\n{content_refs}\n\n"
        f"Resolved evidence:\n{resolved_data}"
    )


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    if not isinstance(raw, str):
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    try:
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fence_match:
        try:
            data = json.loads(fence_match.group(1))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(candidate[start:end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def parse_step_note(raw: str) -> StepNote | None:
    data = _extract_json_object(raw)
    if not isinstance(data, dict):
        return None
    return StepNote(
        summary=str(data.get("summary", "")).strip(),
        salient_observations=_coerce_string_list(data.get("salient_observations")),
        material_points=_coerce_string_list(data.get("material_points")),
        deltas=_coerce_string_list(data.get("deltas")),
        relations=_coerce_relations(data.get("relations")),
        drift=_coerce_string_list(data.get("drift")),
        mutation_implications=_coerce_string_list(data.get("mutation_implications")),
        open_questions=_coerce_string_list(data.get("open_questions")),
    )


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = " ".join(item.split()).strip()
        if stripped:
            result.append(stripped)
    return result


def _coerce_relations(value: Any) -> list[RelationNote]:
    if not isinstance(value, list):
        return []
    result: list[RelationNote] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        type_ = str(item.get("type", "")).strip()
        from_ref = str(item.get("from_ref", "")).strip()
        to_ref = str(item.get("to_ref", "")).strip()
        note = str(item.get("note", "")).strip()
        if not type_ or not from_ref or not to_ref:
            continue
        result.append(RelationNote(type=type_, from_ref=from_ref, to_ref=to_ref, note=note))
    return result


def generate_step_note(*, gap_desc: str, resolved_data: str, step_refs: list[str], content_refs: list[str],
                       model: str | None = None) -> StepNote | None:
    if not ENABLE_STATELESS_NOTES:
        return None
    if not isinstance(resolved_data, str) or not resolved_data.strip():
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    client = OpenAI(api_key=api_key)
    prompt = build_note_context(
        gap_desc=gap_desc,
        resolved_data=resolved_data,
        step_refs=step_refs,
        content_refs=content_refs,
    )
    try:
        response = client.chat.completions.create(
            model=model or DEFAULT_NOTE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write rich evidence-grounded semantic notes for a runtime.\n"
                        "Your notes should preserve enough artifact detail and comparative analysis that a later reasoning step can rely on the note as a semantic substitute for reopening the raw resolved source.\n"
                        "When multiple artifacts or refs are present, compare them explicitly and capture the meaningful semantic differences.\n"
                        "Return strict JSON only.\n"
                        "Never include markdown fences unless unavoidable."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
    except Exception:
        return None

    raw = response.choices[0].message.content if response.choices else None
    return parse_step_note(raw or "")
