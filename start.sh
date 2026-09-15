#!/usr/bin/env bash
set -e

# Change to the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "    Reaction Extractor (rxn_extractor) Setup      "
echo "=================================================="

# 1. Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

# 2. Virtual Environment Setup
if [ ! -d "venv" ] || [ ! -f "venv/bin/python" ]; then
    echo "[INFO] Creating virtual environment in ./venv..."
    python3 -m venv venv || {
        echo "[ERROR] Failed to create virtual environment."
        echo "On Ubuntu/Debian, you may need: sudo apt install python3-venv"
        exit 1
    }
else
    echo "[INFO] Virtual environment './venv' found."
fi

# Use the virtual environment's binaries explicitly (guaranteed isolation)
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
VENV_PIP="$SCRIPT_DIR/venv/bin/pip"

# 3. Dependency Installation — only run when requirements.txt has changed
DEPS_MARKER="$SCRIPT_DIR/venv/.deps_installed"
if [ ! -f "$DEPS_MARKER" ] || [ "$SCRIPT_DIR/requirements.txt" -nt "$DEPS_MARKER" ]; then
    echo "[INFO] Installing / updating dependencies (this may take a while on first run)..."
    "$VENV_PIP" install --upgrade pip --quiet
    "$VENV_PIP" install -r requirements.txt --quiet
    touch "$DEPS_MARKER"
    echo "[INFO] Dependencies ready."
else
    echo "[INFO] Dependencies already up to date. Skipping install."
fi

# 4. Check for reaction.yaml (single source of truth)
if [ ! -f "reaction.yaml" ]; then
    if [ -f "domains/example_reaction.yaml" ]; then
        echo "[INFO] reaction.yaml not found. Copying from domains/example_reaction.yaml..."
        cp domains/example_reaction.yaml reaction.yaml
    else
        echo "[WARNING] Neither reaction.yaml nor domains/example_reaction.yaml found."
    fi
fi

# 5. Build Artifacts (Compile reaction.yaml -> models, prompts, UI)
if [ -f "reaction.yaml" ]; then
    echo "[INFO] Compiling schema from reaction.yaml using venv Python..."
    "$VENV_PYTHON" -m src.builder.cli
fi

# 6. Execution Command Handling
ACTION="${1:-ui}"

case "$ACTION" in
    ui)
        echo "=================================================="
        echo "[INFO] Starting HITL Web Dashboard at http://localhost:8000"
        echo "Press Ctrl+C to stop."
        echo "=================================================="
        exec "$SCRIPT_DIR/venv/bin/uvicorn" src.api.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    batch)
        shift || true
        echo "=================================================="
        echo "[INFO] Running batch extraction..."
        echo "=================================================="
        exec "$VENV_PYTHON" run_batch.py "$@"
        ;;
    convert)
        shift || true
        echo "=================================================="
        echo "[INFO] Converting PDFs in pdfs/ → markdowns/"
        echo "[INFO] Skipping PDFs whose .md already exists."
        echo "[NOTE] First run downloads ~1.5GB of layout models."
        echo "=================================================="
        exec "$VENV_PYTHON" -m src.pipeline.pdf_converter "$@"
        ;;
    build)
        echo "[INFO] Build completed successfully."
        ;;
    *)
        echo "Usage: $0 [ui|batch|convert|build]"
        echo "  ui      : Launch the HITL FastAPI web dashboard (default)"
        echo "  batch   : Run the batch extraction pipeline (e.g., ./start.sh batch --limit 5)"
        echo "  convert : Convert PDFs in pdfs/ to Markdown in markdowns/"
        echo "            (e.g., ./start.sh convert --force  to re-convert existing files)"
        echo "  build   : Only compile models, prompts, and UI from reaction.yaml"
        exit 1
        ;;
esac
