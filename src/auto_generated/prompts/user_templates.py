PARSER_USER_TEMPLATE = """
INSTRUCTION: Find and list every distinct experiment in the paper below.
DO NOT summarize the paper.
DO NOT return the abstract, title, authors, keywords, or references.
ONLY return a JSON object with the experiments list.

Specifically look for:
- Tables showing results for different catalysts or conditions
- Sections labelled "Experimental", "Results", "Catalytic Tests"
- Any reported yield, conversion, selectivity, temperature, or pressure values
- Each unique catalyst + condition combination = one experiment

PAPER CONTENT:
{paper_content}

Remember: Return ONLY the JSON object with keys:
  total_experiments, experiments, extraction_notes
"""

SUBDOMAIN_USER_TEMPLATE = """
You will receive a TARGET EXPERIMENT block at the top, followed by the
full paper text. Extract data ONLY for the specified target experiment.

{experiment_text}
"""
