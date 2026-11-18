# rxn_extractor

`rxn_extractor` turns research papers into structured, experiment-level reaction data. A YAML domain definition describes the target reaction, extraction fields, units, and validation rules. The builder compiles that definition into Pydantic models, prompts, and configuration. The batch pipeline then finds experiments in paper Markdown, extracts the configured fields with a local Qwen GGUF model, normalizes values, validates them, and records the results in CSV files.

Inference runs in-process with `llama-cpp-python` against `models/Qwen2.5-14B-Instruct-Q4_K_M.gguf`; no model server is required. PBS scripts submit PDF conversion and extraction as separate GPU jobs on the Aqua HPC cluster.

---

## End-to-End Workflow

```
  PDFs in pdfs/
       │
       │  qsub markdown_converter.sh
       ▼
  Markdown files in markdowns/
       │
       │  qsub extractor.sh
       ▼
  data/papers.csv  +  data/experiments.csv
       │
       │  python export_csv.py
       ▼
  data/flattened_results.csv   ← ready for analysis
```

**Step by step:**

1. **Collect PDFs** — Place all source papers in `pdfs/`.
2. **Convert to Markdown** — Submit `qsub markdown_converter.sh`. Docling reads from `pdfs/` and writes `.md` files to `markdowns/`. Wait for the job to complete before proceeding.
3. **Extract reactions** — Submit `qsub extractor.sh`. The pipeline screens each paper for relevance, identifies individual experiments, and runs multi-agent extraction for each. Results are written to `data/papers.csv` and `data/experiments.csv`.
4. **Flatten results** — Run `python export_csv.py` locally. This reads the JSON `data` column from `experiments.csv` and writes a wide, analysis-ready table to `data/flattened_results.csv`.
5. **Use the data** — Open `data/flattened_results.csv` in Excel, pandas, or any analysis tool.

---

## Project Tree

```text
rxn_extractor/
├── reaction.yaml                  # Active reaction/domain definition
├── pdfs/                          # Source PDF papers (inputs)
├── markdowns/                     # Docling-converted papers; batch input
├── models/
│   └── Qwen2.5-14B-Instruct-Q4_K_M.gguf
├── data/                          # CSV results
├── checkpoints/                   # Batch resume state
├── logs/                          # PBS stdout/stderr targets
├── run_batch.py                   # Batch extraction entry point (called by extractor.sh)
├── export_csv.py                  # Post-processing: flatten experiments.csv
├── markdown_converter.sh          # PBS job: PDF → Markdown conversion
├── extractor.sh                   # PBS job: Markdown → CSV extraction
├── AQUA_RUNNING_INSTRUCTIONS.md   # Aqua cluster setup and operations guide
├── project.md                     # Detailed architecture and technical notes
├── config/
│   └── settings.py                # Runtime settings (LLM, extraction, API)
└── src/
    ├── builder/                   # Compile reaction.yaml into generated artifacts
    ├── auto_generated/            # Models, config, prompts, and review UI
    ├── agents/                    # Relevance filtering, experiment parsing, extraction
    ├── core/                      # Local LLM client, normalization, validation
    ├── pipeline/                  # PDF conversion, file reading, batch orchestration
    ├── db/                        # CSV persistence layer
    └── api/                       # Human-in-the-loop review dashboard (FastAPI)
```

---

## Domain Definition (`reaction.yaml`)

The domain definition is the single configuration file that controls what gets extracted. It identifies the target reaction, the Markdown input directory, and declares sub-domains with their fields, units, and validation bounds. The active schema extracts catalyst identity/preparation/characterization and reaction conditions:

```yaml
domain_name: "ethylene_conversion"
target_reaction: "oligomerization of ethylene to produce C6-C12 olefins"
input_markdown_dir: "markdowns/"
sub_domains:
  - name: "catalyst"
    fields:
      - name: "catalyst_class"
        type: "string"
      - name: "surface_area"
        type: "float"
        allowed_units: ["m2/g", "m²/g"]
  - name: "conditions"
    fields:
      - name: "temperature"
        type: "range"
        target_unit: "Celsius"
      - name: "total_pressure"
        type: "float"
        target_unit: "atm"
      - name: "ethylene_partial_pressure"
        type: "float"
        target_unit: "atm"
```

This is a shortened illustration; use the complete schema in `reaction.yaml`.

If the schema changes, rebuild generated artifacts before submitting extraction:

