"""
FastAPI REST routes — CSV backend edition.

Reads from and writes to data/*.csv via CsvStore.
Upgrade path: swap get_store() for get_db() and restore SQLAlchemy queries.
"""

import csv
import io
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.db.database import get_store

router = APIRouter(prefix="/api", tags=["API"])


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class ExperimentResponse(BaseModel):
    id: int
    paper_id: int
    paper_identifier: str
    experiment_number: int
    domain_name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    overall_confidence: Optional[int] = None
    validation_status: str
    review_notes: Optional[str] = None
    needs_review: bool
    extracted_at: str


class PaperResponse(BaseModel):
    id: int
    paper_identifier: str
    title: str
    domain_name: Optional[str] = None
    processing_status: str
    created_at: str
    experiment_count: int = 0


class QueueItemResponse(BaseModel):
    experiment_id: int
    paper_identifier: str
    experiment_number: int
    validation_status: str
    overall_confidence: Optional[int] = None
    review_notes: Optional[str] = None
    needs_review: bool


class StatsResponse(BaseModel):
    total_papers: int
    processed_papers: int
    pending_papers: int
    total_experiments: int
    approved_experiments: int
    rejected_experiments: int
    flagged_experiments: int
    avg_confidence: Optional[float] = None
    total_corrections: int


class ValidationUpdate(BaseModel):
    validation_status: str
    reviewer_notes: Optional[str] = None
    reviewer_id: Optional[str] = None


class CorrectionCreate(BaseModel):
    field_path: str
    original_value: Optional[str] = None
    corrected_value: str
    correction_type: str
    reviewer_notes: Optional[str] = None
    reviewer_id: Optional[str] = None


class FieldUpdate(BaseModel):
    field: str          # dot-delimited path e.g. "catalyst.surface_area"
    value: Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(val) if val not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _row_to_experiment(row: dict) -> ExperimentResponse:
    return ExperimentResponse(
        id=int(row["id"]),
        paper_id=int(row["paper_id"]),
        paper_identifier=row.get("paper_identifier", ""),
        experiment_number=int(row["experiment_number"]),
        domain_name=row.get("domain_name"),
        data=row.get("data_parsed") or {},
        overall_confidence=_parse_int(row.get("overall_confidence")),
        validation_status=row.get("validation_status", "pending"),
        review_notes=row.get("review_notes"),
        needs_review=row.get("needs_review", "True") == "True",
        extracted_at=row.get("extracted_at", ""),
    )


# ---------------------------------------------------------------------------
# Validation queue
# ---------------------------------------------------------------------------

