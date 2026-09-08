import json
import os
from typing import Optional
from datetime import datetime

def save_checkpoint(checkpoint_dir: str, index: int, stats: dict, domain_name: str):
    """Write checkpoint state to checkpoints/latest.json."""
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, "latest.json")
    
    data = {
        "last_index": index,
        "timestamp": datetime.utcnow().isoformat(),
        "domain_name": domain_name,
        "stats": stats
    }
    
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_checkpoint(checkpoint_dir: str) -> Optional[dict]:
    """Read and return checkpoint if it exists."""
    checkpoint_path = os.path.join(checkpoint_dir, "latest.json")
    
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    return None
