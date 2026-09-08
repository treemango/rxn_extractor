import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_models(domain: Dict[str, Any], output_path: str) -> None:
    """
    Generates Pydantic models based on the domain definition.
    """
    logger.info(f"Generating models at {output_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    lines = [
        "from typing import Optional, List, Any",
        "from pydantic import BaseModel, Field, field_validator",
        "from enum import Enum",
        "from datetime import datetime",
        "",
        ""
    ]
    
    sub_domain_classes = []
    
    for sub in domain.get('sub_domains', []):
        sub_name = "".join(x.title() for x in sub['name'].split('_'))
        class_name = f"{sub_name}Extraction"
        sub_domain_classes.append((sub['name'], class_name))
        
        # Enums
        for field in sub.get('fields', []):
            if field.get('type') == 'enum':
                enum_name = "".join(x.title() for x in field['name'].split('_')) + "Enum"
                lines.append(f"class {enum_name}(str, Enum):")
                for val in field.get('allowed_values', []):
                    # Clean up value for variable name
                    var_name = val.upper().replace(' ', '_').replace('-', '_')
                    lines.append(f"    {var_name} = '{val}'")
                lines.append("")
        
        # Class definition
        lines.append(f"class {class_name}(BaseModel):")
        
        for field in sub.get('fields', []):
            f_name = field['name']
            f_type = field.get('type')
            
            if f_type == 'float':
                lines.append(f"    {f_name}_value: Optional[float] = Field(None, gt=0)")
                lines.append(f"    {f_name}_unit: Optional[str] = Field(None)")
            elif f_type == 'range':
                lines.append(f"    {f_name}_min: Optional[float] = Field(None)")
                lines.append(f"    {f_name}_max: Optional[float] = Field(None)")
                lines.append(f"    {f_name}_unit: Optional[str] = Field(None)")
            elif f_type == 'enum':
                enum_name = "".join(x.title() for x in f_name.split('_')) + "Enum"
                lines.append(f"    {f_name}: Optional[{enum_name}] = Field(None)")
            elif f_type == 'string':
                lines.append(f"    {f_name}: Optional[str] = Field(None)")
                
        # Range validators (Pydantic v2 style)
        for field in sub.get('fields', []):
            f_name = field['name']
            f_type = field.get('type')
            if f_type == 'range':
                lines.append(f"    @field_validator('{f_name}_max')")
                lines.append(f"    @classmethod")
                lines.append(f"    def check_{f_name}_range(cls, v, info):")
                lines.append(f"        if v is not None and info.data.get('{f_name}_min') is not None:")
                lines.append(f"            if v < info.data['{f_name}_min']:")
                lines.append(f"                raise ValueError('{f_name}_max must be >= {f_name}_min')")
                lines.append(f"        return v")

        lines.append(f"    confidence_score: int = Field(ge=1, le=5)")
        lines.append(f"    source_quote: str = Field(default='N/A', min_length=3)")
        lines.append("")
        
    # Parser Output Models
    lines.extend([
        "class ExperimentMetadata(BaseModel):",
        "    experiment_number: int",
        "    brief_description: str",
        "    key_parameters: str",
        "    confidence: int = Field(ge=1, le=5)",
        "",
        "class ParserOutput(BaseModel):",
        "    total_experiments: int",
        "    experiments: List[ExperimentMetadata]",
        "    extraction_notes: Optional[str] = None",
        ""
    ])
    
    # Envelope Model
    lines.append("class ExperimentExtraction(BaseModel):")
    lines.append("    experiment_id: str")
    lines.append("    paper_id: str")
    lines.append("    overall_confidence: int = Field(ge=1, le=5)")
    lines.append("    validation_status: str = 'pending'")
    lines.append("    review_notes: Optional[str] = None")
    lines.append("    needs_review: bool = False")
    lines.append("    extraction_timestamp: datetime")
    
    for _, class_name in sub_domain_classes:
        f_name = "".join(['_'+i.lower() if i.isupper() else i for i in class_name]).lstrip('_').replace('_extraction', '')
        lines.append(f"    {f_name}: Optional[{class_name}] = None")
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    logger.info("Models generated successfully")
