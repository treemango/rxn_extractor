import yaml
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_domain(yaml_path: str) -> Dict[str, Any]:
    """
    Reads a YAML domain definition file, validates required keys,
    and returns the parsed dictionary.
    
    Args:
        yaml_path: Path to the YAML file.
        
    Returns:
        The parsed YAML dictionary.
        
    Raises:
        ValueError: If required keys are missing or invalid.
    """
    logger.info(f"Loading domain from {yaml_path}")
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            domain = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read YAML file {yaml_path}: {e}")
        raise ValueError(f"Failed to read YAML file: {e}")

    if not domain:
        raise ValueError("YAML file is empty")

    required_keys = ['domain_name', 'sub_domains', 'parser']
    for key in required_keys:
        if key not in domain:
            raise ValueError(f"Missing required key: {key}")
            
    if not isinstance(domain['sub_domains'], list) or not domain['sub_domains']:
        raise ValueError("sub_domains must be a non-empty list")

    logger.info(f"Successfully loaded domain definition: {domain.get('domain_name')}")
    return domain
