PARSER_USER_TEMPLATE = """
INSTRUCTION: Find and list every distinct experiment in the paper below.
DO NOT summarize the paper.
DO NOT return the abstract, title, authors, keywords, or references.
ONLY return a JSON object with the experiments list.

Look specifically for:
- Tables showing results for different catalysts or conditions
- Sections labelled "Experimental", "Results", "Catalytic Tests"
- Any reported yield, conversion, selectivity, temperature, or pressure values

PAPER CONTENT:
{paper_content}

Remember: Return ONLY the JSON object with keys: total_experiments, experiments, extraction_notes.
"""

SUBDOMAIN_USER_TEMPLATE = """
Extract the requested data for the specific experiment described below.
Return your answer as a JSON object following the schema shown in your instructions.

EXPERIMENT CONTEXT AND FULL PAPER:
{experiment_text}
"""
