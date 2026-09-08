import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_config(domain: Dict[str, Any], output_path: str) -> None:
    """Generates the config Python file."""
    logger.info(f"Generating config at {output_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    lines = [
        "import math",
        "",
        f"DOMAIN_NAME = {repr(domain.get('domain_name', ''))}",
        f"DOMAIN_DESCRIPTION = {repr(domain.get('domain_description', ''))}",
        f"INPUT_MARKDOWN_DIR = {repr(domain.get('input_markdown_dir', ''))}",
        ""
    ]
    
    # SUB_DOMAIN_NAMES
    sub_domain_names = {sub['name']: sub.get('display_name', sub['name']) for sub in domain.get('sub_domains', [])}
    lines.append(f"SUB_DOMAIN_NAMES = {json.dumps(sub_domain_names, indent=4)}")
    lines.append("")
    
    # VALIDATION_BOUNDS
    bounds = {}
    for sub in domain.get('sub_domains', []):
        for field in sub.get('fields', []):
            if field.get('min') is not None or field.get('max') is not None:
                key = f"{sub['name']}.{field['name']}"
                bounds[key] = {
                    "min": field.get('min'),
                    "max": field.get('max'),
                    "target_unit": field.get('target_unit'),
                    "allowed_units": field.get('allowed_units', [])
                }

    lines.append(f"VALIDATION_BOUNDS = {repr(bounds)}")
    lines.append("")

    # UNIT_CONVERSIONS
    lines.append("UNIT_CONVERSIONS = {")
    lines.append("    ('K', 'Celsius'): lambda x: x - 273.15,")
    lines.append("    ('Kelvin', 'Celsius'): lambda x: x - 273.15,")
    lines.append("    ('Fahrenheit', 'Celsius'): lambda x: (x - 32) * 5.0/9.0,")
    lines.append("    ('kg', 'g'): lambda x: x * 1000.0,")
    lines.append("    ('mg', 'g'): lambda x: x / 1000.0,")
    lines.append("    ('lb', 'g'): lambda x: x * 453.592,")
    lines.append("    ('minutes', 'hours'): lambda x: x / 60.0,")
    lines.append("    ('seconds', 'hours'): lambda x: x / 3600.0,")
    lines.append("    ('days', 'hours'): lambda x: x * 24.0,")
    lines.append("    ('L/min', 'mL/min'): lambda x: x * 1000.0,")
    lines.append("    ('L/h', 'mL/min'): lambda x: x * 1000.0 / 60.0,")
    lines.append("    ('cm3/min', 'mL/min'): lambda x: x,")
    lines.append("    ('bar', 'atm'): lambda x: x * 0.986923,")
    lines.append("    ('kPa', 'atm'): lambda x: x / 101.325,")
    lines.append("    ('MPa', 'atm'): lambda x: x * 9.86923,")
    lines.append("    ('psi', 'atm'): lambda x: x / 14.6959,")
    lines.append("    ('mmol/g', 'umol/g'): lambda x: x * 1000.0,")
    lines.append("    ('h-1', 's-1'): lambda x: x / 3600.0,")
    lines.append("}")
    lines.append("")

    # VALIDATION_RULES
    lines.append(f"VALIDATION_RULES = {repr(domain.get('validation_rules', []))}")
    lines.append("")

    # CONFIDENCE
    lines.append(f"CONFIDENCE_SCALE = {repr(domain.get('confidence_scale', {}))}")
    lines.append("")

    conf_algo = domain.get('confidence_algorithm', {})
    lines.append(f"REVIEW_THRESHOLD = {conf_algo.get('review_threshold', 3)}")
    lines.append("")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        
    logger.info("Config generated successfully")
