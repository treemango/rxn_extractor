import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def generate_models(domain: Dict[str, Any], output_path: str) -> None:
    """
    Generates Pydantic models based on the domain definition.

    Validation philosophy (lenient mode):
    - All domain fields are Optional with None defaults.
    - No min/max bound constraints on field values (handled separately by validator.py).
    - confidence_score is clamped to 1-5 via a validator instead of hard-failing.
    - source_quote has no min_length — empty or missing is fine.
    - ExperimentMetadata fields have defaults so missing keys don't crash parsing.
    """
    logger.info(f"Generating models at {output_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = [
        "from typing import Optional, List, Any",
        "from pydantic import BaseModel, Field, field_validator, model_validator",
        "from enum import Enum",
        "from datetime import datetime",
        "",
        ""
    ]

    sub_domain_classes = []

    for sub in domain.get('sub_domains', []):
        sub_name = "".join(x.title() for x in sub['name'].split('_'))
        class_name = f"{sub_name}Extraction"
        sub_domain_classes.append((sub['name'], class_name))

        # Enums
        for field in sub.get('fields', []):
            if field.get('type') == 'enum':
                enum_name = "".join(x.title() for x in field['name'].split('_')) + "Enum"
                lines.append(f"class {enum_name}(str, Enum):")
                for val in field.get('allowed_values', []):
                    var_name = val.upper().replace(' ', '_').replace('-', '_').replace('/', '_')
                    lines.append(f"    {var_name} = '{val}'")
                lines.append("")

        # Class definition — all fields Optional, no hard constraints
        lines.append(f"class {class_name}(BaseModel):")
        lines.append(f"    model_config = {{'extra': 'ignore'}}  # silently drop unknown keys from LLM")
        lines.append("")

        for field in sub.get('fields', []):
            f_name = field['name']
            f_type = field.get('type')

            if f_type == 'float':
                # No gt/ge/lt/le — accept whatever the LLM returns
                lines.append(f"    {f_name}_value: Optional[float] = Field(None)")
                lines.append(f"    {f_name}_unit: Optional[str] = Field(None)")
            elif f_type == 'range':
                lines.append(f"    {f_name}_min: Optional[float] = Field(None)")
                lines.append(f"    {f_name}_max: Optional[float] = Field(None)")
                lines.append(f"    {f_name}_unit: Optional[str] = Field(None)")
            elif f_type == 'enum':
                enum_name = "".join(x.title() for x in f_name.split('_')) + "Enum"
                # Accept enum or plain string — use Any to avoid strict enum failures
                lines.append(f"    {f_name}: Optional[Any] = Field(None)")
            elif f_type == 'string':
                lines.append(f"    {f_name}: Optional[str] = Field(None)")

        # Confidence: clamp to 1-5 instead of hard-failing on out-of-range values
        lines.extend([
            "",
            "    confidence_score: Optional[int] = Field(None)",
            "    source_quote: Optional[str] = Field(None)",
            "",
            "    @field_validator('confidence_score', mode='before')",
            "    @classmethod",
            "    def clamp_confidence(cls, v):",
            "        if v is None:",
            "            return 3  # default mid-range if missing",
            "        try:",
            "            return max(1, min(5, int(v)))",
            "        except (TypeError, ValueError):",
            "            return 3",
            "",
        ])

    # ── Parser Output Models ─────────────────────────────────────────────────
    lines.extend([
        "class ExperimentMetadata(BaseModel):",
        "    model_config = {'extra': 'ignore'}",
        "    experiment_number: int = Field(default=1)",
        "    brief_description: str = Field(default='')",
        "    key_parameters: str = Field(default='')",
        "    confidence: Optional[int] = Field(None)",
        "",
        "    @field_validator('confidence', mode='before')",
        "    @classmethod",
        "    def clamp_exp_confidence(cls, v):",
        "        if v is None:",
        "            return 3",
        "        try:",
        "            return max(1, min(5, int(v)))",
        "        except (TypeError, ValueError):",
        "            return 3",
        "",
        "class ParserOutput(BaseModel):",
        "    model_config = {'extra': 'ignore'}",
        "    total_experiments: int = Field(default=0)",
        "    experiments: List[ExperimentMetadata] = Field(default_factory=list)",
        "    extraction_notes: Optional[str] = None",
        "",
    ])

    # ── Envelope Model ───────────────────────────────────────────────────────
    lines.append("class ExperimentExtraction(BaseModel):")
    lines.append("    model_config = {'extra': 'ignore'}")
    lines.append("    experiment_id: str")
    lines.append("    paper_id: str")
    lines.append("    overall_confidence: int = Field(default=3, ge=1, le=5)")
    lines.append("    validation_status: str = 'pending'")
    lines.append("    review_notes: Optional[str] = None")
    lines.append("    needs_review: bool = False")
    lines.append("    extraction_timestamp: datetime")

    for _, class_name in sub_domain_classes:
        f_name = "".join(
            ['_' + i.lower() if i.isupper() else i for i in class_name]
        ).lstrip('_').replace('_extraction', '')
        lines.append(f"    {f_name}: Optional[{class_name}] = None")

    lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info("Models generated successfully")
