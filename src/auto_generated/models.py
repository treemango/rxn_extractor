from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from datetime import datetime


class CatalystExtraction(BaseModel):
    model_config = {'extra': 'ignore'}  # silently drop unknown keys from LLM

    catalyst_name: Optional[str] = Field(None)
    catalyst_class: Optional[str] = Field(None)
    exposed_facet: Optional[str] = Field(None)
    active_metal: Optional[str] = Field(None)
    metal_loading: Optional[str] = Field(None)
    support: Optional[str] = Field(None)
    support_topology: Optional[str] = Field(None)
    surface_area_value: Optional[float] = Field(None)
    surface_area_unit: Optional[str] = Field(None)
    catalyst_deactivation: Optional[str] = Field(None)

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
    pressure_value: Optional[float] = Field(None)
    pressure_unit: Optional[str] = Field(None)
    space_velocity_value: Optional[float] = Field(None)
    space_velocity_unit: Optional[str] = Field(None)
    feed_composition: Optional[str] = Field(None)
    testing_time_min: Optional[float] = Field(None)
    testing_time_max: Optional[float] = Field(None)
    testing_time_unit: Optional[str] = Field(None)

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

class PerformanceExtraction(BaseModel):
    model_config = {'extra': 'ignore'}  # silently drop unknown keys from LLM

    ethylene_conversion_value: Optional[float] = Field(None)
    ethylene_conversion_unit: Optional[str] = Field(None)
    c8_c16_selectivity_value: Optional[float] = Field(None)
    c8_c16_selectivity_unit: Optional[str] = Field(None)
    isomers_selectivity_value: Optional[float] = Field(None)
    isomers_selectivity_unit: Optional[str] = Field(None)
    yield_value: Optional[float] = Field(None)
    yield_unit: Optional[str] = Field(None)
    reaction_rate_value: Optional[float] = Field(None)
    reaction_rate_unit: Optional[str] = Field(None)
    turnover_frequency_value: Optional[float] = Field(None)
    turnover_frequency_unit: Optional[str] = Field(None)
    specific_mechanism: Optional[str] = Field(None)

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

class MetadataExtraction(BaseModel):
    model_config = {'extra': 'ignore'}  # silently drop unknown keys from LLM

    doi: Optional[str] = Field(None)
    year_of_publication_value: Optional[float] = Field(None)
    year_of_publication_unit: Optional[str] = Field(None)
    journal: Optional[str] = Field(None)

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
    model_config = {'extra': 'ignore'}
    experiment_number: int = Field(default=1)
    brief_description: str = Field(default='')
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
    performance: Optional[PerformanceExtraction] = None
    metadata: Optional[MetadataExtraction] = None
