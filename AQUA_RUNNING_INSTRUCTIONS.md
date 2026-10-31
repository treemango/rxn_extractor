# Running Reaction Extractor on IITM Aqua Cluster

This guide documents the **complete, battle-tested** setup process for running `rxn_extractor` on the IITM Aqua HPC cluster, including all non-obvious fixes discovered during the initial setup.

---

## 1. Cluster Rules — Read This First

| Aspect | Location | Why |
| :--- | :--- | :--- |
| **All Files (Code, Venv, Models)** | `~/rxn_extractor/` (50 GB `$HOME` quota) | Code + Python env (~2.5 GB) + model (~9 GB) + Docling models (~1.5 GB) = ~13-15 GB, well within quota. |
| **Interactive Setup Tasks** | Login / Head Node only | File editing, `pip install`, `wget`, `qsub`. No GPU here. |
| **Model Inference / Extraction** | GPU Compute Node via PBS | **NEVER run `python run_batch.py` directly on the login terminal.** |

---

## 2. Step 1: Transfer Code from Local Machine

Run these from your **local machine** terminal (WSL/Linux):

### 2.1 Create a Clean Tarball (Exclude Local Caches and Models)
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
> **Critical:** The destination must have a colon `:` before `~/`. Without the colon, SCP silently creates a local file instead of transferring!

```bash
# CORRECT — note the :~/  at the end
scp rxn_extractor.tar.gz <username>@aqua.iitm.ac.in:~/

# WRONG — missing colon, does nothing useful
scp rxn_extractor.tar.gz <username>@aqua.iitm.ac.in~/
```

---

## 3. Step 2: One-Time Setup on Aqua (Login Node)

SSH into Aqua:
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
Download the ~9 GB model directly into the project. Large sequential file downloads are fast on Lustre/Aqua:
```bash
mkdir -p ~/rxn_extractor/models
cd ~/rxn_extractor/models

wget -c "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf"

cd ~/rxn_extractor
```
> **Note:** `venv` creation and `pip install` take 2–10 minutes on Lustre because they create thousands of small files. Large file downloads (like this model) are fast. This is normal Lustre behavior — not an error.

---

## 4. Step 3: Set Up the Python Environment

> **Why not use `module load python385`?**
> The `python385` module was compiled without OpenSSL support. This means Python 3.8.5 on Aqua **cannot make HTTPS requests**, so `pip install` fails with `SSL module not available`. We use a standalone portable Python 3.10 instead.

### 4.1 Download and Extract Standalone Python 3.10
```bash
cd ~
wget https://github.com/astral-sh/python-build-standalone/releases/download/20240224/cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz

tar -xzf cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz
mv python python310
rm cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz
```

### 4.2 Create Virtual Environment Using Python 3.10
```bash
~/python310/bin/python3 -m venv ~/rxn_env
source ~/rxn_env/bin/activate
```

### 4.3 Verify Python and SSL Are Working
```bash
which python          # Must show ~/rxn_env/bin/python — NOT /usr/bin/python
python -c "import ssl; print('SSL OK:', ssl.OPENSSL_VERSION)"
pip --version         # Must show pip pointing to ~/rxn_env/bin/pip
```
If `which pip` still shows `/usr/bin/pip`, run:
```bash
python -m ensurepip --upgrade
hash -r
```

---

## 5. Step 4: Install `llama-cpp-python` with GPU (CUDA 11.4) Support

This is the most complex step. Aqua's RHEL 7 system has glibc 2.17, which is too old for pre-built binary wheels. We must **compile from source**. 

> **CRITICAL CLUSTER DISCOVERY — CUDA 11.4 Compatibility:**
> * Aqua's GPU nodes are heterogeneous: some nodes have NVIDIA drivers supporting up to CUDA 12.2, while other GPU nodes only support **CUDA 11.4**!
> * If you compile against CUDA 12.1 runtime, your job will fail whenever PBS assigns it to a CUDA 11.4 node (`ggml_cuda_init: failed to initialize CUDA: CUDA driver version is insufficient for CUDA runtime version`).
> * **CUDA 11.4 runtime is backwards-compatible across 100% of Aqua's GPU nodes.** Compiling against CUDA 11.4 guarantees GPU acceleration on all nodes.

