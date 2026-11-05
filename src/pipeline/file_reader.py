import glob
import hashlib
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class MarkdownSection:
    section_id: str
    heading: str
    heading_path: Tuple[str, ...]
    level: int
    text: str

    @property
    def display_path(self) -> str:
        return " > ".join(self.heading_path) or "Preamble"


@dataclass(frozen=True)
class SectionSelection:
    text: str
    section_ids: Tuple[str, ...]
    used_fallback: bool


_SECTION_ALIASES = {
    "parser": (
        "abstract", "introduction", "experimental", "methods", "materials and methods",
        "experiments", "results", "discussion", "conclusion", "catalytic tests", "catalytic activity",
        "results and discussion",
    ),
    "catalyst": (
        "catalyst", "preparation", "synthesis", "characterization", "materials and methods",
        "experimental", "methods",
    ),
    "conditions": (
        "reaction conditions", "catalytic tests", "catalytic experiments", "experimental",
        "methods", "results",
    ),
    "performance": (
        "results", "discussion", "conclusion", "catalytic tests", "catalytic activity",
        "performance", "evaluation",
    ),
    "metadata": ("abstract", "metadata", "front matter"),
}
_REFERENCE_HEADING = re.compile(
    r"\b(references?|bibliography|literature cited|works cited)\b"
)
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def index_markdown_sections(markdown: str) -> List[MarkdownSection]:
    """Split Markdown at headings while retaining each heading and its source text."""
    sections: List[MarkdownSection] = []
    heading_stack: List[Tuple[int, str]] = []
    current_heading = ""
    current_level = 0
    current_path: Tuple[str, ...] = ()
    current_lines: List[str] = []
    fence_char = ""
    fence_length = 0

    def add_section() -> None:
        if not current_lines:
            return
        section_id = f"section-{len(sections) + 1:03d}"
        sections.append(MarkdownSection(
            section_id=section_id,
            heading=current_heading,
            heading_path=current_path,
            level=current_level,
            text="".join(current_lines).strip(),
        ))

    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not fence_char:
                fence_char, fence_length = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char, fence_length = "", 0

        heading_match = None if fence_char else _HEADING.match(line)
        if heading_match:
            add_section()
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading))
            current_heading = heading
            current_level = level
            current_path = tuple(item[1] for item in heading_stack)
            current_lines = [line]
        else:
            current_lines.append(line)

    add_section()
    return sections


def select_sections(
    sections: Sequence[MarkdownSection],
    purpose: str,
    locator: str = "",
) -> SectionSelection:
    """Select task-relevant sections, falling back to all non-reference content."""
    aliases = _SECTION_ALIASES.get(purpose.lower(), ())
    eligible = [
        section for section in sections
        if not any(_REFERENCE_HEADING.search(heading) for heading in section.heading_path)
    ]
    normalized_aliases = tuple(_normalize_text(alias) for alias in aliases)
    matched = [
        section for section in eligible
        if (
            (purpose.lower() == "metadata" and section.section_id == "section-001")
            or any(alias in _normalize_text(section.display_path) for alias in normalized_aliases)
        )
    ]
    supporting = [
        section for section in eligible
        if section.section_id == "section-001"
        and (section.heading or len(sections) > 1)
    ]
    locator_matches = [
        section for section in eligible
        if locator and _locator_matches(locator, section.text)
    ]
    selected_by_id = {section.section_id: section for section in supporting}
    selected_by_id.update({section.section_id: section for section in matched})
    selected_by_id.update({section.section_id: section for section in locator_matches})
    used_fallback = not (matched or locator_matches)
    if used_fallback:
        selected_by_id = {section.section_id: section for section in eligible}

    selected = list(selected_by_id.values())
    selected.sort(key=lambda section: (
        0 if section in locator_matches else 1,
        sections.index(section),
    ))
    evidence = "\n\n".join(
        f"[SECTION {section.section_id} | {section.display_path}]\n{section.text}"
        for section in selected
    )
    if used_fallback:
        evidence = (
            "[SECTION SELECTION FALLBACK: no configured heading matched; "
            "all non-reference sections are included.]\n\n"
            f"{evidence}"
        )
    return SectionSelection(
        text=evidence,
        section_ids=tuple(section.section_id for section in selected),
        used_fallback=used_fallback,
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold().replace("&", " and ")).strip()


def _locator_matches(locator: str, section_text: str) -> bool:
    locator_terms = re.findall(r"\b(?:table|row|test|figure)\s+\d+[a-z]?\b", locator, re.I)
    normalized_section = _normalize_text(section_text)
    return bool(locator_terms) and all(
        _normalize_text(term) in normalized_section for term in locator_terms
    )


def discover_papers(input_dir: str) -> List[Dict[str, str]]:
    """
    Glob for *.md files in the input_dir, sorted.
    For each, extract identifier, title, file_path, and hash.
    """
    pattern = os.path.join(input_dir, "**/*.md")
    files = sorted(glob.glob(pattern, recursive=True))
    
    papers = []
    for file_path in files:
        filename = os.path.basename(file_path)
        identifier = os.path.splitext(filename)[0]
        
        title = identifier
        content = read_paper(file_path)
        
        # Extract title from first `# ` header
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
                
        # Compute SHA-256 hash (first 16 hex characters)
        file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
        
        papers.append({
            "identifier": identifier,
            "title": title,
            "file_path": file_path,
            "file_hash": file_hash
        })
        
    return papers

def read_paper(file_path: str) -> str:
    """Read and return markdown content."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