@router.get("/queue", response_model=List[QueueItemResponse])
def get_validation_queue(
    status: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    store = get_store()
    rows = store.list_experiments(
        validation_status=status or "pending",
        limit=limit,
        offset=offset,
    )
    # Sort by overall_confidence asc (lowest confidence first for review)
    rows.sort(key=lambda r: _parse_int(r.get("overall_confidence"), 99) or 99)
    return [
        QueueItemResponse(
            experiment_id=int(r["id"]),
            paper_identifier=r.get("paper_identifier", ""),
            experiment_number=int(r["experiment_number"]),
            validation_status=r.get("validation_status", "pending"),
            overall_confidence=_parse_int(r.get("overall_confidence")),
            review_notes=r.get("review_notes"),
            needs_review=r.get("needs_review", "True") == "True",
        )
        for r in rows
    ]


@router.get("/queue/stats")
def get_queue_stats():
    store = get_store()
    all_exp = store.list_experiments(limit=100_000)
    counts: Dict[str, int] = {}
    for r in all_exp:
        s = r.get("validation_status", "pending")
        counts[s] = counts.get(s, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------

@router.get("/papers", response_model=List[PaperResponse])
def get_papers(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    store = get_store()
    rows = store.list_papers(search=search, status=status, limit=limit, offset=offset)
    return [
        PaperResponse(
            id=int(r["id"]),
            paper_identifier=r["paper_identifier"],
            title=r["title"],
            domain_name=r.get("domain_name"),
            processing_status=r.get("processing_status", "pending"),
            created_at=r.get("created_at", ""),
            experiment_count=int(r.get("experiment_count", 0)),
        )
        for r in rows
    ]


@router.get("/papers/{paper_id}", response_model=PaperResponse)
def get_paper(paper_id: int):
    store = get_store()
    row = store.get_paper(paper_id)
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    exp_count = len(store.list_experiments(paper_id=paper_id, limit=100_000))
    return PaperResponse(
        id=int(row["id"]),
        paper_identifier=row["paper_identifier"],
        title=row["title"],
        domain_name=row.get("domain_name"),
        processing_status=row.get("processing_status", "pending"),
        created_at=row.get("created_at", ""),
        experiment_count=exp_count,
    )


@router.get("/papers/{paper_id}/experiments", response_model=List[ExperimentResponse])
def get_paper_experiments(paper_id: int):
    store = get_store()
    rows = store.list_experiments(paper_id=paper_id, limit=1000)
    return [_row_to_experiment(r) for r in rows]


# ---------------------------------------------------------------------------
# Experiments & HITL
# ---------------------------------------------------------------------------

@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: int):
    store = get_store()
    row = store.get_experiment(experiment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return _row_to_experiment(row)


@router.post("/experiments/{experiment_id}/validate")
def validate_experiment(experiment_id: int, update: ValidationUpdate):
    store = get_store()
    row = store.get_experiment(experiment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")
    store.update_experiment_validation(
        experiment_id=experiment_id,
        validation_status=update.validation_status,
        reviewer_notes=update.reviewer_notes or "",
    )
    return {"message": "Validation updated successfully"}


@router.put("/experiments/{experiment_id}")
def update_experiment_field(experiment_id: int, update: FieldUpdate):
    store = get_store()
    row = store.get_experiment(experiment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")

    original = store.update_experiment_field(experiment_id, update.field, update.value)

    # Log correction
    store.add_correction(
        experiment_id=experiment_id,
        field_path=update.field,
        original_value=original,
        corrected_value=update.value,
        correction_type="edit",
        reviewer_notes="Inline field update from UI",
    )
    return {"message": "Field updated", "field": update.field, "original": original, "new": update.value}


@router.get("/experiments/{experiment_id}/corrections")
def get_corrections(experiment_id: int):
    store = get_store()
    return store.list_corrections(experiment_id)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
def get_stats():
    store = get_store()
    return StatsResponse(**store.get_stats())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _flatten(d: dict, parent: str = "", sep: str = ".") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{parent}{sep}{k}" if parent else k
        if isinstance(v, dict):
            out.update(_flatten(v, key, sep))
        else:
            out[key] = v
    return out


@router.get("/export/csv")
def export_csv(status: Optional[str] = None):
    store = get_store()
    rows = store.list_experiments(validation_status=status, limit=100_000)

    if not rows:
        return StreamingResponse(iter(["No data"]), media_type="text/csv")

    flat_rows = []
    all_keys: set = set()
    base_keys = ["id", "paper_identifier", "experiment_number", "validation_status", "overall_confidence"]

    for r in rows:
        flat_data = _flatten(r.get("data_parsed") or {})
        all_keys.update(flat_data.keys())
        flat_rows.append({
            "id": r["id"],
            "paper_identifier": r.get("paper_identifier", ""),
            "experiment_number": r["experiment_number"],
            "validation_status": r.get("validation_status", ""),
            "overall_confidence": r.get("overall_confidence", ""),
            **flat_data,
        })

    fieldnames = base_keys + sorted(all_keys - set(base_keys))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(flat_rows)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rxn_extractor_export.csv"},
    )


@router.get("/export/json")
def export_json(status: Optional[str] = None):
    store = get_store()
    rows = store.list_experiments(validation_status=status, limit=100_000)
    result = [
        {
            "id": r["id"],
            "paper_identifier": r.get("paper_identifier", ""),
            "experiment_number": r["experiment_number"],
            "validation_status": r.get("validation_status", ""),
            "overall_confidence": r.get("overall_confidence"),
            "data": r.get("data_parsed") or {},
        }
        for r in rows
    ]
    return StreamingResponse(
        iter([json.dumps(result, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=rxn_extractor_export.json"},
    )


# ---------------------------------------------------------------------------
# Batch status
# ---------------------------------------------------------------------------

@router.get("/batch/status")
def get_batch_status():
    store = get_store()
    return {
        "active_job": store.get_active_batch_job(),
        "recent_jobs": store.list_batch_jobs(limit=5),
    }
