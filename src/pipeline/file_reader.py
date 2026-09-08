import glob
import hashlib
import os
from typing import List, Dict

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
