from types import SimpleNamespace

from src.agents import extractor as extractor_module
from src.agents.extractor import Extractor
from src.pipeline.file_reader import index_markdown_sections, select_sections


def test_index_preserves_heading_paths_duplicate_names_and_code_blocks():
    markdown = """# Paper
Preamble text.
## Results
First result.
### Details
```markdown
# Not a heading
```
## Results
Second result.
"""

    sections = index_markdown_sections(markdown)

    assert [section.heading for section in sections] == ["Paper", "Results", "Details", "Results"]
    assert sections[2].heading_path == ("Paper", "Results", "Details")
    assert "# Not a heading" in sections[2].text
    assert sections[1].section_id != sections[3].section_id


def test_select_sections_prioritizes_locator_and_excludes_reference_subtree():
    markdown = """# Paper title
Abstract text.
## Introduction
Introduction-only text.
## Results
General results.
### Catalytic tests
Table 1
Header A | Header B
Row 1 | Other experiment
Row 2 | Target experiment
## References
Reference list.
### More sources
Nested reference text.
"""
    sections = index_markdown_sections(markdown)

    selection = select_sections(sections, "performance", "Table 1, Row 2")

    assert not selection.used_fallback
    assert "Row 2 | Target experiment" in selection.text
    assert "Header A | Header B" in selection.text
    assert "Introduction-only text" not in selection.text
    assert "Reference list" not in selection.text
    assert "Nested reference text" not in selection.text


def test_metadata_selection_uses_front_matter_without_results():
    sections = index_markdown_sections(
        "# Paper title\nDOI: 10.1234/example\n## Results\nResult data."
    )

    selection = select_sections(sections, "metadata")

    assert not selection.used_fallback
    assert "10.1234/example" in selection.text
    assert "Result data" not in selection.text


def test_unknown_headings_fall_back_to_non_reference_sections():
    sections = index_markdown_sections(
        "# Paper\nContent.\n## Unusual section\nUseful evidence.\n## References\nCitations."
    )

    selection = select_sections(sections, "performance")

    assert selection.used_fallback
    assert "Useful evidence" in selection.text
    assert "Citations" not in selection.text
    assert "SECTION SELECTION FALLBACK" in selection.text


def test_extractor_passes_selected_evidence_not_full_paper(monkeypatch, caplog):
    monkeypatch.setattr(extractor_module, "DEBUG_SECTION_CONTENT", True)
    caplog.set_level("INFO")
    paper = """# Paper title
## Introduction
INTRODUCTION_ONLY
## Experimental
METHODS_EVIDENCE
## Results
Table 1
Header | Value
Row 1 | TARGET_RESULT
## References
REFERENCE_ONLY
"""
    experiment = SimpleNamespace(
        experiment_number=1,
        brief_description="Target run",
        catalyst_name="Catalyst A",
        reactant="ethylene",
        main_temperature="80 C",
        main_pressure="30 atm",
        products_mentioned="product A",
        key_section="Table 1, Row 1",
        key_parameters="value=1",
    )

    class Parser:
        def __init__(self):
            self.input_text = None

        def parse(self, paper_content, paper_id):
            self.input_text = paper_content
            return SimpleNamespace(experiments=[experiment])

    class LLM:
        num_ctx = 32768

        def __init__(self):
            self.user_messages = []

        def extract(self, **kwargs):
            self.user_messages.append(kwargs["user_message"])
            return SimpleNamespace(model_dump=lambda: {})

    class Validator:
        def validate(self, extraction, sub_domain_results):
            return {"overall_confidence": 4}

    extractor = Extractor.__new__(Extractor)
    extractor.llm_client = LLM()
    extractor.config = None
    extractor.sub_domain_names = ["performance"]
    extractor.validator = Validator()
    extractor._load_prompt = lambda sub_domain: "prompt"
    extractor._get_model_class = lambda sub_domain: object
    parser = Parser()

    results = extractor.extract_paper(paper, 1, parser)

    assert len(results) == 1
    assert "INTRODUCTION_ONLY" in parser.input_text
    assert "METHODS_EVIDENCE" in parser.input_text
    assert "REFERENCE_ONLY" not in parser.input_text
    message = extractor.llm_client.user_messages[0]
    assert "TARGET_RESULT" in message
    assert "INTRODUCTION_ONLY" not in message
    assert "REFERENCE_ONLY" not in message
    assert "FULL PAPER TEXT" not in message
    assert "DEBUG section content | paper=1 | stage=parser" in caplog.text
    assert "DEBUG section content | paper=1 | experiment=1 | sub_domain=performance" in caplog.text
    assert "TARGET_RESULT" in caplog.text
