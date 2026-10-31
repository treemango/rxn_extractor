    #!/bin/bash
    #PBS -N pdf_to_md_converter
    #PBS -o logs/batch_out.log
    #PBS -e logs/batch_err.log
    #PBS -q gpuq
    #PBS -l select=1:ncpus=16:ngpus=1:mpiprocs=1
    #PBS -l walltime=10:00:00
    
    cd $PBS_O_WORKDIR
    mkdir -p logs

    # 1. Force Python to flush every print/log statement immediately
    export PYTHONUNBUFFERED=1
    
    # 2. Tell PBS not to hold back output (direct streaming)
    #PBS -k oe
    
    # 1. Clean module environment & load CUDA 12.1
    module purge
    module load cuda12.1

    # 2. Add GCC 9.2 modern C++ libraries to LD_LIBRARY_PATH (Fixes GLIBCXX error!)
    export LD_LIBRARY_PATH=$HOME/rxn_env/lib:/lfs/sware/gcc9.2.0/lib64:$LD_LIBRARY_PATH    
    #export LD_LIBRARY_PATH=/lfs/sware/gcc9.2.0/lib64:$LD_LIBRARY_PATH
    
    # 2. Activate Python virtual environment
    source $HOME/rxn_env/bin/activate

    # 3. Model & Runtime configuration
    export MODEL_PATH="models/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
    export NUM_GPU_LAYERS="-1"
    export NUM_CTX="32768"    
    #export NUM_CTX="8192"

    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1
    export HF_DATASETS_OFFLINE=1

    echo "=== Job Started ==="
    echo "Node assigned: $(cat $PBS_NODEFILE)"
    echo "Date: $(date)"

    # Verify GPU is accessible on compute node
    nvidia-smi

    echo "=== Step 1: Converting PDFs to Markdown ==="
    python -u -m src.pipeline.pdf_converter

    echo "=== Job Finished at: $(date) ==="