```bash
source ~/rxn_env/bin/activate
python -m src.builder.cli
```

The generated models, validation/conversion config, and prompts are written under `src/auto_generated/`. Generated files should be rebuilt from the YAML rather than edited by hand. Existing CSV records are not migrated when the schema changes; archive prior results before combining runs.

---

## Outputs

The batch pipeline writes these files under `data/`:

| File                    | Contents                                                                       |
| ----------------------- | ------------------------------------------------------------------------------ |
| `papers.csv`            | Paper identifiers, paths, processing status (pending / irrelevant / processed / error), and error messages |
| `experiments.csv`       | One row per extracted experiment; confidence score, validation flags, and a JSON `data` column containing all extracted fields |
| `batch_jobs.csv`        | Batch-level processing status and counts                                       |
| `flattened_results.csv` | Generated by `export_csv.py`; wide table with one column per extracted field, ready for analysis |

In `experiments.csv`, the `data` column contains a JSON-encoded object with extracted values grouped by sub-domain:

```json
{
  "sub_domain_results": {
    "catalyst": {
      "catalyst_class": "supported metal catalyst",
      "active_metal": "Ni",
      "surface_area_value": 145.0,
      "surface_area_unit": "m2/g"
    },
    "conditions": {
      "temperature_min": 250.0,
      "temperature_max": 250.0,
      "total_pressure_value": 1.0,
      "total_pressure_unit": "atm",
      "ethylene_partial_pressure_value": null
    }
  },
  "overall_confidence": 4,
  "validation": { ... }
}
```

Run `python export_csv.py` after a batch to get a flat, analysis-friendly version in `data/flattened_results.csv`.

---

## Pipeline Internals

### Relevance filter

Before any expensive extraction runs, `FilterAgent` checks the first ~4 000 characters of each paper (title, abstract, introduction) against the `target_reaction` defined in `reaction.yaml`. Papers that do not match are recorded in `papers.csv` with status `irrelevant` and skipped. This avoids running the full extraction pipeline on unrelated papers.

### Experiment parsing

`ParserAgent` reads section-aware text from the paper and asks the model to enumerate distinct physical experiments (not computational, review, or theoretical sections). Each experiment is returned with a brief description, key parameter hints, and a pointer to the paper section where it appears.

### Sub-domain extraction

`Extractor` loops over the sub-domains declared in `reaction.yaml`. For each experiment, it:
1. Selects the most relevant Markdown sections for that sub-domain.
2. Passes a structured context block (experiment description, catalyst, temperature, pressure, section pointer) together with the section text to the LLM.
3. Validates the returned values against the bounds and rules in the domain config.
4. Normalizes units to the `target_unit` declared in `reaction.yaml`.

Results are assembled into a single dict per experiment and written to `experiments.csv`.

### Checkpointing and resume

The batch saves `checkpoints/latest.json` after every paper. To resume an interrupted run, pass `--resume` to `run_batch.py` (or leave the flag in `extractor.sh`).

### Review dashboard

`src/api/` provides a lightweight FastAPI dashboard for human-in-the-loop review of extracted experiments. Reviewers can inspect extracted values, flag issues, and submit corrections, which are recorded in `data/corrections.csv`.

---

## Running on Aqua

### Quick reference

```bash
# 1. Place PDFs in pdfs/
# 2. Rebuild generated artifacts if reaction.yaml changed:
source ~/rxn_env/bin/activate
python -m src.builder.cli

# 3. Submit PDF conversion job
qsub markdown_converter.sh

# 4. Wait for conversion to finish, then submit extraction
qstat -u "$USER"
qsub extractor.sh

# 5. Monitor
tail -f logs/batch_out.log
tail -f logs/batch_err.log

# 6. Retrieve results to your local machine
scp -r <username>@aqua.iitm.ac.in:~/rxn_extractor/data ./aqua_results/

# 7. Flatten
python export_csv.py
```

`markdown_converter.sh` and `extractor.sh` are the active PBS scripts. They use different CUDA module versions and runtime settings; check each script before submission. `job.sh` is a legacy combined script and is not the current workflow.

For initial cluster setup, one-time dependency installation, model download, Docling caching, and PBS diagnostics, see `AQUA_RUNNING_INSTRUCTIONS.md`.

---

## Aqua Running Instructions

The guide below is reproduced from `AQUA_RUNNING_INSTRUCTIONS.md`.

