# These templates are no longer used for building user messages.
#
# With the KV Prefix Cache refactor (Sept 2026), the paper is sent as its own
# dedicated message in the chat array (the shared cache prefix). The parser and
# subdomain agents build their question_prompt inline from their system prompt
# + experiment pointer. The {paper_content} / {experiment_text} placeholders
# that used to live here are therefore obsolete.
#
# Kept as empty strings to avoid ImportError in any code that still imports
# these names. Safe to remove entirely once all callers are confirmed updated.

PARSER_USER_TEMPLATE = ""

SUBDOMAIN_USER_TEMPLATE = ""
