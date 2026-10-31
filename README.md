# rxn_extractor

`rxn_extractor` turns research papers into structured, experiment-level reaction data. A YAML domain definition describes the target reaction, extraction fields, units, and validation rules. The builder compiles that definition into Pydantic models, prompts, and configuration. The batch pipeline then finds experiments in paper Markdown, extracts the configured fields with a local Qwen GGUF model, normalizes values, validates them, and records the results in CSV files.

The Aqua branch runs inference in-process with `llama-cpp-python` against `models/Qwen2.5-14B-Instruct-Q4_K_M.gguf`; it does not use Ollama or a separate model server. PBS scripts run PDF conversion and extraction as separate GPU jobs.

## Project Tree

```text
rxn_extractor/
├── reaction.yaml                  # Active reaction/domain definition
├── domains/
│   └── example_reaction.yaml      # Example schema
├── pdfs/                          # Source PDF papers
├── markdowns/                     # Docling-converted papers; batch input
├── models/
│   └── Qwen2.5-14B-Instruct-Q4_K_M.gguf
├── data/                          # CSV results and review data
├── checkpoints/                   # Batch resume state
├── logs/                          # PBS stdout/stderr targets
├── run_batch.py                   # Batch extraction entry point
├── markdown_converter.sh          # PBS PDF-to-Markdown job
├── extractor.sh                   # PBS Markdown extraction job
├── job.sh                         # Legacy combined job; not current workflow
├── start.sh                       # Legacy local wrapper; not current Aqua workflow
├── AQUA_RUNNING_INSTRUCTIONS.md   # Aqua setup and operations guide
├── project.md                     # Detailed architecture and technical notes
├── config/
│   └── settings.py                # Runtime settings
└── src/
    ├── builder/                   # Compile reaction.yaml into generated artifacts
    ├── auto_generated/            # Models, config, prompts, and review UI
    ├── agents/                    # Filtering, experiment parsing, extraction
    ├── core/                      # Local LLM client, normalization, validation
    ├── pipeline/                  # PDF conversion, file reading, batch control
    ├── db/                        # CSV persistence
    └── api/                       # Review dashboard API
```

## Basic Input and Output

### Inputs

The domain definition is `reaction.yaml`. It identifies the reaction and the Markdown input directory, then declares extraction sub-domains and fields. For example, the active schema includes catalyst properties, reaction conditions, catalytic performance, and paper metadata:

```yaml
domain_name: "ethylene_conversion"
target_reaction: "oligomerization of ethylene to produce C6-C12 olefins"
input_markdown_dir: "markdowns/"
sub_domains:
  - name: "conditions"
    fields:
      - name: "temperature"
        type: "range"
        target_unit: "Celsius"
      - name: "pressure"
        type: "float"
        target_unit: "atm"
```

This is a shortened illustration; use the complete schema in `reaction.yaml`. Put source PDFs in `pdfs/` for conversion, or provide converted `.md` papers in `markdowns/` for extraction. PDF conversion writes matching Markdown files to `markdowns/`; the extractor consumes Markdown, not PDFs.

If the schema changes, compile it before extraction:

```bash
source ~/rxn_env/bin/activate
python -m src.builder.cli --domain reaction.yaml
```

The generated models, validation/conversion config, prompts, and UI are written under `src/auto_generated/`. Generated files should be rebuilt from the YAML rather than edited by hand.

### Outputs

The batch pipeline writes these files under `data/`:

| File              | Contents                                                                       |
| ----------------- | ------------------------------------------------------------------------------ |
| `papers.csv`      | Paper identifiers, paths, processing status, and errors                        |
| `experiments.csv` | One row per extracted experiment, with confidence and validation/review fields |
| `batch_jobs.csv`  | Batch-level processing status and counts                                       |
| `corrections.csv` | Human review corrections, when made through the review workflow                |

In `experiments.csv`, the `data` column contains a JSON-encoded object with the extracted values grouped by sub-domain. A simplified record looks like this:

```json
{
  "paper_identifier": "sample-paper.md",
  "experiment_number": 1,
  "data": {
    "catalyst": { "catalyst_name": "Ni/Al2O3", "surface_area": 145.0 },
    "conditions": { "temperature": 250.0, "pressure": 1.0 },
    "performance": { "ethylene_conversion": 62.5 }
  },
  "overall_confidence": 4,
  "validation_status": "...",
  "needs_review": true
}
```

The exact fields inside `data` follow the currently compiled domain schema. The CSV store creates its files on demand in `data/` (or in the directory selected by `DATA_DIR`). Batch resume state is stored in `checkpoints/latest.json`.

## Running on Aqua

The current Aqua workflow uses PBS jobs, not `start.sh`:

1. Place PDFs in `pdfs/`. If the schema has changed, run the builder with the project environment before submitting extraction.
2. Submit PDF conversion with `qsub markdown_converter.sh` and wait for that job to finish.
3. Submit extraction with `qsub extractor.sh`.
4. Monitor jobs with `qstat -u "$USER"`; inspect `logs/batch_out.log` and `logs/batch_err.log` for output.
5. Retrieve the resulting CSV files from `data/`.

`markdown_converter.sh` converts PDFs to Markdown; `extractor.sh` processes Markdown and writes extraction records. They are separate jobs so extraction can start after conversion is complete. `job.sh` is currently out of date; the intended combined job will run the conversion stage first and then the extraction stage in sequence. The two current scripts also have distinct CUDA/runtime settings, so use the submitted scripts as the source of truth for the current setup.

For initial cluster setup, dependencies, model caching, PBS monitoring, and troubleshooting, see the Aqua guide appended below.

## Aqua Running Instructions

The Aqua setup and operations guide below is adapted from `AQUA_RUNNING_INSTRUCTIONS.md` to reflect the current branch workflow. The source file is unchanged; its older combined `job.sh` submission example is not presented as the current run path.

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

## 6. Current PBS Workflow on This Branch

The current workflow uses two scripts. Submit conversion first, wait for it to complete, then submit extraction:

```bash
cd ~/rxn_extractor
qsub markdown_converter.sh
qstat -u "$USER"
# After conversion finishes:
qsub extractor.sh
```

The checked-in `job.sh` is not current; the intended combined job should run the conversion stage followed by extraction in one PBS job. Check the two active scripts for their current module, library, and offline settings before submission.

Place input PDFs in `~/rxn_extractor/pdfs/`. The conversion script writes Markdown to `markdowns/`; the extractor consumes that Markdown and writes result CSVs to `data/`.

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
python -m src.builder.cli --domain reaction.yaml
```
