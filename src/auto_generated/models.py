from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from datetime import datetime


class CatalystExtraction(BaseModel):
    model_config = {'extra': 'ignore'}  # silently drop unknown keys from LLM

    catalyst_class: Optional[str] = Field(None)
    catalyst_name: Optional[str] = Field(None)
    active_metal: Optional[str] = Field(None)
    metal_loading_value: Optional[float] = Field(None)
    metal_loading_unit: Optional[str] = Field(None)
    support_identity: Optional[str] = Field(None)
    preparation_method: Optional[str] = Field(None)
    pretreatment_or_activation: Optional[str] = Field(None)
    surface_area_value: Optional[float] = Field(None)
    surface_area_unit: Optional[str] = Field(None)
    pore_diameter_value: Optional[float] = Field(None)
    pore_diameter_unit: Optional[str] = Field(None)
    pore_volume_value: Optional[float] = Field(None)
    pore_volume_unit: Optional[str] = Field(None)
    total_acidity_value: Optional[float] = Field(None)
    total_acidity_unit: Optional[str] = Field(None)
    bronsted_acid_site_density_value: Optional[float] = Field(None)
    bronsted_acid_site_density_unit: Optional[str] = Field(None)
    lewis_acid_site_density_value: Optional[float] = Field(None)
    lewis_acid_site_density_unit: Optional[str] = Field(None)

    confidence_score: Optional[int] = Field(None)
    source_quote: Optional[str] = Field(None)

    @field_validator('confidence_score', mode='before')
    @classmethod
    def clamp_confidence(cls, v):
        if v is None:
            return 3  # default mid-range if missing
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return 3

class ConditionsExtraction(BaseModel):
    model_config = {'extra': 'ignore'}  # silently drop unknown keys from LLM

    reactor_type: Optional[str] = Field(None)
    temperature_min: Optional[float] = Field(None)
    temperature_max: Optional[float] = Field(None)
    temperature_unit: Optional[str] = Field(None)
    total_pressure_value: Optional[float] = Field(None)
    total_pressure_unit: Optional[str] = Field(None)
    ethylene_partial_pressure_value: Optional[float] = Field(None)
    ethylene_partial_pressure_unit: Optional[str] = Field(None)
    whsv_value: Optional[float] = Field(None)
    whsv_unit: Optional[str] = Field(None)
    ghsv_value: Optional[float] = Field(None)
    ghsv_unit: Optional[str] = Field(None)
    time_on_stream_min: Optional[float] = Field(None)
    time_on_stream_max: Optional[float] = Field(None)
    time_on_stream_unit: Optional[str] = Field(None)

    confidence_score: Optional[int] = Field(None)
    source_quote: Optional[str] = Field(None)

    @field_validator('confidence_score', mode='before')
    @classmethod
    def clamp_confidence(cls, v):
        if v is None:
            return 3  # default mid-range if missing
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return 3

class ExperimentMetadata(BaseModel):
    """
    Enriched metadata for a single experiment extracted by the Parser agent.
    These fields act as a precise pointer so subdomain agents know exactly
    which experiment to look at in the paper, without reading the whole thing.
    """
    model_config = {'extra': 'ignore'}
    experiment_number: int = Field(default=1)
    brief_description: str = Field(default='')
    # ── Concrete pointers — new fields ─────────────────────────────────
    catalyst_name: Optional[str] = Field(None,
        description='Catalyst or system name as written in the paper, e.g. 1/Ni(COD)2')
    reactant: Optional[str] = Field(None,
        description='Primary reactant or feedstock, e.g. ethylene, HDPE')
    main_temperature: Optional[str] = Field(None,
        description='Primary reaction temperature as written, e.g. 80°C or 80-105°C')
    main_pressure: Optional[str] = Field(None,
        description='Operating pressure as written, e.g. 30 atm or 20-35 atm')
    products_mentioned: Optional[str] = Field(None,
        description='Key products mentioned, e.g. butene-1, hexene-1')
    key_section: Optional[str] = Field(None,
        description='Exact table/section reference, e.g. Table 1 Row 1, Table 2 Test 3')
    key_parameters: str = Field(default='')
    confidence: Optional[int] = Field(None)

    @field_validator('confidence', mode='before')
    @classmethod
    def clamp_exp_confidence(cls, v):
        if v is None:
            return 3
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return 3

class ParserOutput(BaseModel):
    model_config = {'extra': 'ignore'}
    total_experiments: int = Field(default=0)
    experiments: List[ExperimentMetadata] = Field(default_factory=list)
    extraction_notes: Optional[str] = None

class ExperimentExtraction(BaseModel):
    model_config = {'extra': 'ignore'}
    experiment_id: str
    paper_id: str
    overall_confidence: int = Field(default=3, ge=1, le=5)
    validation_status: str = 'pending'
    review_notes: Optional[str] = None
    needs_review: bool = False
    extraction_timestamp: datetime
    catalyst: Optional[CatalystExtraction] = None
    conditions: Optional[ConditionsExtraction] = None
