"""
Batch processing orchestrator — CSV backend edition.

Reads markdown papers → runs the multi-agent extraction pipeline →
writes results to data/*.csv via CsvStore.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.agents.extractor import Extractor
from src.agents.parser_agent import ParserAgent
from src.db.database import get_store
from src.pipeline.checkpoint import load_checkpoint, save_checkpoint
from src.pipeline.file_reader import discover_papers, read_paper

logger = logging.getLogger(__name__)
console = Console()


REACTION_YAML = "reaction.yaml"


class BatchManager:
    """Batch processing orchestrator (CSV backend)."""

    def __init__(self, domain_yaml_path: str = REACTION_YAML):
        self.domain_yaml_path = domain_yaml_path
        self.parser_agent = ParserAgent()
        self.extractor = Extractor()
        self.store = get_store()
        # Read domain_name from auto-generated config if available
        try:
            from src.auto_generated import config as ag_config
            self.domain_name = ag_config.DOMAIN_NAME
        except ImportError:
            self.domain_name = os.path.splitext(os.path.basename(domain_yaml_path))[0]

    # ------------------------------------------------------------------ helpers

    def _store_paper(self, paper_info: dict) -> int:
        return self.store.upsert_paper(
            paper_identifier=paper_info["identifier"],
            title=paper_info["title"],
            file_path=paper_info["file_path"],
            file_hash=paper_info["file_hash"],
            domain_name=self.domain_name,
            processing_status="pending",
        )

    def _store_experiment(
        self, paper_id: int, paper_identifier: str, exp_num: int, extraction_dict: dict
    ) -> int:
        confidence = extraction_dict.get("overall_confidence") or extraction_dict.get("confidence")
        return self.store.upsert_experiment(
            paper_id=paper_id,
            paper_identifier=paper_identifier,
            experiment_number=exp_num,
            domain_name=self.domain_name,
            extraction_data=extraction_dict,
            overall_confidence=confidence,
        )

    # ---------------------------------------------------------------- main loop

    def process_all(
        self,
        input_dir: Optional[str] = None,
        limit: Optional[int] = None,
        resume: bool = False,
        checkpoint_interval: int = 5,
    ):
        """Process all markdown papers in input_dir and save to CSV.

        input_dir defaults to the value of INPUT_MARKDOWN_DIR in auto_generated/config.py,
        which is derived from reaction.yaml → input_markdown_dir.
        """
        checkpoint_dir = os.path.join(os.getcwd(), "checkpoints")

        # Resolve input directory from auto-generated config if not explicitly given
        if input_dir is None:
            try:
                from src.auto_generated import config as ag_config
                input_dir = ag_config.INPUT_MARKDOWN_DIR
            except (ImportError, AttributeError):
                input_dir = "markdowns/"
        logger.info(f"Reading papers from: {os.path.abspath(input_dir)}")

        papers_info = discover_papers(input_dir)
        if not papers_info:
            console.print("[bold yellow]No markdown papers found in directory.[/bold yellow]")
            return

        if limit:
            papers_info = papers_info[:limit]

        start_index = 0
        stats = {"processed": 0, "successful": 0, "failed": 0, "total_experiments": 0}

        if resume:
            ckpt = load_checkpoint(checkpoint_dir)
            if ckpt and ckpt.get("domain_name") == self.domain_name:
                start_index = ckpt.get("last_index", 0)
                stats = ckpt.get("stats", stats)
                console.print(f"[cyan]Resuming from paper index {start_index}[/cyan]")

        papers_to_process = papers_info[start_index:]

        # Create batch job record
        job_id = self.store.create_batch_job(
            job_name=f"Batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            domain_name=self.domain_name,
            total_papers=len(papers_info),
        )

        console.print(
            f"[bold blue]Starting batch extraction: {len(papers_to_process)} papers "
            f"(domain: {self.domain_name})[/bold blue]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting...", total=len(papers_to_process))

            for idx, paper_info in enumerate(papers_to_process):
                current_index = start_index + idx
                identifier = paper_info["identifier"]
                progress.update(task, description=f"[cyan]{identifier[:40]}[/cyan]")

                try:
                    content = read_paper(paper_info["file_path"])
                    paper_id = self._store_paper(paper_info)
                    self.store.update_paper_status(paper_id, "processing")

                    results = self.extractor.extract_paper(
                        content, paper_id, self.parser_agent
                    )

                    for exp_idx, exp_data in enumerate(results):
                        self._store_experiment(
                            paper_id, identifier, exp_idx + 1, exp_data
                        )
                        stats["total_experiments"] += 1

                    self.store.update_paper_status(paper_id, "processed")
                    stats["successful"] += 1
                    logger.info(
                        f"✓ {identifier}: {len(results)} experiments extracted"
                    )

                except Exception as e:
                    logger.error(
                        f"✗ {identifier}: {e}", exc_info=True
                    )
                    if "paper_id" in dir():
                        self.store.update_paper_status(paper_id, "error", str(e))
                    stats["failed"] += 1

                stats["processed"] += 1
                progress.advance(task)

                # Checkpoint & job update
                if stats["processed"] % checkpoint_interval == 0:
                    save_checkpoint(checkpoint_dir, current_index + 1, stats, self.domain_name)
                    self.store.update_batch_job(
                        job_id,
                        processed_papers=stats["processed"],
                        successful_experiments=stats["successful"],
                        failed_experiments=stats["failed"],
                    )

        # Final saves
        save_checkpoint(
            checkpoint_dir, start_index + len(papers_to_process), stats, self.domain_name
        )
        self.store.update_batch_job(
            job_id,
            processed_papers=stats["processed"],
            successful_experiments=stats["successful"],
            failed_experiments=stats["failed"],
            status="completed",
            end_time=datetime.utcnow().isoformat(),
        )

        # Summary
        console.rule("[bold green]Batch complete[/bold green]")
        console.print(f"  Papers processed  : {stats['processed']}")
        console.print(f"  Successful        : {stats['successful']}")
        console.print(f"  Failed            : {stats['failed']}")
        console.print(f"  Experiments total : {stats['total_experiments']}")
        console.print(f"  Results saved to  : {os.path.abspath(self.store.data_dir)}/")
