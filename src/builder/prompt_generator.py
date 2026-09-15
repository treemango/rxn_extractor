import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Parser Prompt Generation
# ─────────────────────────────────────────────────────────────────────────────

_PARSER_EXAMPLES = """
## WORKED EXAMPLES — READ ALL OF THESE CAREFULLY

────────────────────────────────────────────────────────────────────────────────
EXAMPLE 1: Ligand / Catalyst Variation (most common type)
────────────────────────────────────────────────────────────────────────────────
Scenario: A paper tests 3 different ligands combined with Ni(COD)2, all at 80°C
and 30-32 atm. Results are in Table 1.

Input text excerpt:
"N-(pyrazin-2-yl) (1), N-(pyridin-2-yl) (2), and N-(pyrimidin-2-yl) (3)
α-diphenylphosphinoglycines combined with Ni(COD)2 were tested. Table 1:
Ligand 1: TOF=52 h-1, butene yield=379 golig/gNi.
Ligand 2: TOF=411 h-1, butene yield=1556 golig/gNi.
Ligand 3: TOF=384 h-1, butene yield=881 golig/gNi.
Conditions: 80°C, 30-32 atm, THF solvent, 18-22 h."

Correct output:
{
  "total_experiments": 3,
  "experiments": [
    {
      "experiment_number": 1,
      "brief_description": "N-(pyrazin-2-yl) α-diphenylphosphinoglycine with Ni(COD)2 at 80°C",
      "catalyst_name": "1/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "80°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butene-1, hexene-1",
      "key_section": "Table 1, Row 1 (Ligand 1)",
      "key_parameters": "ligand=N-(pyrazin-2-yl), TOF=52 h-1, butene_yield=379 golig/gNi",
      "confidence": 5
    },
    {
      "experiment_number": 2,
      "brief_description": "N-(pyridin-2-yl) α-diphenylphosphinoglycine with Ni(COD)2 at 80°C",
      "catalyst_name": "2/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "80°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butene-1, hexene-1",
      "key_section": "Table 1, Row 2 (Ligand 2)",
      "key_parameters": "ligand=N-(pyridin-2-yl), TOF=411 h-1, butene_yield=1556 golig/gNi",
      "confidence": 5
    },
    {
      "experiment_number": 3,
      "brief_description": "N-(pyrimidin-2-yl) α-diphenylphosphinoglycine with Ni(COD)2 at 80°C",
      "catalyst_name": "3/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "80°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butene-1, hexene-1",
      "key_section": "Table 1, Row 3 (Ligand 3)",
      "key_parameters": "ligand=N-(pyrimidin-2-yl), TOF=384 h-1, butene_yield=881 golig/gNi",
      "confidence": 5
    }
  ],
  "extraction_notes": "Three distinct catalyst systems tested at identical conditions."
}

────────────────────────────────────────────────────────────────────────────────
EXAMPLE 2: Temperature Series (same catalyst, different temperatures)
────────────────────────────────────────────────────────────────────────────────
Scenario: A paper tests ONE catalyst at 5 different temperatures (30, 55, 80, 105, 130°C).
Each temperature row in Table 2 is a SEPARATE experiment.

Input text excerpt:
"Table 2. Results of catalytic tests of the 1/Ni(COD)2 system at 30-130°C.
Test 1: T=30°C, α=0.52, TOF=ND, butene=39.2%.
Test 2: T=55°C, α=0.66, TOF=48 h-1, butene=16.9%.
Test 3: T=80°C, α=0.19, TOF=52 h-1, butene=72.6%.
Test 4: T=105°C, α=0.20, TOF=509 h-1, butene=71.4%.
Test 5: T=130°C, α=0.41, TOF=203 h-1, butene=31.3%."

Correct output:
{
  "total_experiments": 5,
  "experiments": [
    {
      "experiment_number": 1,
      "brief_description": "1/Ni(COD)2 catalyst at 30°C",
      "catalyst_name": "1/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "30°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butenes (39.2%)",
      "key_section": "Table 2, Test 1",
      "key_parameters": "temp=30°C, alpha=0.52, TOF=ND, butene_selectivity=39.2%",
      "confidence": 5
    },
    {
      "experiment_number": 2,
      "brief_description": "1/Ni(COD)2 catalyst at 55°C",
      "catalyst_name": "1/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "55°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butenes (16.9%)",
      "key_section": "Table 2, Test 2",
      "key_parameters": "temp=55°C, alpha=0.66, TOF=48 h-1, butene_selectivity=16.9%",
      "confidence": 5
    },
    {
      "experiment_number": 3,
      "brief_description": "1/Ni(COD)2 catalyst at 80°C",
      "catalyst_name": "1/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "80°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butenes (72.6%), hexenes (20.6%)",
      "key_section": "Table 2, Test 3",
      "key_parameters": "temp=80°C, alpha=0.19, TOF=52 h-1, butene_selectivity=72.6%",
      "confidence": 5
    },
    {
      "experiment_number": 4,
      "brief_description": "1/Ni(COD)2 catalyst at 105°C",
      "catalyst_name": "1/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "105°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butenes (71.4%), hexenes (21.2%)",
      "key_section": "Table 2, Test 4",
      "key_parameters": "temp=105°C, alpha=0.20, TOF=509 h-1, butene_selectivity=71.4%",
      "confidence": 5
    },
    {
      "experiment_number": 5,
      "brief_description": "1/Ni(COD)2 catalyst at 130°C",
      "catalyst_name": "1/Ni(COD)2",
      "reactant": "ethylene",
      "main_temperature": "130°C",
      "main_pressure": "30-32 atm",
      "products_mentioned": "butenes (31.3%)",
      "key_section": "Table 2, Test 5",
      "key_parameters": "temp=130°C, alpha=0.41, TOF=203 h-1, butene_selectivity=31.3%",
      "confidence": 5
    }
  ],
  "extraction_notes": "Five temperature variation experiments using the same 1/Ni(COD)2 system."
}

────────────────────────────────────────────────────────────────────────────────
EXAMPLE 3: Purely computational / theoretical paper (ZERO experiments)
────────────────────────────────────────────────────────────────────────────────
Scenario: The paper only presents DFT calculations. No physical reactions were run.

Input text excerpt:
"Using density functional theory (DFT) at the B3LYP/6-31G* level, we calculated
the activation barriers for the Cossee-Arlman mechanism. The insertion barrier was
found to be 15.3 kcal/mol. No experimental validation was performed."

Correct output:
{
  "total_experiments": 0,
  "experiments": [],
  "extraction_notes": "Purely computational DFT study. No physical experiments performed."
}

────────────────────────────────────────────────────────────────────────────────
EXAMPLE 4: Mixed paper — theory + one experimental validation
────────────────────────────────────────────────────────────────────────────────
Scenario: Most of the paper is computational, but there is ONE experimental section
that validates the model predictions.

Input text excerpt:
"Quantum chemical calculations predicted high selectivity for butene-1.
To validate, Ni/Al2O3 catalyst (5 wt% Ni) was tested in a batch autoclave
at 300°C and 25 atm for 4 h. Ethylene conversion: 78%, butene-1 selectivity: 65%."

Correct output:
{
  "total_experiments": 1,
  "experiments": [
    {
      "experiment_number": 1,
      "brief_description": "Ni/Al2O3 validation experiment at 300°C, 25 atm",
      "catalyst_name": "Ni/Al2O3",
      "reactant": "ethylene",
      "main_temperature": "300°C",
      "main_pressure": "25 atm",
      "products_mentioned": "butene-1 (65% selectivity)",
      "key_section": "Experimental section, validation run",
      "key_parameters": "catalyst=Ni/Al2O3 (5 wt% Ni), temp=300°C, pressure=25 atm, conversion=78%, butene-1_sel=65%",
      "confidence": 5
    }
  ],
  "extraction_notes": "One physical validation experiment found. Remainder of paper is DFT calculation."
}

────────────────────────────────────────────────────────────────────────────────
EXAMPLE 5: Paper with incomplete data (some values missing)
────────────────────────────────────────────────────────────────────────────────
Scenario: A paper briefly mentions testing a catalyst but only reports a few values.
You should still report it as 1 experiment — do not require complete data.

Input text excerpt:
"Preliminary tests with a Pd/SiO2 catalyst showed promising ethylene dimerization
activity at elevated temperatures. Full characterization data will be reported elsewhere."

Correct output:
{
  "total_experiments": 1,
  "experiments": [
    {
      "experiment_number": 1,
      "brief_description": "Pd/SiO2 preliminary ethylene dimerization test",
      "catalyst_name": "Pd/SiO2",
      "reactant": "ethylene",
      "main_temperature": null,
      "main_pressure": null,
      "products_mentioned": "ethylene dimerization products",
      "key_section": "preliminary results section",
      "key_parameters": "catalyst=Pd/SiO2, reaction=ethylene dimerization",
      "confidence": 2
    }
  ],
  "extraction_notes": "Incomplete data — only catalyst mentioned. No quantitative values reported."
}

────────────────────────────────────────────────────────────────────────────────
EXAMPLE 6: Catalyst variation with support (common in heterogeneous catalysis)
────────────────────────────────────────────────────────────────────────────────
Scenario: Same metal (Ni), but different support materials tested. Each combination
is a separate experiment.

Input text excerpt:
"Table 3. Effect of support on Ni catalyst performance.
Ni/Al2O3: conversion 85%, selectivity 70%.
Ni/SiO2: conversion 72%, selectivity 82%.
Ni/ZSM-5: conversion 91%, selectivity 60%.
All at 400°C, WHSV=2 h-1."

Correct output:
{
  "total_experiments": 3,
  "experiments": [
    {
      "experiment_number": 1,
      "brief_description": "Ni/Al2O3 catalyst at 400°C",
      "catalyst_name": "Ni/Al2O3",
      "reactant": "ethylene",
      "main_temperature": "400°C",
      "main_pressure": null,
      "products_mentioned": "conversion 85%, selectivity 70%",
      "key_section": "Table 3, Row 1 (Ni/Al2O3)",
      "key_parameters": "catalyst=Ni/Al2O3, temp=400°C, WHSV=2 h-1, conversion=85%, selectivity=70%",
      "confidence": 5
    },
    {
      "experiment_number": 2,
      "brief_description": "Ni/SiO2 catalyst at 400°C",
      "catalyst_name": "Ni/SiO2",
      "reactant": "ethylene",
      "main_temperature": "400°C",
      "main_pressure": null,
      "products_mentioned": "conversion 72%, selectivity 82%",
      "key_section": "Table 3, Row 2 (Ni/SiO2)",
      "key_parameters": "catalyst=Ni/SiO2, temp=400°C, WHSV=2 h-1, conversion=72%, selectivity=82%",
      "confidence": 5
    },
    {
      "experiment_number": 3,
      "brief_description": "Ni/ZSM-5 catalyst at 400°C",
      "catalyst_name": "Ni/ZSM-5",
      "reactant": "ethylene",
      "main_temperature": "400°C",
      "main_pressure": null,
      "products_mentioned": "conversion 91%, selectivity 60%",
      "key_section": "Table 3, Row 3 (Ni/ZSM-5)",
      "key_parameters": "catalyst=Ni/ZSM-5, temp=400°C, WHSV=2 h-1, conversion=91%, selectivity=60%",
      "confidence": 5
    }
  ],
  "extraction_notes": "Three support variations with same Ni loading. Conditions identical."
}
"""


