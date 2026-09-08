"""
CSV-based storage layer for rxn_extractor.
Replaces the SQL database during development.
Upgrade path: swap CsvStore for the SQLAlchemy session in batch_manager and routes.

CSV files written to: data/ (configurable via DATA_DIR env var)
  data/papers.csv
  data/experiments.csv
  data/corrections.csv
  data/batch_jobs.csv
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.getenv("DATA_DIR", "data")


# ---------------------------------------------------------------------------
# Column schemas — these define the flat CSV columns for each file.
# The 'data' column in experiments holds a JSON-encoded string of the full
# extraction dict (all sub-domains). Everything else is top-level metadata.
# ---------------------------------------------------------------------------

PAPERS_COLS = [
    "id", "paper_identifier", "title", "file_path", "file_hash",
    "domain_name", "processing_status", "error_message", "created_at", "updated_at",
]

EXPERIMENTS_COLS = [
    "id", "paper_id", "paper_identifier", "experiment_number", "domain_name",
    "data",               # JSON string — full extraction dict
    "overall_confidence", "validation_status", "review_notes",
    "needs_review", "extracted_at",
]

CORRECTIONS_COLS = [
    "id", "experiment_id", "field_path", "original_value", "corrected_value",
    "correction_type", "reviewer_notes", "reviewer_id", "created_at",
]

BATCH_JOBS_COLS = [
    "id", "job_name", "domain_name", "total_papers", "processed_papers",
    "successful_experiments", "failed_experiments",
    "status", "start_time", "end_time", "error_log", "created_at",
]


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _csv_path(filename: str, data_dir: str = DATA_DIR) -> str:
    _ensure_dir(data_dir)
    return os.path.join(data_dir, filename)


def _read_csv(filename: str, data_dir: str = DATA_DIR) -> List[Dict[str, str]]:
    path = _csv_path(filename, data_dir)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(filename: str, rows: List[Dict], cols: List[str], data_dir: str = DATA_DIR):
    path = _csv_path(filename, data_dir)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _next_id(rows: List[Dict]) -> int:
    if not rows:
        return 1
    return max(int(r.get("id", 0)) for r in rows) + 1


def _now() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# CsvStore — public interface used by batch_manager and routes
# ---------------------------------------------------------------------------

class CsvStore:
    """
    Simple CSV-backed data store.

    Usage pattern (mirrors SQLAlchemy session API just enough):
        store = CsvStore()
        paper_id = store.upsert_paper(...)
        store.insert_experiment(paper_id, ...)
        papers = store.list_papers()
    """

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        _ensure_dir(data_dir)
        logger.info(f"CsvStore initialised → {os.path.abspath(data_dir)}/")

    # ------------------------------------------------------------------ papers

    def upsert_paper(
        self,
        paper_identifier: str,
        title: str,
        file_path: str,
        file_hash: str,
        domain_name: str,
        processing_status: str = "pending",
    ) -> int:
        """Insert or update a paper row. Returns the paper id."""
        rows = _read_csv("papers.csv", self.data_dir)
        existing = next((r for r in rows if r["paper_identifier"] == paper_identifier), None)
        now = _now()

        if existing:
            existing["title"] = title
            existing["file_path"] = file_path
            existing["file_hash"] = file_hash
            existing["domain_name"] = domain_name
            existing["processing_status"] = processing_status
            existing["updated_at"] = now
            paper_id = int(existing["id"])
        else:
            paper_id = _next_id(rows)
            rows.append({
                "id": paper_id,
                "paper_identifier": paper_identifier,
                "title": title,
                "file_path": file_path,
                "file_hash": file_hash,
                "domain_name": domain_name,
                "processing_status": processing_status,
                "error_message": "",
                "created_at": now,
                "updated_at": now,
            })

        _write_csv("papers.csv", rows, PAPERS_COLS, self.data_dir)
        return paper_id

    def update_paper_status(self, paper_id: int, status: str, error_message: str = ""):
        rows = _read_csv("papers.csv", self.data_dir)
        for r in rows:
            if int(r["id"]) == paper_id:
                r["processing_status"] = status
                r["error_message"] = error_message
                r["updated_at"] = _now()
                break
        _write_csv("papers.csv", rows, PAPERS_COLS, self.data_dir)

    def list_papers(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        rows = _read_csv("papers.csv", self.data_dir)
        if search:
            s = search.lower()
            rows = [r for r in rows if s in r["title"].lower() or s in r["paper_identifier"].lower()]
        if status:
            rows = [r for r in rows if r["processing_status"] == status]
        # attach experiment_count
        exp_rows = _read_csv("experiments.csv", self.data_dir)
        for r in rows:
            r["experiment_count"] = sum(1 for e in exp_rows if e["paper_id"] == r["id"])
        return rows[offset: offset + limit]

    def get_paper(self, paper_id: int) -> Optional[Dict]:
        rows = _read_csv("papers.csv", self.data_dir)
        return next((r for r in rows if int(r["id"]) == paper_id), None)

    # -------------------------------------------------------------- experiments

    def upsert_experiment(
        self,
        paper_id: int,
        paper_identifier: str,
        experiment_number: int,
        domain_name: str,
        extraction_data: Dict,
        overall_confidence: Optional[int],
    ) -> int:
        """Insert or replace an experiment row. Returns the experiment id."""
        rows = _read_csv("experiments.csv", self.data_dir)
        existing = next(
            (r for r in rows
             if int(r["paper_id"]) == paper_id and int(r["experiment_number"]) == experiment_number),
            None,
        )
        now = _now()
        data_json = json.dumps(extraction_data, default=str)

        if existing:
            existing["data"] = data_json
            existing["overall_confidence"] = str(overall_confidence or "")
            existing["needs_review"] = "True"
            exp_id = int(existing["id"])
        else:
            exp_id = _next_id(rows)
            rows.append({
                "id": exp_id,
                "paper_id": paper_id,
                "paper_identifier": paper_identifier,
                "experiment_number": experiment_number,
                "domain_name": domain_name,
                "data": data_json,
                "overall_confidence": str(overall_confidence or ""),
                "validation_status": "pending",
                "review_notes": "",
                "needs_review": "True",
                "extracted_at": now,
            })

        _write_csv("experiments.csv", rows, EXPERIMENTS_COLS, self.data_dir)
        return exp_id

    def list_experiments(
        self,
        paper_id: Optional[int] = None,
        validation_status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict]:
        rows = _read_csv("experiments.csv", self.data_dir)
        if paper_id is not None:
            rows = [r for r in rows if int(r["paper_id"]) == paper_id]
        if validation_status:
            rows = [r for r in rows if r["validation_status"] == validation_status]
        # Parse data JSON for callers
        for r in rows:
            try:
                r["data_parsed"] = json.loads(r.get("data", "{}"))
            except Exception:
                r["data_parsed"] = {}
        return rows[offset: offset + limit]

    def get_experiment(self, experiment_id: int) -> Optional[Dict]:
        rows = _read_csv("experiments.csv", self.data_dir)
        row = next((r for r in rows if int(r["id"]) == experiment_id), None)
        if row:
            try:
                row["data_parsed"] = json.loads(row.get("data", "{}"))
            except Exception:
                row["data_parsed"] = {}
        return row

    def update_experiment_validation(
        self,
        experiment_id: int,
        validation_status: str,
        reviewer_notes: str = "",
    ):
        rows = _read_csv("experiments.csv", self.data_dir)
        for r in rows:
            if int(r["id"]) == experiment_id:
                r["validation_status"] = validation_status
                r["review_notes"] = reviewer_notes
                r["needs_review"] = "False" if validation_status in ("approved", "rejected") else "True"
                break
        _write_csv("experiments.csv", rows, EXPERIMENTS_COLS, self.data_dir)

    def update_experiment_field(self, experiment_id: int, field_path: str, new_value: Any) -> Any:
        """Navigate into the data JSON, update a nested field, return original value."""
        rows = _read_csv("experiments.csv", self.data_dir)
        original_value = None
        for r in rows:
            if int(r["id"]) == experiment_id:
                data = json.loads(r.get("data", "{}"))
                keys = field_path.split(".")
                # Navigate to parent
                node = data
                for k in keys[:-1]:
                    node = node.setdefault(k, {})
                original_value = node.get(keys[-1])
                node[keys[-1]] = new_value
                r["data"] = json.dumps(data, default=str)
                break
        _write_csv("experiments.csv", rows, EXPERIMENTS_COLS, self.data_dir)
        return original_value

    # ------------------------------------------------------------- corrections

    def add_correction(
        self,
        experiment_id: int,
        field_path: str,
        original_value: Any,
        corrected_value: Any,
        correction_type: str = "edit",
        reviewer_notes: str = "",
        reviewer_id: str = "",
    ) -> int:
        rows = _read_csv("corrections.csv", self.data_dir)
        corr_id = _next_id(rows)
        rows.append({
            "id": corr_id,
            "experiment_id": experiment_id,
            "field_path": field_path,
            "original_value": str(original_value) if original_value is not None else "",
            "corrected_value": str(corrected_value),
            "correction_type": correction_type,
            "reviewer_notes": reviewer_notes,
            "reviewer_id": reviewer_id,
            "created_at": _now(),
        })
        _write_csv("corrections.csv", rows, CORRECTIONS_COLS, self.data_dir)
        return corr_id

    def list_corrections(self, experiment_id: int) -> List[Dict]:
        rows = _read_csv("corrections.csv", self.data_dir)
        return [r for r in rows if int(r["experiment_id"]) == experiment_id]

    # ---------------------------------------------------------------- batch jobs

    def create_batch_job(self, job_name: str, domain_name: str, total_papers: int) -> int:
        rows = _read_csv("batch_jobs.csv", self.data_dir)
        job_id = _next_id(rows)
        rows.append({
            "id": job_id,
            "job_name": job_name,
            "domain_name": domain_name,
            "total_papers": total_papers,
            "processed_papers": 0,
            "successful_experiments": 0,
            "failed_experiments": 0,
            "status": "in_progress",
            "start_time": _now(),
            "end_time": "",
            "error_log": "",
            "created_at": _now(),
        })
        _write_csv("batch_jobs.csv", rows, BATCH_JOBS_COLS, self.data_dir)
        return job_id

    def update_batch_job(self, job_id: int, **kwargs):
        rows = _read_csv("batch_jobs.csv", self.data_dir)
        for r in rows:
            if int(r["id"]) == job_id:
                for k, v in kwargs.items():
                    r[k] = str(v)
                break
        _write_csv("batch_jobs.csv", rows, BATCH_JOBS_COLS, self.data_dir)

    def list_batch_jobs(self, limit: int = 5) -> List[Dict]:
        rows = _read_csv("batch_jobs.csv", self.data_dir)
        return list(reversed(rows))[:limit]

    def get_active_batch_job(self) -> Optional[Dict]:
        rows = _read_csv("batch_jobs.csv", self.data_dir)
        return next((r for r in reversed(rows) if r["status"] == "in_progress"), None)

    # -------------------------------------------------------------------- stats

    def get_stats(self) -> Dict:
        papers = _read_csv("papers.csv", self.data_dir)
        experiments = _read_csv("experiments.csv", self.data_dir)
        corrections = _read_csv("corrections.csv", self.data_dir)

        total_papers = len(papers)
        processed = sum(1 for p in papers if p["processing_status"] == "processed")
        pending = sum(1 for p in papers if p["processing_status"] == "pending")

        total_exp = len(experiments)
        approved = sum(1 for e in experiments if e["validation_status"] == "approved")
        rejected = sum(1 for e in experiments if e["validation_status"] == "rejected")
        flagged = sum(1 for e in experiments if e["validation_status"] == "flagged")

        confs = [int(e["overall_confidence"]) for e in experiments if e.get("overall_confidence")]
        avg_conf = sum(confs) / len(confs) if confs else None

        return {
            "total_papers": total_papers,
            "processed_papers": processed,
            "pending_papers": pending,
            "total_experiments": total_exp,
            "approved_experiments": approved,
            "rejected_experiments": rejected,
            "flagged_experiments": flagged,
            "avg_confidence": avg_conf,
            "total_corrections": len(corrections),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[CsvStore] = None


def get_store(data_dir: str = DATA_DIR) -> CsvStore:
    global _store
    if _store is None:
        _store = CsvStore(data_dir)
    return _store


def reset_store():
    global _store
    _store = None
