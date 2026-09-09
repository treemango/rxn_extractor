# rxn_extractor

A schema-driven, reaction-agnostic pipeline that extracts structured experimental data from academic papers using a local LLM (Qwen via Ollama). Define your fields once in `reaction.yaml`, and the pipeline handles everything else — parsing, extraction, validation, and a human-in-the-loop review UI.

---

## Source Tree

```
rxn_extractor/
│
├── reaction.yaml              ← Single source of truth. Define your fields, units,
│                                validation rules, and prompts here. Edit this, then
│                                re-run `./start.sh build` to recompile everything.
│
├── pdfs/                      ← Drop research papers (PDF) here
├── markdowns/                 ← Converted .md files land here (auto-generated)
├── data/                      ← Extraction results (CSV files, auto-generated)
├── checkpoints/               ← Batch resume state (auto-generated)
│
├── run_batch.py               ← CLI entry point for batch extraction
├── start.sh                   ← Main script for all actions (setup, build, run)
├── requirements.txt
├── .env                       ← Local config (model, ports, timeouts)
│
├── config/
│   └── settings.py            ← All configurable settings loaded from .env
│
└── src/
    ├── builder/               ← Compile-time: reads reaction.yaml, generates code
    │   ├── cli.py             ← Entry: `python -m src.builder.cli`
    │   ├── yaml_loader.py     ← Validates reaction.yaml structure
    │   ├── model_generator.py ← Generates Pydantic models
    │   ├── config_generator.py← Generates validation bounds & unit conversions
    │   ├── prompt_generator.py← Generates LLM system prompts (.md files)
    │   └── ui_generator.py    ← Generates the HITL review dashboard (HTML)
    │
    ├── auto_generated/        ← OUTPUT of builder (do not edit manually)
    │   ├── models.py          ← Pydantic schemas for each sub-domain
    │   ├── config.py          ← Validation bounds, unit conversions, rules
    │   ├── prompts/           ← One .md system prompt per sub-domain + parser
    │   └── ui/index.html      ← HITL review dashboard
    │
    ├── core/                  ← Domain-agnostic engine (never changes)
    │   ├── llm_client.py      ← Ollama/httpx client, JSON recovery, retries
    │   ├── normalizer.py      ← Deterministic unit conversion (no LLM)
    │   └── validator.py       ← Bound checking, cross-field rules
    │
    ├── agents/
    │   ├── parser_agent.py    ← Identifies distinct experiments in a paper
    │   └── extractor.py       ← Loops sub-domains, calls LLM per sub-domain
    │
    ├── pipeline/
    │   ├── batch_manager.py   ← Processes all papers, tracks progress (Rich UI)
    │   ├── checkpoint.py      ← Save/resume batch state
    │   ├── file_reader.py     ← Reads .md files, extracts title & hash
    │   └── pdf_converter.py   ← Converts PDFs → Markdown using Docling
    │
    ├── db/
    │   └── database.py        ← CsvStore: reads/writes data/*.csv
    │
    └── api/
        ├── main.py            ← FastAPI app, serves the HITL dashboard
        └── routes.py          ← REST endpoints: queue, validate, export, stats
```

---

## Prerequisites

Install these once on any machine:

1. **Python 3.10+**
2. **Ollama** — local LLM runtime:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
3. **Pull the model** (default is 14B; ~9 GB download):
   ```bash
   ollama pull qwen2.5:14b-instruct-q4_K_M
   ```
   > On a memory-limited machine (<16 GB RAM), use the 7B variant instead:
   > ```bash
   > ollama pull qwen2.5:7b-instruct-q4_K_M
   > # then set OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M in .env
   > ```

---

## First-Time Setup

```bash
git clone <repo-url>
cd rxn_extractor

# Make the start script executable (once only)
chmod +x start.sh

# Copy example config and edit if needed (optional — defaults work out of the box)
cp .env.example .env

# Copy the example reaction schema as your starting point
cp domains/example_reaction.yaml reaction.yaml
# Edit reaction.yaml to define your fields, units, and validation rules

# Run setup: creates venv, installs dependencies, builds models/prompts/UI
./start.sh build
```

---

## Workflow

### 1. Convert PDFs to Markdown *(if your papers are PDFs)*

```bash
# Place PDFs in pdfs/
cp /path/to/papers/*.pdf pdfs/

# Convert — skips any paper whose .md already exists
./start.sh convert

# Force re-convert all PDFs (e.g., after updating Docling)
./start.sh convert --force
```

> **First run only:** Docling downloads ~1.5 GB of layout models into `~/.cache/docling/`. Subsequent runs are fast.

---

### 2. Run Batch Extraction

```bash
# Place (or convert) .md papers into markdowns/

# Extract all papers
./start.sh batch

# Test on a small set first
./start.sh batch --limit 5

# Resume a stopped run from the last checkpoint
./start.sh batch --resume
```

Results are saved to `data/experiments.csv` and `data/papers.csv`.

---

### 3. Review & Export via the HITL Dashboard

```bash
./start.sh ui
# → Open http://localhost:8000 in your browser
```

From the dashboard you can:
- Review low-confidence extractions (sorted by confidence score)
- Double-click any field to correct it inline (logged to `data/corrections.csv`)
- Approve / reject / flag experiments
- Export the cleaned dataset as CSV or JSON

---

## Subsequent Runs

| What changed | Command to run |
|---|---|
| New PDFs added to `pdfs/` | `./start.sh convert` then `./start.sh batch` |
| New `.md` files added to `markdowns/` | `./start.sh batch` |
| `reaction.yaml` edited | `./start.sh build` then `./start.sh batch` |
| Model changed in `.env` | `./start.sh batch` (rebuild not needed) |
| Want to re-run the UI only | `./start.sh ui` |

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:14b-instruct-q4_K_M` | Model to use for extraction |
| `OLLAMA_NUM_CTX` | `32768` | Context window (tokens). Safe for 60 GB RAM. |
| `OLLAMA_TIMEOUT` | `180` | Seconds to wait per LLM call |
| `MAX_RETRIES` | `3` | LLM retries per extraction (with temperature escalation) |
| `API_PORT` | `8000` | Port for the HITL web dashboard |
