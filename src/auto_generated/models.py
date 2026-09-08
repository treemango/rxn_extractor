from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime


class CatalystExtraction(BaseModel):
    catalyst_name: Optional[str] = Field(None)
    catalyst_class: Optional[str] = Field(None)
    exposed_facet: Optional[str] = Field(None)
    active_metal: Optional[str] = Field(None)
    metal_loading: Optional[str] = Field(None)
    support: Optional[str] = Field(None)
    support_topology: Optional[str] = Field(None)
    surface_area_value: Optional[float] = Field(None, gt=0)
    surface_area_unit: Optional[str] = Field(None)
    catalyst_deactivation: Optional[str] = Field(None)
    confidence_score: int = Field(ge=1, le=5)
    source_quote: str = Field(default='N/A', min_length=3)

class ConditionsExtraction(BaseModel):
    reactor_type: Optional[str] = Field(None)
    temperature_min: Optional[float] = Field(None)
    temperature_max: Optional[float] = Field(None)
    temperature_unit: Optional[str] = Field(None)
    pressure_value: Optional[float] = Field(None, gt=0)
    pressure_unit: Optional[str] = Field(None)
    space_velocity_value: Optional[float] = Field(None, gt=0)
    space_velocity_unit: Optional[str] = Field(None)
    feed_composition: Optional[str] = Field(None)
    testing_time_min: Optional[float] = Field(None)
    testing_time_max: Optional[float] = Field(None)
    testing_time_unit: Optional[str] = Field(None)
    @field_validator('temperature_max')
    @classmethod
    def check_temperature_range(cls, v, info):
        if v is not None and info.data.get('temperature_min') is not None:
            if v < info.data['temperature_min']:
                raise ValueError('temperature_max must be >= temperature_min')
        return v
    @field_validator('testing_time_max')
    @classmethod
    def check_testing_time_range(cls, v, info):
        if v is not None and info.data.get('testing_time_min') is not None:
            if v < info.data['testing_time_min']:
                raise ValueError('testing_time_max must be >= testing_time_min')
        return v
    confidence_score: int = Field(ge=1, le=5)
    source_quote: str = Field(default='N/A', min_length=3)

class PerformanceExtraction(BaseModel):
    ethylene_conversion_value: Optional[float] = Field(None, gt=0)
    ethylene_conversion_unit: Optional[str] = Field(None)
    c8_c16_selectivity_value: Optional[float] = Field(None, gt=0)
    c8_c16_selectivity_unit: Optional[str] = Field(None)
    isomers_selectivity_value: Optional[float] = Field(None, gt=0)
    isomers_selectivity_unit: Optional[str] = Field(None)
    yield_value: Optional[float] = Field(None, gt=0)
    yield_unit: Optional[str] = Field(None)
    reaction_rate_value: Optional[float] = Field(None, gt=0)
    reaction_rate_unit: Optional[str] = Field(None)
    turnover_frequency_value: Optional[float] = Field(None, gt=0)
    turnover_frequency_unit: Optional[str] = Field(None)
    specific_mechanism: Optional[str] = Field(None)
    confidence_score: int = Field(ge=1, le=5)
    source_quote: str = Field(default='N/A', min_length=3)

class MetadataExtraction(BaseModel):
    doi: Optional[str] = Field(None)
    year_of_publication_value: Optional[float] = Field(None, gt=0)
    year_of_publication_unit: Optional[str] = Field(None)
    journal: Optional[str] = Field(None)
    confidence_score: int = Field(ge=1, le=5)
    source_quote: str = Field(default='N/A', min_length=3)

class ExperimentMetadata(BaseModel):
    experiment_number: int
    brief_description: str
    key_parameters: str
    confidence: int = Field(ge=1, le=5)

class ParserOutput(BaseModel):
    total_experiments: int
    experiments: List[ExperimentMetadata]
    extraction_notes: Optional[str] = None

class ExperimentExtraction(BaseModel):
    experiment_id: str
    paper_id: str
    overall_confidence: int = Field(ge=1, le=5)
    validation_status: str = 'pending'
    review_notes: Optional[str] = None
    needs_review: bool = False
    extraction_timestamp: datetime
    catalyst: Optional[CatalystExtraction] = None
    conditions: Optional[ConditionsExtraction] = None
    performance: Optional[PerformanceExtraction] = None
    metadata: Optional[MetadataExtraction] = None