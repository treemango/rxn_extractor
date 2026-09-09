"""
PDF to Markdown converter using Docling.

Scans pdfs/ for *.pdf files and converts each to a .md file in markdowns/.
Skips any PDF whose corresponding .md already exists (idempotent).

Usage as a module:
    from src.pipeline.pdf_converter import convert_pdfs_to_markdown
    results = convert_pdfs_to_markdown()

Usage from the command line:
    python -m src.pipeline.pdf_converter
    python -m src.pipeline.pdf_converter --force     # re-convert even if .md exists
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults — both relative to the project root (wherever start.sh / run_batch.py is invoked)
PDF_DIR_DEFAULT = "pdfs"
MD_DIR_DEFAULT  = "markdowns"

# Minimum character count for a "healthy" conversion.
# If a converted .md is shorter, the PDF is likely scanned or empty.
MIN_CONTENT_LENGTH = 500


def convert_pdfs_to_markdown(
    pdf_dir: str = PDF_DIR_DEFAULT,
    md_dir:  str = MD_DIR_DEFAULT,
    force:   bool = False,
) -> dict:
    """
    Convert all *.pdf files in `pdf_dir` to *.md files in `md_dir`.

    Args:
        pdf_dir: Directory to scan for PDF files (default: pdfs/).
        md_dir:  Directory to write markdown files (default: markdowns/).
        force:   If True, re-convert even if the .md already exists.

    Returns:
        Summary dict:
        {
          "converted": ["paper_a.pdf", ...],
          "skipped":   ["paper_b.pdf", ...],
          "failed":    ["paper_c.pdf", ...],
          "warned":    ["paper_d.pdf", ...],  # converted but suspiciously short
        }
    """
    # Lazy import so the rest of the project works even without docling installed
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        logger.error(
            "docling is not installed. "
            "Run:  pip install docling"
        )
        return {"converted": [], "skipped": [], "failed": [], "warned": []}

    os.makedirs(md_dir, exist_ok=True)

    pdf_path = Path(pdf_dir)
    if not pdf_path.exists():
        logger.warning(f"PDF directory not found: {pdf_dir!r}  — nothing to convert.")
        return {"converted": [], "skipped": [], "failed": [], "warned": []}

    pdf_files = sorted(pdf_path.glob("*.pdf"))
    if not pdf_files:
        logger.info(f"No *.pdf files found in {pdf_dir!r}.")
        return {"converted": [], "skipped": [], "failed": [], "warned": []}

    logger.info(f"Found {len(pdf_files)} PDF(s) in {pdf_dir!r}")

    # Initialise the converter once (loads layout models into memory)
    logger.info("Initialising Docling converter (may download models on first run)…")
    converter = DocumentConverter()

    results: dict = {"converted": [], "skipped": [], "failed": [], "warned": []}

    for pdf_file in pdf_files:
        md_file = Path(md_dir) / (pdf_file.stem + ".md")

        # Skip if already converted and force is not requested
        if md_file.exists() and not force:
            logger.info(f"[SKIP]    {pdf_file.name}  →  {md_file.name} already exists")
            results["skipped"].append(pdf_file.name)
            continue

        logger.info(f"[CONVERT] {pdf_file.name} …")
        try:
            result = converter.convert(str(pdf_file))
            markdown_content = result.document.export_to_markdown()

            # Warn if the output is suspiciously short (likely a scanned PDF)
            if len(markdown_content.strip()) < MIN_CONTENT_LENGTH:
                logger.warning(
                    f"[WARN]    {pdf_file.name} produced only "
                    f"{len(markdown_content)} characters. "
                    "The PDF may be scanned and require OCR, or the file may be empty."
                )
                results["warned"].append(pdf_file.name)

            md_file.write_text(markdown_content, encoding="utf-8")
            logger.info(
                f"[OK]      {pdf_file.name}  →  {md_file.name} "
                f"({len(markdown_content):,} chars)"
            )
            results["converted"].append(pdf_file.name)

        except Exception as exc:
            logger.error(f"[FAIL]    {pdf_file.name}: {exc}")
            results["failed"].append(pdf_file.name)

    return results


def print_summary(results: dict) -> None:
    lines = [
        "",
        "=" * 52,
        "  PDF Conversion Summary",
        "=" * 52,
        f"  Converted : {len(results['converted'])}",
        f"  Skipped   : {len(results['skipped'])}  (already exist)",
        f"  Warned    : {len(results['warned'])}  (converted but short — check for scanned PDFs)",
        f"  Failed    : {len(results['failed'])}",
    ]
    if results["warned"]:
        lines.append("\n  Warned files (check for OCR issues):")
        for f in results["warned"]:
            lines.append(f"    ⚠  {f}")
    if results["failed"]:
        lines.append("\n  Failed files:")
        for f in results["failed"]:
            lines.append(f"    ✗  {f}")
    lines.append("=" * 52)
    print("\n".join(lines))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDFs in pdfs/ to Markdown files in markdowns/"
    )
    parser.add_argument(
        "--pdf-dir", default=PDF_DIR_DEFAULT,
        help=f"Source directory for PDF files (default: {PDF_DIR_DEFAULT})"
    )
    parser.add_argument(
        "--md-dir", default=MD_DIR_DEFAULT,
        help=f"Destination directory for Markdown files (default: {MD_DIR_DEFAULT})"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-convert PDFs even if the .md file already exists"
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    args = _parse_args()
    results = convert_pdfs_to_markdown(
        pdf_dir=args.pdf_dir,
        md_dir=args.md_dir,
        force=args.force,
    )
    print_summary(results)