### 5.1 Purge All Modules and Load CUDA 11.4

`module purge` is critical to avoid inheriting stale CUDA 10.1 include paths from the default login environment:
```bash
deactivate 2>/dev/null
module purge
module load cuda11.4

# Verify nvcc is 11.4
nvcc --version   # Must say "release 11.4"
which nvcc       # Must show /lfs/sware/cuda-11.4/bin/nvcc
```

### 5.2 Clear Stale Compiler Environment Variables

After `module purge`, stale variables from the login shell may still point to wrong compilers. Clear them:
```bash
unset CC
unset CXX
unset CPATH
unset CPLUS_INCLUDE_PATH
unset C_INCLUDE_PATH
```

### 5.3 Set All Compiler and CUDA Paths Explicitly

Do not rely on any auto-detection. Every path is hardcoded for CUDA 11.4:
```bash
export CC=/lfs/sware/gcc9.2.0/bin/gcc
export CXX=/lfs/sware/gcc9.2.0/bin/g++
export CUDA_HOME=/lfs/sware/cuda-11.4
export CUDA_PATH=/lfs/sware/cuda-11.4
export CUDACXX=/lfs/sware/cuda-11.4/bin/nvcc
export PATH=/lfs/sware/cuda-11.4/bin:$PATH
export LD_LIBRARY_PATH=/lfs/sware/cuda-11.4/lib64:/lfs/sware/gcc9.2.0/lib64:$LD_LIBRARY_PATH
```

### 5.4 Set CMAKE Build Flags

Each flag here fixes a specific error that was encountered:
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
```

| Flag | Why It Is Needed |
| :--- | :--- |
| `CMAKE_C_COMPILER` / `CMAKE_CXX_COMPILER` | After `module purge`, `CC=clang` was left over. cmake could not find clang, so GCC 9.2 is specified explicitly. |
| `CMAKE_CUDA_HOST_COMPILER` | nvcc defaults to system `/usr/bin/g++` (GCC 4.x) which treats C++11 as experimental. This forces nvcc to use GCC 9.2 as its host compiler. |
| `CUDA_TOOLKIT_ROOT_DIR` | cmake's CUDA auto-detection found CUDA 10.1 headers from system paths even though nvcc was from CUDA 11.4. This overrides it. |
| `CMAKE_CUDA_FLAGS` | Adds CUDA 11.4 includes ahead of any lingering CUDA 10.1 paths in the environment. |
| `DGGML_LLAMAFILE=OFF` | The LLAMAFILE tiled kernel uses AVX-512 VNNI (`vpdpbusd`) instructions that Aqua's GCC 9.2 assembler does not support. |
| `DGGML_NATIVE=OFF` | Prevents `-march=native` from auto-enabling unsupported AVX-512 instructions based on the login node CPU. |
| `DGGML_AVX512=OFF` | Explicitly disables all AVX-512 instruction sets. GPU inference is completely unaffected by this. |

### 5.5 Reactivate Venv and Compile (Purging Pip Cache)

```bash
source ~/rxn_env/bin/activate

# Purge pip cache to prevent reusing any previously cached CUDA 12 builds:
pip cache purge
pip uninstall llama-cpp-python -y

