import logging
from typing import Any, Tuple

logger = logging.getLogger(__name__)

def normalize_range_field(
    min_val: Any, 
    max_val: Any, 
    extracted_unit: str, 
    target_unit: str, 
    conversions: dict
) -> Tuple[Any, Any, str]:
    """Convert both min and max values using the conversion function."""
    if not extracted_unit or not target_unit:
        return min_val, max_val, extracted_unit
        
    conv_key = (extracted_unit, target_unit)
    if conv_key in conversions:
        conv_func = conversions[conv_key]
        conv_min = conv_func(min_val) if min_val is not None else None
        conv_max = conv_func(max_val) if max_val is not None else None
        return conv_min, conv_max, target_unit
        
    return min_val, max_val, extracted_unit

def normalize_extraction(extraction_data: dict, config_module: Any) -> dict:
    """Deterministic unit conversion based on config module definitions."""
    normalized = dict(extraction_data)
    validation_bounds = getattr(config_module, "VALIDATION_BOUNDS", {})
    unit_conversions = getattr(config_module, "UNIT_CONVERSIONS", {})
    
    for key, value in list(normalized.items()):
        if key.endswith("_unit"):
            name = key[:-5]  # remove '_unit'
            extracted_unit = value
            if not extracted_unit:
                continue
                
            # Find target unit by matching the suffix in VALIDATION_BOUNDS
            target_unit = None
            for b_key, b_val in validation_bounds.items():
                if b_key.endswith(f".{name}"):
                    target_unit = b_val.get("target_unit")
                    break
                    
            if not target_unit or extracted_unit == target_unit:
                continue
                
            conv_key = (extracted_unit, target_unit)
            if conv_key in unit_conversions:
                conv_func = unit_conversions[conv_key]
                
                # Single value field
                if name in normalized and normalized[name] is not None:
                    try:
                        normalized[name] = conv_func(normalized[name])
                        normalized[key] = target_unit
                    except Exception as e:
                        logger.warning(f"Conversion failed for {name}: {e}")
                        normalized["_normalization_warning"] = True
                        
                # Range field
                elif f"{name}_min" in normalized or f"{name}_max" in normalized:
                    min_v = normalized.get(f"{name}_min")
                    max_v = normalized.get(f"{name}_max")
                    
                    try:
                        conv_min, conv_max, t_unit = normalize_range_field(
                            min_v, max_v, extracted_unit, target_unit, unit_conversions
                        )
                        if conv_min is not None: 
                            normalized[f"{name}_min"] = conv_min
                        if conv_max is not None: 
                            normalized[f"{name}_max"] = conv_max
                        normalized[key] = t_unit
                    except Exception as e:
                        logger.warning(f"Range conversion failed for {name}: {e}")
                        normalized["_normalization_warning"] = True
            else:
                logger.warning(f"Unrecognized unit conversion: {extracted_unit} -> {target_unit}")
                normalized["_normalization_warning"] = True

    return normalized
