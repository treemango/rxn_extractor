import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def generate_prompts(domain: Dict[str, Any], output_dir: str) -> None:
    """Generates prompt markdown files for the agents."""
    logger.info(f"Generating prompts at {output_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # ---------------------------------------------------------------- parser.md
    parser = domain.get('parser', {})

    parser_content = [
        f"You are {parser.get('role_description', 'an expert parser').strip()}",
        "",
        f"Your task: {parser.get('task_description', 'Parse experiment data.').strip()}",
        "",
        "## EXPERIMENT DIFFERENTIATORS",
        "A new experiment is defined by ANY of the following differences:",
    ]
    for diff in parser.get('experiment_differentiators', []):
        parser_content.append(f"- {diff}")

    parser_content.extend([
        "",
        "## CONFIDENCE SCORING",
    ])
    for k, v in domain.get('confidence_scale', {}).items():
        parser_content.append(f"- {k}: {v}")

    # Concrete JSON example — critical for the model to follow the schema
    json_example = json.dumps(
        {
            "total_experiments": 2,
            "experiments": [
                {
                    "experiment_number": 1,
                    "brief_description": "Ni/Al2O3 catalyst at 200°C and 1 atm",
                    "key_parameters": "catalyst=Ni/Al2O3, temp=200°C, pressure=1atm",
                    "confidence": 5
                },
                {
                    "experiment_number": 2,
                    "brief_description": "Pt/Al2O3 catalyst at 300°C and 1 atm",
                    "key_parameters": "catalyst=Pt/Al2O3, temp=300°C, pressure=1atm",
                    "confidence": 4
                }
            ],
            "extraction_notes": "Two distinct catalyst experiments identified."
        },
        indent=2
    )

    parser_content.extend([
        "",
        "## CONCRETE OUTPUT EXAMPLE",
        "Your response must look EXACTLY like this (adjust content to match the paper):",
        "```json",
        json_example,
        "```",
        "",
        "## IMPORTANT RULES",
        "- Respond in English only regardless of the language of the paper.",
        "- An experiment is ANY catalytic run, reaction test, or synthesis where at least ONE",
        "  of these is mentioned: a catalyst, a reactant, a temperature, or a product yield.",
        "  You do NOT need all fields to be present — partial information is fine.",
        "- If the paper describes a range of conditions tested on the same catalyst, that still",
        "  counts as ONE experiment unless explicitly labelled as separate runs.",
        "- If the paper contains NO catalytic or experimental work at all (e.g. it is a purely",
        "  mathematical or computational study with no reactions), return:",
        '  {"total_experiments": 0, "experiments": [], "extraction_notes": "No physical experiments found."}',
        "- For brief_description: one short sentence in English describing the main catalyst and/or reaction.",
        "- For key_parameters: list the most important variables as comma-separated key=value pairs.",
        "  If you only know one parameter, that is fine.",
        "- confidence: 1-5 integer. Use 3 if unsure.",
        "- Do NOT include any text outside the JSON object.",
        "- Do NOT use markdown formatting in your response.",
    ])

    # Optionally include few-shot examples from the YAML as additional context
    few_shot = parser.get('few_shot_examples', [])
    if few_shot:
        parser_content.extend(["", "## ADDITIONAL EXAMPLES FROM YOUR DOMAIN"])
        for ex in few_shot:
            parser_content.append(f"Input text: {ex.get('input', '').strip()}")
            parser_content.append(
                f"(In this case you would adapt the above JSON template to reflect "
                f"the experiments described: {ex.get('output', '').strip()})"
            )
            parser_content.append("")

    with open(os.path.join(output_dir, 'parser.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(parser_content))

    # ---------------------------------------------------------- subdomain prompts
    for sub in domain.get('sub_domains', []):
        content = [
            f"You are {sub.get('role_description', 'an expert').strip()}",
            "",
            f"Your task: {sub.get('task_description', 'extract parameters.').strip()}",
            "",
            "## REQUIRED FIELDS",
        ]

        for field in sub.get('fields', []):
            content.append(f"### {field['name']} ({field.get('type', 'string')})")
            content.append(f"{field.get('prompt_hint', '')}")
            if field.get('allowed_units'):
                content.append(f"Allowed units: {', '.join(field['allowed_units'])}")
            if field.get('min') is not None or field.get('max') is not None:
                content.append(
                    f"Valid range: {field.get('min', '?')} – {field.get('max', '?')}"
                    f" {field.get('target_unit', '')}"
                )
            content.append("")

        content.extend([
            "## EXTRACTION RULES",
        ])
        for rule in sub.get('extraction_rules', []):
            content.append(f"- {rule}")
        content.extend([
            "- If a value is not stated anywhere in the text, return null — NEVER invent data.",
            "- Always provide an exact quote from the paper in source_quote fields.",
            "- For numeric fields, also include the unit exactly as written in the paper.",
            "",
            "## CONFIDENCE SCORING",
        ])
        for k, v in domain.get('confidence_scale', {}).items():
            content.append(f"- {k}: {v}")

        content.extend([
            "",
            "## OUTPUT FORMAT",
            "Return ONLY a valid JSON object. No markdown fences, no explanation.",
            "Use null (not empty string) for any field you cannot find in the text.",
        ])

        with open(
            os.path.join(output_dir, f"{sub['name']}.md"), 'w', encoding='utf-8'
        ) as f:
            f.write('\n'.join(content))

    # ------------------------------------------------------ user_templates.py
    templates_content = (
        'PARSER_USER_TEMPLATE = """\n'
        'Read the following research paper and identify all distinct experiments.\n'
        'Return your answer as a JSON object following the schema shown in your instructions.\n\n'
        'PAPER CONTENT:\n'
        '{paper_content}\n'
        '"""\n\n'
        'SUBDOMAIN_USER_TEMPLATE = """\n'
        'Extract the requested data for the specific experiment described below.\n'
        'Return your answer as a JSON object following the schema shown in your instructions.\n\n'
        'EXPERIMENT CONTEXT AND FULL PAPER:\n'
        '{experiment_text}\n'
        '"""\n'
    )
    with open(os.path.join(output_dir, 'user_templates.py'), 'w', encoding='utf-8') as f:
        f.write(templates_content)

    logger.info("Prompts generated successfully")
