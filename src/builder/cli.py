"""
Build-time compiler CLI.

Reads reaction.yaml from the project root and generates:
  src/auto_generated/models.py
  src/auto_generated/config.py
  src/auto_generated/prompts/*.md
  src/auto_generated/ui/index.html

Usage:
    python -m src.builder.cli
"""
import logging
import os
import sys

from src.builder.yaml_loader import load_domain
from src.builder.model_generator import generate_models
from src.builder.config_generator import generate_config
from src.builder.prompt_generator import generate_prompts
from src.builder.ui_generator import generate_ui

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

REACTION_YAML = "reaction.yaml"


def main():
    if not os.path.exists(REACTION_YAML):
        logger.error(f"Domain file not found: {REACTION_YAML}")
        logger.error("Place your reaction.yaml in the project root and try again.")
        sys.exit(1)

    try:
        domain = load_domain(REACTION_YAML)

        # Output directories
        src_dir   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        auto_dir  = os.path.join(src_dir, 'auto_generated')
        ui_dir    = os.path.join(auto_dir, 'ui')
        prompts_dir = os.path.join(auto_dir, 'prompts')

        os.makedirs(auto_dir,    exist_ok=True)
        os.makedirs(ui_dir,      exist_ok=True)
        os.makedirs(prompts_dir, exist_ok=True)

        generate_models(domain,  os.path.join(auto_dir, 'models.py'))
        generate_config(domain,  os.path.join(auto_dir, 'config.py'))
        generate_prompts(domain, prompts_dir)
        generate_ui(domain,      os.path.join(ui_dir, 'index.html'))

        logger.info("─" * 50)
        logger.info(f"Build complete  →  {os.path.abspath(auto_dir)}/")
        logger.info("  models.py   config.py   prompts/   ui/index.html")
        logger.info("─" * 50)

    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
