    #!/bin/bash
    #PBS -N rxn_extractor
    #PBS -o logs/batch_out.log
    #PBS -e logs/batch_err.log
    #PBS -q gpuq
    #PBS -l select=1:ncpus=8:ngpus=1:mpiprocs=1
    #PBS -l walltime=02:00:00
    
    cd $PBS_O_WORKDIR
    mkdir -p logs
    
    # 1. Clean module environment & load CUDA 12.1
    module purge
    module load cuda12.1

    # 2. Add GCC 9.2 modern C++ libraries to LD_LIBRARY_PATH (Fixes GLIBCXX error!)
    export LD_LIBRARY_PATH=/lfs/sware/gcc9.2.0/lib64:$LD_LIBRARY_PATH
    
    # 2. Activate Python virtual environment
    source $HOME/rxn_env/bin/activate

    # 3. Model & Runtime configuration
    export MODEL_PATH="models/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
    export NUM_GPU_LAYERS="-1"
    export NUM_CTX="32768"    
    #export NUM_CTX="8192"

    echo "=== Job Started ==="
    echo "Node assigned: $(cat $PBS_NODEFILE)"
    echo "Date: $(date)"

    # Verify GPU is accessible on compute node
    nvidia-smi

    echo "=== Step 1: Converting PDFs to Markdown ==="
    python -m src.pipeline.pdf_converter

    echo "=== Running Batch Extraction ==="
    python run_batch.py

    echo "=== Job Finished at: $(date) ==="

