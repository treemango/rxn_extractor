PARSER_USER_TEMPLATE = """
Read the following research paper and identify all distinct experiments.
Return your answer as a JSON object following the schema shown in your instructions.

PAPER CONTENT:
{paper_content}
"""

SUBDOMAIN_USER_TEMPLATE = """
Extract the requested data for the specific experiment described below.
Return your answer as a JSON object following the schema shown in your instructions.

EXPERIMENT CONTEXT AND FULL PAPER:
{experiment_text}
"""
