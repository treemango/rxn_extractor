import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_prompts(domain: Dict[str, Any], output_dir: str) -> None:
    """Generates prompt markdown files for the agents."""
    logger.info(f"Generating prompts at {output_dir}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate parser.md
    parser = domain.get('parser', {})
    parser_content = [
        f"You are {parser.get('role_description', 'an expert parser')}.",
        f"Your task: {parser.get('task_description', 'Parse experiment data.')}",
        "",
        "## EXPERIMENT DIFFERENTIATORS",
    ]
    for diff in parser.get('experiment_differentiators', []):
        parser_content.append(f"- {diff}")
        
    parser_content.extend([
        "",
        "## CONFIDENCE SCORING"
    ])
    for k, v in domain.get('confidence_scale', {}).items():
        parser_content.append(f"- {k}: {v}")
        
    parser_content.extend([
        "",
        "## EXAMPLES"
    ])
    for ex in parser.get('few_shot_examples', []):
        parser_content.append(f"Input:\n{ex.get('input', '')}\nOutput:\n{ex.get('output', '')}\n")
        
    parser_content.extend([
        "## OUTPUT FORMAT",
        "Return ONLY valid JSON with total_experiments and experiments array."
    ])
    
    with open(os.path.join(output_dir, 'parser.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(parser_content))
        
    # Generate subdomain prompts
    for sub in domain.get('sub_domains', []):
        content = [
            f"You are {sub.get('role_description', 'an expert')}",
            f"Your task: {sub.get('task_description', 'extract parameters.')}",
            "",
            "## REQUIRED FIELDS"
        ]
        
        for field in sub.get('fields', []):
            content.append(f"### {field['name']} ({field.get('type')})")
            content.append(f"{field.get('prompt_hint', '')}")
            if 'allowed_units' in field:
                content.append(f"Allowed units: {', '.join(field['allowed_units'])}")
            content.append("")
            
        content.append("## EXTRACTION RULES")
        for rule in sub.get('extraction_rules', []):
            content.append(f"- {rule}")
        content.extend([
            "- If a value is not stated, return null — NEVER invent data",
            "- Always provide exact source quote from the paper",
            "",
            "## CONFIDENCE SCORING"
        ])
        
        for k, v in domain.get('confidence_scale', {}).items():
            content.append(f"- {k}: {v}")
            
        content.extend([
            "",
            "## OUTPUT FORMAT",
            "Return ONLY valid JSON. Include null for missing fields.",
            "For numeric fields, include the unit as written in the paper."
        ])
        
        with open(os.path.join(output_dir, f"{sub['name']}.md"), 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
            
    # User templates — write as a proper Python file
    templates_content = (
        'PARSER_USER_TEMPLATE = """\n'
        'Please extract experiments from the following paper content:\n\n'
        '{paper_content}\n'
        '"""\n\n'
        'SUBDOMAIN_USER_TEMPLATE = """\n'
        'Please extract data from the following experiment description:\n\n'
        '{experiment_text}\n'
        '"""\n'
    )
    with open(os.path.join(output_dir, 'user_templates.py'), 'w', encoding='utf-8') as f:
        f.write(templates_content)

    logger.info("Prompts generated successfully")
