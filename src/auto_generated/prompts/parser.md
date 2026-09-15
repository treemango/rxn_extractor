## TASK: COUNT EXPERIMENTS IN A RESEARCH PAPER

**YOUR ONLY JOB:** Look through the paper and count how many distinct experiments (different catalyst systems or reaction conditions) were tested. Return a JSON list of them.

## WHAT TO RETURN — COPY THIS STRUCTURE EXACTLY:
```json
{
  "total_experiments": 2,
  "experiments": [
    {
      "experiment_number": 1,
      "brief_description": "Ni/Al2O3 catalyst at 200°C and 30 atm",
      "key_parameters": "catalyst=Ni/Al2O3, temp=200°C, pressure=30atm",
      "confidence": 5
    },
    {
      "experiment_number": 2,
      "brief_description": "Pt/SiO2 catalyst at 300°C and 30 atm",
      "key_parameters": "catalyst=Pt/SiO2, temp=300°C, pressure=30atm",
      "confidence": 4
    }
  ],
  "extraction_notes": "Two catalyst systems tested at same conditions."
}
```

## WHAT COUNTS AS ONE EXPERIMENT:
Any row in a results table, or any described catalytic run where at least ONE of these is mentioned: a catalyst name, a reaction temperature, a product yield, or a conversion value.

## WHAT MAKES TWO SEPARATE EXPERIMENTS:
- Different catalyst (e.g. Ni vs Pt, or different support material)
- Different temperature tested in a separate run
- Different pressure or space velocity that produced separate reported results

## RULES:
- Respond in English only, even if the paper is in another language.
- DO NOT extract the abstract, title, authors, keywords, or references. Those are NOT experiments.
- DO NOT summarize the paper. Only list the experiments.
- If this paper has NO physical experiments (pure theory, pure review, purely computational), return:
  {"total_experiments": 0, "experiments": [], "extraction_notes": "No physical experiments found."}
- brief_description: one short English sentence about the catalyst and conditions.
- key_parameters: comma-separated key=value pairs of the most important variables.
- confidence: integer 1 to 5. Use 3 if unsure.
- Return ONLY the JSON object. No explanation. No markdown. No extra text.

## CONFIDENCE SCORING:
- 5: Explicitly stated with exact values and units
- 4: Clearly inferable from context or figures
- 3: Requires some interpretation
- 2: High ambiguity
- 1: Could not be confidently extracted
