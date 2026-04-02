"""Generated-section merge model: markers, insertion, and replacement."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, List

MARKER_BEGIN = re.compile(
    r"<!--\s*BEGIN GENERATED:\s*(?P<section_id>\S+)"
    r"(?:\s+source=(?P<source>\S+))?"
    r"(?:\s+generated_at=(?P<generated_at>\S+))?"
    r"(?:\s+confidence=(?P<confidence>[\d.]+))?"
    r"(?:\s+edit_policy=(?P<edit_policy>\S+))?"
    r"\s*-->"
)
MARKER_END = re.compile(
    r"<!--\s*END GENERATED:\s*(?P<section_id>\S+)\s*-->"
)


class GeneratedSection(NamedTuple):
    section_id: str
    source: str
    generated_at: str
    confidence: float
    edit_policy: str
    content: str
    start_line: int
    end_line: int


def make_begin_marker(
    section_id: str,
    source: str = "",
    confidence: float = 0.0,
    edit_policy: str = "preserve-manual",
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return (
        f"<!-- BEGIN GENERATED: {section_id} "
        f"source={source} "
        f"generated_at={ts} "
        f"confidence={confidence:.2f} "
        f"edit_policy={edit_policy} -->"
    )


def make_end_marker(section_id: str) -> str:
    return f"<!-- END GENERATED: {section_id} -->"


def make_generated_block(
    section_id: str,
    content: str,
    source: str = "",
    confidence: float = 0.0,
    edit_policy: str = "preserve-manual",
) -> str:
    begin = make_begin_marker(section_id, source, confidence, edit_policy)
    end = make_end_marker(section_id)
    return f"{begin}\n{content}\n{end}"


def parse_generated_sections(text: str) -> list[GeneratedSection]:
    """Extract all generated sections from document text.

    Skips lines inside code fences (``` blocks) to avoid false-positive
    marker matches in documentation examples.
    """
    lines = text.split("\n")
    sections = []
    i = 0
    in_code_fence = False
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            in_code_fence = not in_code_fence
            i += 1
            continue
        if in_code_fence:
            i += 1
            continue
        m = MARKER_BEGIN.search(lines[i])
        if m:
            start_line = i
            section_id = m.group("section_id")
            source = m.group("source") or ""
            generated_at = m.group("generated_at") or ""
            confidence = float(m.group("confidence") or "0.0")
            edit_policy = m.group("edit_policy") or "preserve-manual"
            content_lines = []
            i += 1
            while i < len(lines):
                end_m = MARKER_END.search(lines[i])
                if end_m and end_m.group("section_id") == section_id:
                    sections.append(GeneratedSection(
                        section_id=section_id,
                        source=source,
                        generated_at=generated_at,
                        confidence=confidence,
                        edit_policy=edit_policy,
                        content="\n".join(content_lines),
                        start_line=start_line,
                        end_line=i,
                    ))
                    break
                content_lines.append(lines[i])
                i += 1
        i += 1
    return sections


def replace_generated_section(text: str, section_id: str, new_content: str, source: str = "", confidence: float = 0.0) -> str:
    """Replace a generated section's content, preserving manual content outside markers."""
    sections = parse_generated_sections(text)
    target = None
    for s in sections:
        if s.section_id == section_id:
            target = s
            break

    if target is None:
        return text

    lines = text.split("\n")
    new_block = make_generated_block(section_id, new_content, source, confidence)
    new_lines = lines[:target.start_line] + new_block.split("\n") + lines[target.end_line + 1:]
    return "\n".join(new_lines)


def insert_generated_section_at_end(text: str, section_id: str, content: str, source: str = "", confidence: float = 0.0) -> str:
    """Append a generated section at end of document."""
    block = make_generated_block(section_id, content, source, confidence)
    if text.endswith("\n"):
        return text + "\n" + block + "\n"
    return text + "\n\n" + block + "\n"


def has_section(text: str, section_id: str) -> bool:
    for s in parse_generated_sections(text):
        if s.section_id == section_id:
            return True
    return False


AUTO_APPLY_MIN_CONFIDENCE = 0.85


def can_auto_apply(
    confidence: float,
    is_generated_only: bool,
    has_duplicate_source: bool,
    touches_high_risk: bool,
    has_blocking_finding: bool,
) -> bool:
    """Check auto-apply policy."""
    return (
        confidence >= AUTO_APPLY_MIN_CONFIDENCE
        and is_generated_only
        and not has_duplicate_source
        and not touches_high_risk
        and not has_blocking_finding
    )
