import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def generate_ui(domain: Dict[str, Any], output_path: str) -> None:
    """
    Generates the HITL UI index.html file.

    IMPORTANT: If index.html already exists on disk, this function does
    nothing and exits immediately. This preserves any hand-crafted UI that
    has been written to replace the auto-generated scaffold.

    To force a fresh scaffold (e.g. after deleting the existing UI), simply
    delete src/auto_generated/ui/index.html and re-run the builder.
    """
    if os.path.exists(output_path):
        logger.info(
            f"UI already exists at {output_path} — skipping generation. "
            f"Delete the file to regenerate the scaffold."
        )
        return

    logger.info(f"Generating UI scaffold at {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    domain_name = domain.get('domain_name', 'rxn_extractor')

    # Minimal scaffold — just enough to point the developer to the docs.
    # The real UI is expected to be written manually (see src/auto_generated/ui/).
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{domain_name} HITL</title>
    <style>
        body {{ font-family: system-ui, sans-serif; display: flex; align-items: center;
                justify-content: center; height: 100vh; margin: 0; background: #f1f5f9; }}
        .box {{ background: white; padding: 2rem 2.5rem; border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; max-width: 480px; }}
        h1 {{ color: #1e293b; margin-bottom: 0.5rem; }}
        p  {{ color: #64748b; line-height: 1.6; }}
        a  {{ color: #3b82f6; }}
    </style>
</head>
<body>
    <div class="box">
        <h1>{domain_name}</h1>
        <p>UI scaffold generated. Replace this file with your HITL dashboard.</p>
        <p>Backend API is live at <a href="/docs">/docs</a>.</p>
    </div>
</body>
</html>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info("UI scaffold written. Customise src/auto_generated/ui/index.html to build your dashboard.")
