# Technical Specification and Architecture Document: Reaction Extractor (`rxn_extractor`)

---

## 1. High-Performance Computing (HPC) Infrastructure: IITM Aqua Cluster

### 1.1 Operating System and Host Environment
* **Distribution:** Red Hat Enterprise Linux (RHEL) Server release 7.6 (Maipo).
* **Linux Kernel:** `3.10.0-957.el7.x86_64`.
* **Standard C Library:** `glibc 2.17`.
  * *Constraint:* `glibc 2.17` was released in 2012. Modern pre-compiled Python binary wheels (such as `manylinux_2_28` or PyPI wheels targeting `glibc >= 2.27`) cannot execute on this host, raising `version GLIBC_2.27 not found`. All native C/C++ extensions containing shared object files (`.so`) must either be compiled natively against host libraries or statically linked.
* **Default Compilers & Dynamic Linkers:**
  * System Default Compiler: GCC 4.8.5 (`/usr/bin/gcc`).
  * Cluster Software Modules: GCC 9.2.0 (`/lfs/sware/gcc9.2.0/bin/gcc`), GCC 8.2.0.
  * System C++ Standard Library: `/lib64/libstdc++.so.6` (supports up to `GLIBCXX_3.4.19`).

### 1.2 Storage Architecture & File Systems
Storage is partitioned across two main Lustre Parallel File System (PFS) mounts connected via high-speed InfiniBand (o2ib):
* **`/lfs` (User Home Directory: `$HOME`):**
  * Quota: 50 GB per user account.
  * Architecture: Lustre distributed metadata and object storage targets (MDT/OST).
  * Characteristics: High throughput for large sequential reads/writes (up to 25 GB/s cluster-wide). High latency for metadata operations (file creation, stat, deletion, small directory traversal).
  * Storage allocation: Code repository, virtual environment (`rxn_env`), and the primary GGUF model weights (~9.0 GB). Total allocation: ~14.5 GB / 50 GB.
* **`/lfs1` (High-Capacity Scratch):**
  * Quota: 500 GB per user account.
  * Designated for bulk datasets, temporary intermediate dumps, and multi-model checkpoints.

### 1.3 Hardware Acceleration & Compute Topography
The compute partition comprises standard compute nodes (`cn001` through `cn280`) and GPU compute nodes (`gpu001` through `gpu027`):
* **GPU Node Specifications:**
  * Accelerator: NVIDIA Tesla V100-PCIE-32GB (and select V100-16GB variants).
  * Microarchitecture: Volta (Compute Capability 7.0, `sm_70`).
  * Memory: 32,510 MiB HBM2 VRAM per card; memory bandwidth: ~900 GB/s.
  * Host CPU per GPU node: Intel Xeon processors providing 32 to 40 logical cores.
  * Host RAM: 188 GB to 192 GB DDR4.
* **Driver and Runtime Heterogeneity:**
  * Kernel Driver: NVIDIA UNIX x86_64 Kernel Module `535.54.03`.
  * Driver Maximum CUDA Support: CUDA 12.2 on select nodes; older driver baselines on other nodes enforce an effective maximum runtime capability of **CUDA 11.4**.
  * Module Availability: `cuda8.0`, `cuda9.2`, `cuda10.0`, `cuda10.1`, `cuda10.2`, `cuda11.2`, `cuda11.4`, `cuda11.5`, `cuda11.7`, `cuda12.1`, `cuda12.2`, `cuda12.4`.

### 1.4 Job Scheduler & Resource Manager
* **Scheduler:** Altair PBS Professional (PBS Pro).
* **Target Queue:** `gpuq`.
* **Resource Specification Syntax:** `#PBS -l select=1:ncpus=8:ngpus=1:mpiprocs=1`.
* **Spooling Behavior:** PBS buffers `stdout` and `stderr` on the compute node's local spool (`/var/spool/pbs/spool/<job_id>.OU` and `<job_id>.ER`) until process completion. Output files specified via `#PBS -o` and `#PBS -e` are only copied back to the Lustre target path upon job exit.
* **Network Isolation:** Compute nodes have no default outbound route to the WAN. Internet access is restricted strictly to the head/login nodes (`aqua.iitm.ac.in`). Compute node processes attempting HTTP/HTTPS handshakes fail with `[Errno -2] Name or service not known`.