# Running Reaction Extractor on IITM Aqua Cluster

This guide documents the complete setup process for running `rxn_extractor` on the IITM Aqua HPC cluster, including cluster-specific fixes.

---

## 1. Cluster Rules — Read This First

| Aspect                             | Location                                 | Why                                                                                               |
| :--------------------------------- | :--------------------------------------- | :------------------------------------------------------------------------------------------------ |
| **All Files (Code, Venv, Models)** | `~/rxn_extractor/` (50 GB `$HOME` quota) | Code + Python env (~2.5 GB) + model (~9 GB) + Docling models (~1.5 GB) = ~13-15 GB, within quota. |
| **Interactive Setup Tasks**        | Login / Head Node only                   | File editing, `pip install`, `wget`, `qsub`. No GPU here.                                         |
| **Model Inference / Extraction**   | GPU Compute Node via PBS                 | Do not run `python run_batch.py` directly on the login terminal.                                  |

## 2. Transfer Code from Local Machine

Run these from your local machine terminal (WSL/Linux).

### 2.1 Create a Clean Tarball

Exclude local environments, caches, and the large model:

```bash
cd /home/athul/pe_pyrolysis

tar --exclude='rxn_extractor/venv' \
    --exclude='rxn_extractor/.venv' \
    --exclude='rxn_extractor/__pycache__' \
    --exclude='rxn_extractor/*/__pycache__' \
    --exclude='rxn_extractor/models/*.gguf' \
    -czvf rxn_extractor.tar.gz rxn_extractor/
```

### 2.2 Transfer to Aqua via SCP

The destination must include a colon before `~/`:

```bash
scp rxn_extractor.tar.gz <username>@aqua.iitm.ac.in:~/
```

## 3. One-Time Setup on Aqua (Login Node)

Connect to Aqua:

```bash
ssh <username>@aqua.iitm.ac.in
```

### 3.1 Extract the Code

```bash
cd ~
tar -xzvf rxn_extractor.tar.gz
rm rxn_extractor.tar.gz
cd ~/rxn_extractor
```

### 3.2 Download the GGUF Model

```bash
mkdir -p ~/rxn_extractor/models
cd ~/rxn_extractor/models
wget -c "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
cd ~/rxn_extractor
```

### 3.3 Install the Project Python Environment

The cluster's `python385` module lacks OpenSSL support. Use a standalone Python 3.10 runtime instead:

```bash
cd ~
wget https://github.com/astral-sh/python-build-standalone/releases/download/20240224/cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz
tar -xzf cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz
mv python python310
rm cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz

~/python310/bin/python3 -m venv ~/rxn_env
source ~/rxn_env/bin/activate
python -c "import ssl; print('SSL OK:', ssl.OPENSSL_VERSION)"
```

If `pip` does not point into `~/rxn_env`, run:

```bash
python -m ensurepip --upgrade
hash -r
```

## 4. Install `llama-cpp-python` with GPU Support

Aqua's RHEL 7 system has glibc 2.17, so compile `llama-cpp-python` from source. CUDA 11.4 is the compatibility baseline recommended by the original setup notes for the heterogeneous GPU nodes.

### 4.1 Load CUDA 11.4 and Select the Compiler

```bash
deactivate 2>/dev/null
module purge
module load cuda11.4

unset CC CXX CPATH CPLUS_INCLUDE_PATH C_INCLUDE_PATH
export CC=/lfs/sware/gcc9.2.0/bin/gcc
export CXX=/lfs/sware/gcc9.2.0/bin/g++
export CUDA_HOME=/lfs/sware/cuda-11.4
export CUDA_PATH=/lfs/sware/cuda-11.4
export CUDACXX=/lfs/sware/cuda-11.4/bin/nvcc
export PATH=/lfs/sware/cuda-11.4/bin:$PATH
export LD_LIBRARY_PATH=/lfs/sware/cuda-11.4/lib64:/lfs/sware/gcc9.2.0/lib64:$LD_LIBRARY_PATH
```

### 4.2 Configure and Build