def generate_prompts(domain: Dict[str, Any], output_dir: str) -> None:
    """Generates prompt markdown files for the agents."""
    logger.info(f"Generating prompts at {output_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # ── Collect info from domain for contextualising examples ────────────────
    parser     = domain.get('parser', {})
    differentiators = parser.get('experiment_differentiators', [])
    sub_names  = [s['name'] for s in domain.get('sub_domains', [])]

    # Fix "You are " prefix: role_description in YAML starts with
    # "You are an expert..." — avoid doubling it.
    def _role(role_str: str) -> str:
        s = role_str.strip()
        if s.lower().startswith('you are '):
            return s  # already a full sentence
        return f"You are {s}"

    # ── parser.md ────────────────────────────────────────────────────────────
    role_sentence  = _role(parser.get('role_description', 'an expert analytical researcher'))
    task_sentence  = parser.get('task_description', 'Extract and enumerate distinct experiments.').strip()

    differentiator_lines = '\n'.join(f'- {d}' for d in differentiators)

    # Build the JSON schema example using actual sub-domain names
    schema_example = json.dumps(
        {
            "total_experiments": 2,
            "experiments": [
                {
                    "experiment_number": 1,
                    "brief_description": "Catalyst A tested at 80°C under 30 atm",
                    "catalyst_name": "Catalyst A / Ni(COD)2",
                    "reactant": "ethylene",
                    "main_temperature": "80°C",
                    "main_pressure": "30 atm",
                    "products_mentioned": "butene-1, hexene-1",
                    "key_section": "Table 1, Row 1",
                    "key_parameters": "catalyst=CatalystA, temp=80°C, TOF=52 h-1",
                    "confidence": 5
                },
                {
                    "experiment_number": 2,
                    "brief_description": "Catalyst B tested at 80°C under 30 atm",
                    "catalyst_name": "Catalyst B / Ni(COD)2",
                    "reactant": "ethylene",
                    "main_temperature": "80°C",
                    "main_pressure": "30 atm",
                    "products_mentioned": "butene-1, hexene-1",
                    "key_section": "Table 1, Row 2",
                    "key_parameters": "catalyst=CatalystB, temp=80°C, TOF=411 h-1",
                    "confidence": 5
                }
            ],
            "extraction_notes": "Two distinct catalyst systems tested at identical conditions."
        },
        indent=2
    )

    parser_content = f"""{role_sentence}

## YOUR ONLY JOB
Find and list every distinct experiment in the paper. Do NOT summarize the paper.
Do NOT return the title, abstract, authors, keywords, or references.
ONLY return the JSON object described below.

## WHAT COUNTS AS ONE EXPERIMENT
Any physical catalytic run, reaction test, or synthesis where at least ONE of these
is mentioned: a catalyst name, a reaction temperature, a product yield, or a
conversion/selectivity value.

## WHAT MAKES TWO SEPARATE EXPERIMENTS
{differentiator_lines}
- Each table row with different numerical results = a separate experiment
- A temperature series (e.g. 30°C, 55°C, 80°C, 105°C) = one experiment per temperature

## REQUIRED JSON STRUCTURE — COPY THIS EXACTLY:
```json
{schema_example}
```

## FIELD DEFINITIONS
- **experiment_number**: Sequential integer starting at 1.
- **brief_description**: One English sentence — catalyst name + reaction + key condition.
- **catalyst_name**: Exact catalyst identifier as written (e.g. "1/Ni(COD)2", "Ni/Al2O3").
- **reactant**: Primary feedstock (e.g. "ethylene", "HDPE", "propylene").
- **main_temperature**: Temperature as written (e.g. "80°C", "80-105°C"). null if not stated.
- **main_pressure**: Pressure as written (e.g. "30 atm", "20-35 atm"). null if not stated.
- **products_mentioned**: Key products/yields noted (e.g. "butene-1 71%, hexene-1 21%").
- **key_section**: Exact location in paper — table name + row if applicable
  (e.g. "Table 1, Row 2 (Ligand 2)", "Table 2, Test 4", "Experimental section").
- **key_parameters**: Comma-separated key=value pairs of the most important
  distinguishing values (temperature, TOF, conversion, selectivity, etc.).
- **confidence**: Integer 1-5. Use 5 if values are explicitly stated, 3 if inferred.

## STRICT RULES
- Respond in English regardless of the input paper language.
- For null fields: write null (not empty string "").
- If the paper has NO physical experiments (pure theory, DFT, review, synthesis-only
  with no catalytic test), return: {{"total_experiments": 0, "experiments": [], "extraction_notes": "No physical experiments."}}
- Return ONLY the JSON object. No explanation, no markdown fences.

{_PARSER_EXAMPLES}
"""

    with open(os.path.join(output_dir, 'parser.md'), 'w', encoding='utf-8') as f:
        f.write(parser_content)

    # ── Subdomain prompts ─────────────────────────────────────────────────────
    for sub in domain.get('sub_domains', []):
        role_sentence_sub = _role(sub.get('role_description', 'an expert'))
        task_sentence_sub = sub.get('task_description', 'Extract parameters.').strip()

        content_lines = [
            role_sentence_sub,
            "",
            f"## YOUR TASK",
            task_sentence_sub,
            "",
            "## CONTEXT YOU WILL RECEIVE",
            "At the top of the user message you will see a structured block like:",
            "  TARGET EXPERIMENT: #2 of 5",
            "  Catalyst/System : 1/Ni(COD)2",
            "  Temperature     : 80°C",
            "  Paper location  : Table 2, Test 3",
            "Use this block to identify WHICH experiment you are extracting.",
            "Extract data ONLY for that specific experiment. Ignore all others.",
            "",
            "## REQUIRED FIELDS",
        ]

        for field in sub.get('fields', []):
            f_name = field['name']
            f_type = field.get('type', 'string')
            hint   = field.get('prompt_hint', '').strip()
            units  = field.get('allowed_units', [])
            f_min  = field.get('min')
            f_max  = field.get('max')
            t_unit = field.get('target_unit', '')

            content_lines.append(f"### `{f_name}` ({f_type})")
            if hint:
                content_lines.append(f"  {hint}")
            if units:
                content_lines.append(f"  Accepted units: {', '.join(units)}")
            if t_unit:
                content_lines.append(f"  Preferred output unit: {t_unit}")
            if f_min is not None or f_max is not None:
                content_lines.append(
                    f"  Valid range: {f_min if f_min is not None else '—'} "
                    f"to {f_max if f_max is not None else '∞'} {t_unit}"
                )
            content_lines.append("")

        # Extraction rules
        content_lines.extend([
            "## EXTRACTION RULES",
        ])
        for rule in sub.get('extraction_rules', []):
            content_lines.append(f"- {rule}")
        content_lines.extend([
            "- If a field is not mentioned for THIS specific experiment, return null.",
            "- NEVER invent data. Only extract what is explicitly stated.",
            "- For numeric fields: extract the numeric value only (not the unit string).",
            "- For unit fields: extract the unit string as written in the paper.",
            "",
            "## CONFIDENCE SCORING",
            "- 5: Value explicitly stated with exact numbers and units",
            "- 4: Clearly inferable from context, tables, or figures",
            "- 3: Requires interpretation or minor ambiguity",
            "- 2: High ambiguity or indirect evidence only",
            "- 1: Could not be confidently extracted",
            "",
        ])

        # Build a concrete JSON example for this sub-domain
        example_dict: Dict[str, Any] = {"confidence_score": 5, "source_quote": "exact sentence from paper"}
        for field in sub.get('fields', []):
            f_name = field['name']
            f_type = field.get('type', 'string')
            if f_type == 'float':
                example_dict[f"{f_name}_value"] = 52.0
                example_dict[f"{f_name}_unit"] = field.get('target_unit', 'unit')
            elif f_type == 'range':
                example_dict[f"{f_name}_min"] = 80.0
                example_dict[f"{f_name}_max"] = 105.0
                example_dict[f"{f_name}_unit"] = field.get('target_unit', 'unit')
            elif f_type in ('string', 'enum'):
                vals = field.get('allowed_values', [])
                example_dict[f_name] = vals[0] if vals else "example value"

        content_lines.extend([
            "## EXAMPLE OUTPUT (fill with real values from the paper):",
            "```json",
            json.dumps(example_dict, indent=2),
            "```",
            "",
            "## OUTPUT FORMAT",
            "Return ONLY a valid JSON object. No markdown fences. No explanation.",
            "Use null (not empty string) for any field not found in the paper.",
        ])

        with open(
            os.path.join(output_dir, f"{sub['name']}.md"), 'w', encoding='utf-8'
        ) as f:
            f.write('\n'.join(content_lines))

    # ── user_templates.py ─────────────────────────────────────────────────────
    templates_content = (
        'PARSER_USER_TEMPLATE = """\n'
        'INSTRUCTION: Find and list every distinct experiment in the paper below.\n'
        'DO NOT summarize the paper.\n'
        'DO NOT return the abstract, title, authors, keywords, or references.\n'
        'ONLY return a JSON object with the experiments list.\n\n'
        'Specifically look for:\n'
        '- Tables showing results for different catalysts or conditions\n'
        '- Sections labelled "Experimental", "Results", "Catalytic Tests"\n'
        '- Any reported yield, conversion, selectivity, temperature, or pressure values\n'
        '- Each unique catalyst + condition combination = one experiment\n\n'
        'PAPER CONTENT:\n'
        '{paper_content}\n\n'
        'Remember: Return ONLY the JSON object with keys:\n'
        '  total_experiments, experiments, extraction_notes\n'
        '"""\n\n'
        'SUBDOMAIN_USER_TEMPLATE = """\n'
        'You will receive a TARGET EXPERIMENT block at the top, followed by the\n'
        'full paper text. Extract data ONLY for the specified target experiment.\n\n'
        '{experiment_text}\n'
        '"""\n'
    )
    with open(os.path.join(output_dir, 'user_templates.py'), 'w', encoding='utf-8') as f:
        f.write(templates_content)

    logger.info("Prompts generated successfully")
