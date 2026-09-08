#!/usr/bin/env bash
set -e

# Change to the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "    Reaction Extractor (rxn_extractor) Setup      "
echo "=================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment in ./venv..."
    python3 -m venv venv
else
    echo "[INFO] Virtual environment './venv' found."
fi

echo "[INFO] Activating virtual environment..."
source venv/bin/activate

echo "[INFO] Installing / verifying dependencies from requirements.txt..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

if [ ! -f "reaction.yaml" ]; then
    if [ -f "domains/example_reaction.yaml" ]; then
        echo "[INFO] reaction.yaml not found. Copying from domains/example_reaction.yaml..."
        cp domains/example_reaction.yaml reaction.yaml
    else
        echo "[WARNING] Neither reaction.yaml nor domains/example_reaction.yaml found."
    fi
fi

if [ -f "reaction.yaml" ]; then
    echo "[INFO] Compiling schema from reaction.yaml..."
    python -m src.builder.cli
fi

# 6. Execution Command Handling
# ACTION="${1:-ui}"
# 
# case "$ACTION" in
#     ui)
#         echo "=================================================="
#         echo "[INFO] Starting HITL Web Dashboard at http://localhost:8000"
#         echo "Press Ctrl+C to stop."
#         echo "=================================================="
#         exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
#         ;;
#     batch)
#         shift || true
#         echo "=================================================="
#         echo "[INFO] Running batch extraction..."
#         echo "=================================================="
#         exec python run_batch.py "$@"
#         ;;
#     build)
#         echo "[INFO] Build completed successfully."
#         ;;
#     *)
#         echo "Usage: $0 [ui|batch|build]"
#         echo "  ui     : Launch the HITL FastAPI web dashboard (default)"
#         echo "  batch  : Run the batch extraction pipeline (e.g., ./start.sh batch --limit 5)"
#         echo "  build  : Only compile models, prompts, and UI from reaction.yaml"
#         exit 1
#         ;;
# esac