# Compile from source with --no-cache-dir (takes 5–10 minutes):
pip install llama-cpp-python --no-binary llama-cpp-python --no-cache-dir --verbose 2>&1 | tee /tmp/llama_build_cu114.log
```

Watch the counter climb from `[1/338]` to `[338/338]`. It is done when you see:
```
Successfully installed llama-cpp-python-x.x.x
```

### 5.6 Verify CUDA 11.4 Shared Library Linkage
```bash
ldd ~/rxn_env/lib/python3.10/site-packages/llama_cpp/lib/libllama.so | grep "libcudart"
```
It should report:
`libcudart.so.11.0 => /lfs/sware/cuda-11.4/lib64/libcudart.so.11.0`

### 5.6 Install Project Core Dependencies
```bash
pip install pydantic httpx fastapi uvicorn rich python-dotenv pyyaml pandas sqlalchemy openpyxl jinja2
```

---

## 6. Step 5: Install `docling` for PDF-to-Markdown Conversion

Docling converts research paper PDFs into structured Markdown. Installing it on Aqua encounters specific toolchain quirks with Python 3.10 standalone:

### 6.1 Fix Missing `/tools/llvm/bin/llvm-ar` (Pillow Error)
When pip tries to compile C extensions (like `pillow`), standalone Python's internal sysconfig looks for `/tools/llvm/bin/llvm-ar`, which does not exist on Aqua:
```text
error: [Errno 2] No such file or directory: '/tools/llvm/bin/llvm-ar'
ERROR: Failed building wheel for pillow
```
**Fix:** Explicitly point `AR` to Linux's standard GNU archiver and install Pillow using pre-built binary wheels:
```bash
source ~/rxn_env/bin/activate
export AR=/usr/bin/ar
pip install --only-binary=pillow pillow
```

### 6.2 Install `docling` in Background (`nohup`)
Docling downloads several packages and layout models. On Lustre, this can take 10+ minutes. Use `nohup` so the installation keeps running even if your laptop disconnects:
```bash
export AR=/usr/bin/ar
nohup pip install docling > ~/docling_install.log 2>&1 &
```

* **Check installation progress:**
  ```bash
  tail -f ~/docling_install.log
  ```
### 6.3 Fix Missing `libspatialindex_c.so` (Rtree Error in Docling)
When running Docling, `rtree` crashes with:
```text
OSError: Could not load libspatialindex_c library
```
This is because RHEL 7 does not have `spatialindex` installed system-wide, and `rtree` searches specifically for the unversioned symlink `libspatialindex_c.so`.

**Fix:** Download and unpack the EPEL7 binary RPM into `~/rxn_env/lib/` and create the required symlinks:
```bash
source ~/rxn_env/bin/activate

# 1. Download EPEL 7 package and extract shared libraries
cd /tmp
wget https://dl.fedoraproject.org/pub/archive/epel/7/x86_64/Packages/s/spatialindex-1.8.5-1.el7.x86_64.rpm
rpm2cpio spatialindex-1.8.5-1.el7.x86_64.rpm | cpio -idmv

# 2. Copy libraries into the virtual environment's lib directory
cp -a usr/lib64/libspatialindex* ~/rxn_env/lib/
rm -rf usr spatialindex-1.8.5-1.el7.x86_64.rpm

# 3. Create the unversioned symlinks that rtree expects
cd ~/rxn_env/lib
ln -sf libspatialindex_c.so.4 libspatialindex_c.so
ln -sf libspatialindex.so.4 libspatialindex.so

# 4. Verify Docling and spatialindex
export LD_LIBRARY_PATH=$HOME/rxn_env/lib:$LD_LIBRARY_PATH
python -c "import rtree; from docling.document_converter import DocumentConverter; print('>>> Docling & Spatialindex SUCCESS!')"
```

### 6.4 Crucial Step: Pre-Cache Docling Models by Running Once on the Login Node (Online)
> **Critical Offline HPC Gotcha:**
> * On Aqua (and almost all HPC clusters), **GPU compute nodes have NO internet access**. Only the login/head node has outbound internet access.
> * Docling downloads its layout detection and OCR weights (~1.5 GB, e.g. `docling-layout-heron`) from Hugging Face **only when `.convert()` is actually executed on a PDF file**. Simply importing Docling does NOT download the weights.
> * If you submit a PBS batch job without doing this first, the compute node will fail with:
>   `ConnectError: [Errno -2] Name or service not known` or `Cannot find an appropriate cached snapshot folder`.

**Fix:** You **MUST** run the converter once on the **login node** with internet access on at least one real PDF. This permanently caches the layout weights in `~/.cache/huggingface/hub/` on your shared Lustre filesystem:

```bash
cd ~/rxn_extractor
source ~/rxn_env/bin/activate
export LD_LIBRARY_PATH=$HOME/rxn_env/lib:$LD_LIBRARY_PATH

# 1. Place at least one sample PDF in pdfs/
mkdir -p pdfs markdowns

# 2. Run the converter directly on the login node (downloads ~1.5 GB models to ~/.cache)
python -m src.pipeline.pdf_converter