```bash
export CMAKE_ARGS="-DGGML_CUDA=on \
  -DCMAKE_C_COMPILER=/lfs/sware/gcc9.2.0/bin/gcc \
  -DCMAKE_CXX_COMPILER=/lfs/sware/gcc9.2.0/bin/g++ \
  -DCMAKE_CUDA_COMPILER=/lfs/sware/cuda-11.4/bin/nvcc \
  -DCMAKE_CUDA_HOST_COMPILER=/lfs/sware/gcc9.2.0/bin/g++ \
  -DCUDA_TOOLKIT_ROOT_DIR=/lfs/sware/cuda-11.4 \
  -DCMAKE_CUDA_FLAGS=-I/lfs/sware/cuda-11.4/include \
  -DGGML_LLAMAFILE=OFF \
  -DGGML_NATIVE=OFF \
  -DGGML_AVX512=OFF"

source ~/rxn_env/bin/activate
pip cache purge
pip uninstall llama-cpp-python -y
pip install llama-cpp-python --no-binary llama-cpp-python --no-cache-dir --verbose 2>&1 | tee /tmp/llama_build_cu114.log
```

Verify CUDA linkage:

```bash
ldd ~/rxn_env/lib/python3.10/site-packages/llama_cpp/lib/libllama.so | grep "libcudart"
```

Install the project's core dependencies:

```bash
pip install pydantic httpx fastapi uvicorn rich python-dotenv pyyaml pandas sqlalchemy openpyxl jinja2
```

## 5. Install Docling for PDF Conversion

### 5.1 Fix the Archiver Path if Pillow Fails to Build

```bash
source ~/rxn_env/bin/activate
export AR=/usr/bin/ar
pip install --only-binary=pillow pillow
```

### 5.2 Install Docling

```bash
export AR=/usr/bin/ar
nohup pip install docling > ~/docling_install.log 2>&1 &
```

Monitor installation with `tail -f ~/docling_install.log`.

### 5.3 Fix Missing `libspatialindex_c.so` if Rtree Fails

```bash
source ~/rxn_env/bin/activate
cd /tmp
wget https://dl.fedoraproject.org/pub/archive/epel/7/x86_64/Packages/s/spatialindex-1.8.5-1.el7.x86_64.rpm
rpm2cpio spatialindex-1.8.5-1.el7.x86_64.rpm | cpio -idmv
cp -a usr/lib64/libspatialindex* ~/rxn_env/lib/
rm -rf usr spatialindex-1.8.5-1.el7.x86_64.rpm
cd ~/rxn_env/lib
ln -sf libspatialindex_c.so.4 libspatialindex_c.so
ln -sf libspatialindex.so.4 libspatialindex.so
export LD_LIBRARY_PATH=$HOME/rxn_env/lib:$LD_LIBRARY_PATH
python -c "import rtree; from docling.document_converter import DocumentConverter; print('Docling and Spatialindex OK')"
```

### 5.4 Cache Docling Models on the Login Node

Compute nodes do not have WAN access. Run conversion once on the login node with a real PDF so Docling's layout and OCR models are cached on shared storage:

```bash
cd ~/rxn_extractor
source ~/rxn_env/bin/activate
export LD_LIBRARY_PATH=$HOME/rxn_env/lib:$LD_LIBRARY_PATH
mkdir -p pdfs markdowns
python -m src.pipeline.pdf_converter
ls -la ~/.cache/huggingface/hub/models--docling-project--docling-layout-heron/snapshots/
```

## 6. Current PBS Workflow

The current workflow uses two separate scripts. Submit conversion first, wait for it to complete, then submit extraction:

```bash
cd ~/rxn_extractor
qsub markdown_converter.sh
qstat -u "$USER"
# After conversion finishes:
qsub extractor.sh
```

Place input PDFs in `~/rxn_extractor/pdfs/`. The conversion script writes Markdown to `markdowns/`; the extractor consumes that Markdown and writes result CSVs to `data/`. The two scripts use different CUDA module versions and runtime settings; check each script before submission.

## 7. Monitor, Cancel, and Retrieve Results

```bash
qstat -u "$USER"
tail -f logs/batch_out.log
tail -f logs/batch_err.log
qdel <job_id>
```

From your local machine, retrieve the results with:

```bash
scp -r <username>@aqua.iitm.ac.in:~/rxn_extractor/data ./aqua_results/
```

## 8. Useful Aqua Diagnostics

```bash
quota -s
qstat -Q
qstat -an
pbsnodes -aS | grep "gpu"
qstat -f <job_id> | grep -E "comment =|Resource_List|queue ="
```

If `reaction.yaml` changes, rebuild generated artifacts from the project environment before submitting extraction:

```bash
source ~/rxn_env/bin/activate
python -m src.builder.cli
```
