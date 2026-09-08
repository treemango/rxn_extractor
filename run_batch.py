#!/usr/bin/env python3
"""
Entry point for the rxn_extractor batch pipeline.

Usage:
    python run_batch.py                  # process all papers
    python run_batch.py --limit 10       # process first 10 papers
    python run_batch.py --resume         # resume from last checkpoint

The domain is always read from reaction.yaml in the project root.
"""
import argparse
import logging
import sys

REACTION_YAML = "reaction.yaml"

def main():
    parser = argparse.ArgumentParser(description="Run the rxn_extractor batch pipeline")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of papers to process")
    parser.add_argument("--resume", action="store_true",
                        help="Resume processing from the latest checkpoint")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Starting batch extraction  (domain: {REACTION_YAML})")

    if args.limit:
        logger.info(f"Limiting to {args.limit} papers")
    if args.resume:
        logger.info("Resuming from checkpoint")

    try:
        from src.pipeline.batch_manager import BatchManager
        batch_manager = BatchManager(domain_yaml_path=REACTION_YAML)
        batch_manager.process_all(limit=args.limit, resume=args.resume)
        logger.info("Batch extraction completed successfully")
    except Exception as e:
        logger.error(f"Batch extraction failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