---

## 2. Infrastructure-Driven Architectural Decisions

The physical and operational constraints of the Aqua cluster directly governed the system design:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        IITM Aqua Constraints                           │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ No WAN on Compute Nodes  │ Old Host OS/Libs     │ PBS Pro Batch Model  │
│ (Air-gapped GPU nodes)   │ (glibc 2.17, RHEL 7) │ (Non-daemon, queuing)│
└────────────┬─────────────┴──────────┬───────────┴──────────┬───────────┘
             │                        │                      │
             ▼                        ▼                      ▼
┌──────────────────────────┐┌───────────────────┐┌───────────────────────┐
│ Fully Offline Execution  ││ Standalone Runtimes││ In-Process LLM       │
│ • Local Docling caching  ││ & Native Compiles  ││ Execution            │
│ • HF_HUB_OFFLINE=1       ││ • Python 3.10 AST  ││ • llama-cpp-python   │
│ • Static GGUF binaries   ││ • CUDA 11.4 link   ││ • Direct memory-map  │
│                          ││ • Custom libpath   ││ • No background HTTP │
└──────────────────────────┘└───────────────────┘└───────────────────────┘
```

1. **In-Process Inference via `llama-cpp-python` vs. Client-Server Architecture (Ollama / vLLM):**
   * *Rejected:* Running Ollama or vLLM requires a persistent daemon, active local networking loopbacks, port binding inside container namespaces, and systemd/service management unsupported under standard PBS batch slots.
   * *Adopted:* In-process dynamic linking using `llama-cpp-python`. The C++ core (`llama.cpp`) loads directly into the Python process memory space, maps GGUF model tensors straight to the V100 GPU via CUDA driver APIs, and requires zero background daemons or socket bindings.
2. **Runtime Toolchain Bootstrapping:**
   * The cluster's `python385` module was compiled without OpenSSL headers, causing `import ssl` to fail and rendering `pip` inoperable.
   * *Resolution:* Deployment of a standalone, self-contained Python 3.10.13 runtime (`cpython-3.10.13+20240224-x86_64-unknown-linux-gnu`) containing statically linked OpenSSL 1.1.1.
3. **CUDA 11.4 Baseline Compilation:**
   * Compiling against `cuda12.1` caused dynamic initialization failures on GPU nodes running older drivers (`CUDA driver version is insufficient for CUDA runtime version`).
   * *Resolution:* Cross-node compatibility enforced by compiling `llama-cpp-python` against `cuda11.4` and GCC 9.2.0, with runtime explicit linkage to `libcudart.so.11.0` and `libstdc++.so.6` (providing `GLIBCXX_3.4.25`).
4. **Offline Layout Model Pre-Caching:**
   * Docling depends on vision-transformer weights (`docling-project/docling-layout-heron`) and OCR models.
   * *Resolution:* Execution of a single bootstrap run on the login node (which has WAN access) to download models into `~/.cache/huggingface/hub/`. Compute jobs run with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, reading weights directly from Lustre storage.

---

## 3. Technology Stack and Dependency Specifications

| Component | Library / Binary | Version Constraint | Execution Context | Functional Role |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime** | CPython | 3.10.13 | User space (`~/python310`) | Base runtime environment |
| **Inference Engine** | `llama-cpp-python` | 0.3.36 | Python / C++ Ctypes | Direct GGUF loading, CUDA Graph dispatch |
| **CUDA Toolchain** | NVIDIA CUDA Toolkit | 11.4.4 (`nvcc`) | Module (`cuda11.4`) | Compilation of GGML CUDA kernels |
| **C++ Toolchain** | GNU Compiler Collection | 9.2.0 (`gcc`/`g++`) | Module (`gcc9.2.0`) | Host compilation, ISO C++17 support |
| **PDF Conversion** | `docling` | $\ge 2.0.0$ | Python | PDF parsing, document layout reconstruction |
| **Spatial Indexing**| `rtree` / `spatialindex` | 1.8.5 / 1.4.1 | Native `.so` / Python | 2D bounding-box hierarchy resolution |
| **Data Validation** | `pydantic` | $\ge 2.5.0$ | Python | Static type validation, schema enforcement |
| **Meta-Compilation**| `jinja2`, `pyyaml` | $\ge 3.1.0$, $\ge 6.0$ | Python | Code generation from declarative YAML |
| **Storage & I/O** | `pandas`, `sqlalchemy` | $\ge 2.1.0$, $\ge 2.0.0$ | Python | Tabular aggregation, SQLite/CSV persistence |

---

## 4. Software Architecture and Pipeline Execution Flow

```
                      reaction.yaml (Declarative Schema)
                                      │
                                      ▼
                        src/builder/cli.py (Builder)
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                    ▼
       src/auto_generated/   src/auto_generated/   src/auto_generated/
            models.py             config.py             prompts/*.md
                 │                    │                    │
═════════════════╪════════════════════╪════════════════════╪═════════════════
                 │         PIPELINE EXECUTION       │
                 ▼                    ▼                    ▼
          pdfs/*.pdf ──► [Step 1: pdf_converter.py] ──► markdowns/*.md
                                                           │
                                                           ▼
                                                [Step 2: FilterAgent]
                                                (Abstract Slice: 4k chars)
                                                           │
                                        ┌──────────────────┴──────────────────┐
                                        ▼                                     ▼
                                  [Irrelevant]                           [Relevant]
                                        │                                     │
                             Mark in DB & Skip Paper                          ▼
                                                                    [Step 3: ParserAgent]
                                                                  (Instruction-First Prompt)
                                                                              │
                                                                              ▼
                                                                     ParserOutput Schema
                                                                 (N Experiments Discovered)
                                                                              │
                                                                              ▼
                                                                   [Step 4: Extractor Loop]
                                                                (Surgical Pointer Insertion)
                                                                              │
                                                      ┌───────────────┬───────┴───────┬───────────────┐
                                                      ▼               ▼               ▼               ▼
                                                   Catalyst       Conditions     Performance       Metadata
                                                      └───────────────┼───────────────┴───────────────┘
                                                                      │
                                                                      ▼
                                                          [Step 5: Normalizer]
                                                          (Unit Mapping & Float Midpoints)
                                                                      │
                                                                      ▼
                                                          [Step 6: Validator]
                                                          (Range Bounds & Confidence Score)
                                                                      │
                                                                      ▼
                                                          [Step 7: CsvStore DB]
                                                          (Atomic Checkpoint & CSV Commit)
```

### 4.1 Detailed Execution Phases

#### Phase 1: PDF Conversion (`src/pipeline/pdf_converter.py`)
1. Traverses the directory `pdfs/` for all files matching `*.pdf`.
2. Inspects `markdowns/` for corresponding `{stem}.md` files. If an existing markdown file is present and `--force` is not asserted, skips processing immediately (idempotent validation).
3. Instantiates Docling's `DocumentConverter`.
4. Reads raw PDF byte streams, applies visual layout detection models (`docling-layout-heron`) to isolate tables, reading order, and body text, and produces a structured markdown document.
5. Writes markdown output directly to disk per-file to prevent data loss in the event of job timeout.

#### Phase 2: Batch Management & Abstract Pre-Filtering (`src/pipeline/batch_manager.py`, `src/agents/filter_agent.py`)
1. Reads all available markdown files from `markdowns/`.
2. Slices the initial 4,000 characters of the document (capturing Title, Abstract, and Introduction).
3. Invokes `FilterAgent` with the system directive comparing content against `TARGET_REACTION` from `reaction.yaml`.
4. The LLM executes inference and outputs structured JSON: `{"is_relevant": bool, "reason": str}`.
5. If `is_relevant == False`, the paper is registered in `papers.csv` with status `irrelevant`, recording the rejection justification, and execution terminates for that paper in ~3 seconds.

#### Phase 3: Experiment Enumeration (`src/agents/parser_agent.py`)
1. Ingests the complete markdown text of relevant papers.
2. Formats the instruction-first prompt using `PARSER_USER_TEMPLATE` and `src/auto_generated/prompts/parser.md`.
3. Dispatches the prompt to `LLMClient.extract()`.
4. The LLM returns a structured JSON payload conforming to `ParserOutput`:
   * Identifies total experiments ($N$).
   * Extracts catalyst labels, reactants, operating temperatures, pressures, key sections, and locator descriptions per experiment.
5. Updates `papers.csv` status to `parsed`, recording total experiment counts.

#### Phase 4: Sub-Domain Extraction (`src/agents/extractor.py`)
1. Iterates sequentially from experiment $1$ to $N$.
2. For each experiment, generates a localized contextual prefix block:
   ```text
   ============================================================
   TARGET EXPERIMENT: #i of N
   ============================================================
   Description    : <brief_description>
   Catalyst/System: <catalyst_name>
   Reactant       : <reactant>
   Temperature    : <temperature>
   Pressure       : <pressure>
   Paper location : <key_section>
   ============================================================
   ```
3. Sequentially executes queries across the four configured sub-domains:
   * `catalyst`: Catalyst composition, support material, active metals, surface areas.
   * `conditions`: Reactor configuration, temperature, pressure, space velocity, time-on-stream.
   * `performance`: Ethylene conversion percentage, product selectivities ($C_6, C_8, C_{10}, C_{12}$), reaction rates.
   * `metadata`: Publication year, DOI, operational notes.
4. Each extraction target is constrained by its respective Pydantic model (`src/auto_generated/models.py`).

#### Phase 5: Normalization and Quality Validation (`src/core/normalizer.py`, `src/core/validator.py`)
1. `normalizer.py` iterates over every extracted key-value pair. If raw units differ from target canonical units (e.g., input: `2.5 MPa`, target: `atm`), it applies deterministic lambda conversion factors defined in `UNIT_CONVERSIONS`.
2. String ranges (e.g., `"150-200"`) are converted to arithmetic midpoints (`175.0`), appending `_normalization_warning` to the dictionary.
3. `validator.py` evaluates normalized numerical values against `VALIDATION_BOUNDS`:
   * Verifies if values reside within physical operational boundaries (`min` / `max`).
   * Evaluates custom cross-field validation rules (e.g., selectivity summations).
   * Computes deterministic integer confidence scores ($1$ to $5$) based on data completeness, bound compliance, and normalization status.

#### Phase 6: Persistence Layer (`src/db/database.py`)
1. Commits normalized and validated experiment dictionaries to SQLite (`rxn_extractor.db`) and flushes records to persistent tabular CSV files:
   * `data/papers.csv`: Paper processing telemetry, relevance status, execution errors.
   * `data/experiments.csv`: Fully denormalized reaction records containing all extracted, normalized, and validated metrics.
   * `data/batch_jobs.csv`: High-level execution metrics, elapsed runtimes, and completion rates.

---

## 5. Mathematical & Algorithmic Analysis of KV Caching

In transformer-based autoregressive inference, Key-Value (KV) caching eliminates the redundant recalculation of key and value self-attention tensors for preceding tokens:

$$K_i = W_K \cdot x_i, \quad V_i = W_V \cdot x_i$$
$$A = \text{softmax}\left(\frac{Q K^T}{\sqrt{d_k}}\right) V$$

```
Sequence Layout A (Instruction-First Framing — Current Production Baseline):
┌───────────────────────────┬───────────────────────────────────────────┐
│ Dynamic Directives (500t) │ Full Paper Context (12,000 to 16,000t)    │
└───────────────────────────┴───────────────────────────────────────────┘
▲ Token 0 changes on every sub-domain call (catalyst != conditions != performance).
Result: Complete KV cache invalidation. Recomputes all 15,000 tokens every call.

Sequence Layout B (Prefix Inversion — Evaluated for KV Cache Reuse):
┌───────────────────────────────────────────┬───────────────────────────┐
│ Full Paper Context (12,000 to 16,000t)    │ Dynamic Directives (500t) │
└───────────────────────────────────────────┴───────────────────────────┘
▲ Token 0 to 15,000 is static across all calls for this paper.
Result: 15,000 tokens cached in VRAM once. Subsequent calls compute only 500 tokens.
Empirical Result: Attention degradation ("Lost in the Middle"). 57% recall reduction.
```

### 5.1 Prefix Invalidation Boundary Condition
KV cache reuse requires an identical token prefix starting strictly at **Index 0**:

$$\text{Prefix Match} = \arg\max_L \left\{ \forall j < L : t_j^{\text{current}} == t_j^{\text{cached}} \right\}$$

If token $t_0$ diverges, $L = 0$. The entire KV tensor cache is invalidated, requiring full forward-pass evaluation of the sequence.

### 5.2 Architectural Trade-Off Analysis

1. **Current Pipeline Layout (Sequence Layout A):**
   * *Order:* `[System Prompt & Schema (Dynamic)]` $\rightarrow$ `[Pointer Header (Dynamic)]` $\rightarrow$ `[Paper Markdown (Static)]`.
   * *Prefix Length:* $L = 0$.
   * *Computational Cost per Query:* Full prefill of $12,000 \text{ to } 16,000$ tokens on every sub-domain call.
   * *Accuracy Metric:* 100% extraction recall on broad experiment discovery (21 out of 21 test experiments detected).
2. **Inverted Prefix Layout (Sequence Layout B):**
   * *Order:* `[Paper Markdown (Static)]` $\rightarrow$ `[System Prompt & Schema (Dynamic)]`.
   * *Prefix Length:* $L \approx 12,000 \text{ to } 16,000$ tokens.
   * *Computational Cost per Query:* Prefill evaluated once per paper; subsequent sub-domain calls evaluate only the $\sim 500$ instruction tokens.
   * *Accuracy Metric:* Extraction recall collapsed from 21 experiments to 9 experiments (57.1% failure rate).
3. **Root Cause of Accuracy Collapse:**
   Small-to-medium open-weights architectures (specifically 3B to 14B parameter models) suffer from the **"Lost in the Middle"** attention deficit. Attention weights concentrate heavily on the initial prompt tokens and the final generated tokens. When instruction constraints are placed after 15,000 tokens of raw document text, the cross-entropy attention signal for schema compliance degrades significantly, causing the model to omit experimental blocks.
4. **Engineering Resolution:**
   Precision and recall in chemical databases supersede raw compute optimization. The pipeline explicitly rejects global prefix caching on broad parsing to ensure complete data recovery. For sub-domain extraction, `llama-cpp-python` maintains native context structures, leveraging CUDA graph execution for rapid single-batch autoregression.

---

## 6. Context Sizing & VRAM Memory Budget (Qwen2.5-14B on Tesla V100 32GB)

### 6.1 Parameter Sizing & Quantization Configuration
* **Base Architecture:** `Qwen2.5-14B-Instruct`.
* **Parameter Count:** 14.77 Billion.
* **Quantization Scheme:** `Q4_K_M` (4-bit medium symmetric quantization with K-quants).
  * Weight memory footprint: **8.99 GB**.
  * Attention layers: 48 transformer blocks.
  * Attention heads: 40 Query heads, 8 Key/Value heads (Grouped Query Attention — GQA, ratio 5:1).
  * Hidden dimension: 5,120; Head dimension: 128.

### 6.2 Analytical VRAM Allocation Equation

$$\text{VRAM}_{\text{total}} = M_{\text{weights}} + M_{\text{KV-cache}}(C) + M_{\text{CUDA-runtime}} + M_{\text{activation}}(B, C)$$

Where $C$ is context size (`NUM_CTX`), and $B$ is batch size ($B=1$).

1. **KV Cache Footprint Formula (GQA):**

$$M_{\text{KV}} = 2 \times N_{\text{layers}} \times N_{\text{KV\_heads}} \times D_{\text{head}} \times P_{\text{bytes}} \times C$$

For $C = 32,768$ tokens, with 16-bit float representation ($P_{\text{bytes}} = 2$):

$$M_{\text{KV}} = 2 \times 48 \times 8 \times 128 \times 2 \times 32,768 = 6,442,450,944 \text{ Bytes} \approx \mathbf{6.00 \text{ GB}}$$

2. **Total Allocation Table:**

| Component | VRAM Consumption (16k Context) | VRAM Consumption (32k Context - Baseline) | Allocation Status |
| :--- | :--- | :--- | :--- |
| **Model Tensors (`Q4_K_M`)** | 8.99 GB | 8.99 GB | Static (VRAM) |
| **KV Cache Buffer** | 3.00 GB | 6.00 GB | Dynamic (Pre-allocated) |
| **CUDA Driver & Scratchpad** | 1.10 GB | 1.10 GB | Static |
| **Activation Tensors ($B=1$)** | 1.80 GB | 2.50 GB | Peak generation buffer |
| **Total VRAM Utilized** | **14.89 GB** | **18.59 GB** | **Within 32 GB Bounds** |
| **Headroom on V100-32GB** | 17.61 GB | 13.91 GB | Safe |
| **Headroom on V100-16GB** | 0.81 GB | **-2.89 GB (OOM Spill to CPU)**| **Fatal on 16GB cards** |

*Hardware Guard:* On nodes equipped with 32 GB VRAM, the 32k context baseline operates with ~13.9 GB of surplus headroom. On 16 GB cards, setting `NUM_CTX=32768` causes partial offloading (26 layers on GPU, 22 on CPU), reducing token throughput by 98.7% (dropping from ~45 tokens/s to ~0.6 tokens/s).

### 6.3 Defensive Context Overflow Guard
In `src/core/llm_client.py`, dynamic token estimation enforces a safety ceiling:

$$\text{Max Prompt Tokens} = \text{NUM\_CTX} - 2,048$$

If estimated tokens exceed this threshold, the user text is mathematically truncated at character index $L_{\text{cutoff}}$ and appended with `[... truncated by extractor to fit context window ...]`. This prevents C-level assertion aborts inside `llama.cpp`.

---

## 7. Output Schema and Data Definitions

The pipeline generates three primary CSV relational structures under `data/`:

### 7.1 `papers.csv` (Document Tracking & Filter Telemetry)
* `paper_id` (`int`, Primary Key): Sequential unique identifier.
* `filename` (`str`): File name of the source markdown file.
* `title` (`str`): Extracted research title.
* `status` (`enum`): `pending` | `irrelevant` | `parsed` | `failed`.
* `is_relevant` (`bool`): Abstract relevance determination.
* `relevance_reason` (`str`): Justification generated by `FilterAgent`.
* `total_experiments` (`int`): Count of validated experiments identified.
* `processed_at` (`iso8601`): UTC timestamp.

### 7.2 `experiments.csv` (Extracted Chemical Data)
* **Identity:**
  * `experiment_id` (`int`, Primary Key): Global identifier.
  * `paper_id` (`int`, Foreign Key): Link to `papers.csv`.
  * `experiment_number` (`int`): Local experiment index within the paper.
  * `experiment_label` (`str`): Author's designation (e.g., "Run 3b", "Table 2, Entry 4").
* **Catalyst Sub-Domain:**
  * `catalyst_name` (`str`): Full catalyst formulation.
  * `support_material` (`str`): Solid support (e.g., "H-ZSM-5", "SiO2-Al2O3").
  * `active_metal` (`str`): Catalytic metal (e.g., "Ni", "Cr", "Ti").
  * `metal_loading_wt_percent` (`float`): Loading normalized to wt%.
  * `surface_area` (`float`): BET surface area normalized to $m^2/g$.
  * `pore_volume` (`float`): Pore volume normalized to $cm^3/g$.
* **Reaction Conditions Sub-Domain:**
  * `reactor_type` (`str`): "fixed-bed", "autoclave", "semi-batch", "CSTR".
  * `temperature` (`float`): Reaction temperature normalized strictly to **Celsius** ($^\circ\text{C}$).
  * `pressure` (`float`): Total pressure normalized strictly to **atm**.
  * `space_velocity` (`float`): Space velocity normalized to $h^{-1}$ (WHSV/GHSV).
  * `testing_time` (`float`): Time-on-stream normalized to **hours**.
* **Performance Metrics Sub-Domain:**
  * `ethylene_conversion` (`float`): Substrate conversion normalized to $\%$.
  * `c8_c16_selectivity` (`float`): Oligomer selectivity fraction normalized to $\%$.
  * `isomers_selectivity` (`float`): Branched vs linear fraction ($\%$).
  * `yield` (`float`): Direct product yield ($\%$).
  * `reaction_rate` (`float`): Normalized to $mol \cdot g^{-1} \cdot h^{-1}$.
  * `turnover_frequency` (`float`): Normalized to $s^{-1}$.
* **Data Quality & Traceability:**
  * `confidence_score` (`int`): Deterministic validation score ($1$ = lowest, $5$ = highest).
  * `_normalization_warning` (`str`): Audit log of approximate inputs, missing units, or midpoint conversions.
  * `key_section` (`str`): Section/table citation from source text.

### 7.3 `batch_jobs.csv` (Cluster Execution Telemetry)
* `job_id` (`str`): Unique batch run execution identifier.
* `total_papers` (`int`): Papers processed in session.
* `successful_extractions` (`int`): Experiments passing schema validation.
* `elapsed_seconds` (`float`): End-to-end execution runtime.
* `average_tokens_per_second` (`float`): Real-time inference generation throughput.

---

## 8. Extensibility: Adapting to Alternate Chemical Reactions

The system uses an autonomous compiler architecture. Extending or altering the extraction domain requires no manual modification of Python agents, AST models, or prompt definitions:

```
┌────────────────────────────────────────────────────────┐
│ 1. Edit reaction.yaml                                  │
│    • Define target_reaction string                     │
│    • Specify sub_domains, fields, types                │
│    • Define validation_bounds & unit_conversions       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Run Meta-Compiler                                   │
│    $ python -m src.builder.cli --domain reaction.yaml  │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐ ┌────────────────────────────┐
│ Auto-Generated Code:    │ │ Auto-Generated Prompts:    │
│ • src/auto_generated/   │ │ • src/auto_generated/      │
│   models.py             │ │   prompts/parser.md        │
│ • src/auto_generated/   │ │ • src/auto_generated/      │
│   config.py             │ │   prompts/{sub_domain}.md  │
└─────────────────────────┘ └────────────────────────────┘
```

### 8.1 Modification Procedure
1. **Modify `reaction.yaml`:**
   * Update the `target_reaction` string (e.g., `"pyrolysis of polyethylene to liquid hydrocarbons"`).
   * Modify or add sub-domains under `sub_domains:` (e.g., `pyrolysis_conditions`, `feedstock`, `liquid_products`).
   * Define field keys, data types (`float`, `str`), physical units, and permitted conversion pairings.
   * Define numerical acceptance intervals under `validation_bounds`.
2. **Execute the Code Generator:**
   ```bash
   python -m src.builder.cli --domain reaction.yaml
   ```
3. **Internal Compilation Artifacts:**
   * The AST builder (`model_generator.py`) generates fully typed Pydantic models in `src/auto_generated/models.py`.
   * The configuration builder (`config_generator.py`) compiles conversion matrices into executable lambdas in `src/auto_generated/config.py`.
   * The prompt builder (`prompt_generator.py`) produces structured system prompts under `src/auto_generated/prompts/` injecting few-shot rubrics and JSON constraints.
4. **Deploy Execution:**
   Submit `job.sh` via PBS. The extraction orchestrator dynamically introspects the newly compiled modules without source code alterations.

---

## 9. Model Correctness, Evaluation, and Failure Modes

### 9.1 Evaluation of Qwen2.5-14B-Instruct-Q4_K_M
The Qwen2.5-14B parameter model was selected over smaller variants (e.g., Llama-3.2-3B, Qwen2.5-3B, or 7B architectures) based on empirical evaluations:
* **JSON Schema Adherence:** Native instruction-tuning produces robust JSON grammar compliance when operating under `response_format={"type": "json_object"}`. Smaller 3B models frequently emitted unescaped markdown text, non-standard quotes, or trailing prose that aborted JSON decoders.
* **Complex Tabular Parsing:** Chemical reaction data is heavily concentrated within multi-column, multi-row dense tables. Qwen2.5-14B exhibits superior spatial comprehension over Markdown-formatted tables, correctly correlating row catalyst formulations with column conversion yields across page boundaries.
* **Context Window Fidelity:** The model natively supports up to 128k context lengths via RoPE (Rotary Position Embeddings) scaling, ensuring minimal perplexity degradation across our target 32,768-token operating window.

### 9.2 Quantization Precision Impact (`Q4_K_M`)
* **Weight Distortion:** 4-bit medium K-quantization (`Q4_K_M`) introduces negligible loss in semantic text classification and language parsing compared to FP16 baselines.
* **Numerical Entity Preservation:** Floating-point precision loss is not observed in numerical extraction; numbers are processed as discrete text tokens rather than continuous floating-point weights. The model outputs token sequences representing numbers (e.g., `"2"`, `"."`, `"5"`), preserving the exact digits present in the source literature.

### 9.3 Known Failure Modes and Mitigation Systems

```
┌─────────────────────────────────┬─────────────────────────────────┐
│ Observed Failure Mode           │ Mitigation Architecture         │
├─────────────────────────────────┼─────────────────────────────────┤
│ Schema Mismatch / Missing Keys  │ Temperature Ladder Retry        │
│ (Model emits partial keys)      │ (0.6 -> 0.7 -> 0.8)             │
├─────────────────────────────────┼─────────────────────────────────┤
│ Malformed JSON Tokens           │ 4-Tier JSON Parser Recovery     │
│ (Markdown fences, escapes)      │ (Regex, strip, brace discovery) │
├─────────────────────────────────┼─────────────────────────────────┤
│ Null Confidence Scores          │ None-Safe Math Sanitization     │
│ (None emitted for missing data) │ (Filters None before min())     │
├─────────────────────────────────┼─────────────────────────────────┤
│ Unit Ambiguity / Range Outputs  │ Deterministic Range Midpoint &  │
│ (e.g. "100-150 bar")            │ _normalization_warning Tag      │
├─────────────────────────────────┼─────────────────────────────────┤
│ Context Overflow (>32k tokens)  │ Dynamic Safety Truncation       │
│                                 │ (Ceiling: NUM_CTX - 2048)       │
└─────────────────────────────────┴─────────────────────────────────┘
```

1. **Schema Mismatch Mitigation (Temperature Ladder Protocol):**
   * If the LLM generates a JSON response that fails Pydantic schema validation or lacks required root keys, `LLMClient` catches the `ValidationError`.
   * It increments the sampling temperature:
     $$\text{temp}_{k} = \text{temp}_0 + k \cdot \Delta \text{temp} \quad (0.6 \rightarrow 0.7 \rightarrow 0.8)$$
   * Retries execution up to `MAX_RETRIES=3` to allow alternative stochastic sampling paths.
2. **4-Tier JSON Parsing Recovery:**
   * Level 1: Native `json.loads(text)` invocation.
   * Level 2: Extraction of code content wrapped in markdown fences: ```` ```json ... ``` ````.
   * Level 3: Regex boundary isolation searching between first `{` and last `}`.
   * Level 4: Control character sanitization (removing unescaped tabs, newlines inside string literals).
3. **Null-Safe Aggregation (`validator.py`):**
   * If sub-domain agents return `None` for unmeasured properties, confidence calculation avoids `TypeError` exceptions by filtering null primitives before evaluating mathematical minima:
     ```python
     valid_scores = [s for s in scores if s is not None]
     overall_confidence = min(valid_scores) if valid_scores else 1
     ```
4. **Physical Bounds Outlier Handling:**
   * Extraction of physically impossible values (e.g., Conversion = `140%`, Temperature = `-300 °C`) does not abort the batch. The value is logged as an invalid bound, and the confidence rating is downgraded to `1`, alerting downstream consumers that the datapoint requires human verification.