# 3. Verify the models are physically cached on disk
ls -la ~/.cache/huggingface/hub/models--docling-project--docling-layout-heron/snapshots/
```
Once you see `[OK] ... -> ... .md`, the models are cached forever, and all future runs on the isolated GPU compute nodes will work 100% offline.

---

## 7. Step 6: Create the PBS Job Submission Script

Create or edit `~/rxn_extractor/job.sh`:

> **Critical Runtime Fixes in `LD_LIBRARY_PATH` & Offline Flags:** 
> 1. GCC 9.2 modern C++ library (`/lfs/sware/gcc9.2.0/lib64`) is required for `GLIBCXX_3.4.25`.
> 2. Virtual environment library (`$HOME/rxn_env/lib`) is required for `libspatialindex_c.so`.
> 3. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` prevent any Hugging Face network lookups on the compute node.
> You **must** include these in `job.sh`!

```bash
cat << 'EOF' > ~/rxn_extractor/job.sh
#!/bin/bash
# ==============================================================================
# PBS Job Script — Reaction Extractor on Aqua Tesla V100 GPU
# ==============================================================================
#PBS -N rxn_extractor
#PBS -q gpuq
#PBS -o logs/batch_out.log
#PBS -e logs/batch_err.log
#PBS -l select=1:ncpus=8:ngpus=1:mpiprocs=1
#PBS -l walltime=02:00:00

cd $PBS_O_WORKDIR
mkdir -p logs pdfs markdowns

# 1. Clean modules & load CUDA 11.4 (Backwards-compatible across all Aqua GPU nodes)
module purge
module load cuda11.4

# 2. Set library search paths (Fixes GLIBCXX_3.4.25, libcudart.so.11.0, and libspatialindex_c.so)
export LD_LIBRARY_PATH=/lfs/sware/cuda-11.4/lib64:/lfs/sware/gcc9.2.0/lib64:$HOME/rxn_env/lib:$LD_LIBRARY_PATH

# 3. Activate Python virtual environment
source $HOME/rxn_env/bin/activate

# 4. Force HuggingFace & Docling to run 100% offline from local cache
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

# 5. Model & Runtime configuration
export MODEL_PATH="models/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
export NUM_GPU_LAYERS="-1"
export NUM_CTX="32768"

echo "=== Job Started on $(cat $PBS_NODEFILE) at $(date) ==="
nvidia-smi

# 6. Convert PDFs to Markdown (automatically skips files already converted)
echo "=== Step 1: Converting PDFs to Markdown ==="
python -m src.pipeline.pdf_converter

# 7. Run Batch Extraction (Note: no --all flag, default processes all markdowns)
echo "=== Step 2: Running Batch Extraction ==="
python run_batch.py

echo "=== Job Finished at: $(date) ==="
EOF
```

---

## 8. Step 7: Submit and Monitor the Job

### 8.1 Place Input PDFs
Place your PDF papers into:
```bash
~/rxn_extractor/pdfs/
```
*(The pipeline will auto-convert them into `markdowns/` on the first run, and skip already converted ones thereafter).*

### 8.2 Submit Job
```bash
cd ~/rxn_extractor
qsub job.sh
# Returns a Job ID e.g. 123456.aqua-m
```

### 8.3 Monitor
```bash
qstat -u $USER                  # Q=Queued, R=Running
tail -f logs/batch_out.log      # Live extraction output
tail -f logs/batch_err.log      # Errors
```

### 8.4 Cancel a Job
```bash
qdel <job_id>
```

---

## 9. Step 8: Retrieve Results

From your **local machine**:
```bash
scp -r <username>@aqua.iitm.ac.in:~/rxn_extractor/data ./aqua_results/
```

---

## 10. Reference: Useful Diagnostics & Commands on Aqua

```bash
# Check quota usage
quota -s

# View queue summary
qstat -Q

# View active jobs and assigned nodes
qstat -an

# See only GPU node states
pbsnodes -aS | grep "gpu"

# See why a queued job is waiting
qstat -f <job_id> | grep -E "comment =|Resource_List|queue ="

# Re-compile domain config if reaction.yaml was edited on Aqua:
source ~/rxn_env/bin/activate
python -m src.builder.cli --domain reaction.yaml
```
