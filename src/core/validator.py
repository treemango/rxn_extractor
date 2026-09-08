import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class Validator:
    """Deterministic validation engine for extraction data."""

    def __init__(self, config_module: Any):
        self.config_module = config_module

    def _check_bounds(self, sub_domain_name: str, field_name: str, value: float) -> Optional[str]:
        bounds = getattr(self.config_module, "VALIDATION_BOUNDS", {})
        key = f"{sub_domain_name}.{field_name}"
        if key in bounds:
            b = bounds[key]
            min_val = b.get("min")
            max_val = b.get("max")
            if min_val is not None and value < min_val:
                return f"Value {value} for {key} is below minimum {min_val}"
            if max_val is not None and value > max_val:
                return f"Value {value} for {key} is above maximum {max_val}"
        return None

    def _run_validation_rules(self, extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
        rules = getattr(self.config_module, "VALIDATION_RULES", [])
        results = []
        for rule in rules:
            if rule.get("type") == "sum_check":
                fields = rule.get("fields", [])
                expected = rule.get("expected_sum", 100.0)
                tol = rule.get("tolerance_percent", 5.0)
                
                total = 0.0
                missing_data = False
                for field_path in fields:
                    parts = field_path.split(".")
                    if len(parts) == 2:
                        sub, field = parts
                        sub_data = extraction.get(sub, {})
                        if not sub_data:
                            missing_data = True
                            continue
                            
                        val = sub_data.get(field)
                        if val is None:
                            # check if it's a range
                            min_v = sub_data.get(f"{field}_min")
                            max_v = sub_data.get(f"{field}_max")
                            if min_v is not None and max_v is not None:
                                val = (min_v + max_v) / 2.0
                            elif min_v is not None:
                                val = min_v
                            elif max_v is not None:
                                val = max_v
                        
                        if val is not None:
                            total += val
                        else:
                            missing_data = True
                    else:
                        missing_data = True
                            
                if missing_data:
                    status = "insufficient_data"
                else:
                    margin = expected * (tol / 100.0)
                    if abs(total - expected) <= margin:
                        status = "ok"
                    elif total < expected - margin:
                        status = "warning_low"
                    else:
                        status = "warning_high"
                        
                results.append({"name": rule.get("name", "sum_check"), "status": status, "total": total})
                
            elif rule.get("type") == "comparison":
                field1 = rule.get("field1")
                field2 = rule.get("field2")
                op = rule.get("operator")
                
                def get_val(fp):
                    parts = fp.split(".")
                    if len(parts) == 2:
                        data = extraction.get(parts[0], {})
                        if data:
                            return data.get(parts[1])
                    return None
                    
                v1 = get_val(field1)
                v2 = get_val(field2)
                
                if v1 is not None and v2 is not None:
                    status = False
                    if op == "<": status = v1 < v2
                    elif op == "<=": status = v1 <= v2
                    elif op == ">": status = v1 > v2
                    elif op == ">=": status = v1 >= v2
                    elif op == "==": status = v1 == v2
                    elif op == "!=": status = v1 != v2
                    results.append({"name": rule.get("name", "comparison"), "status": status})
                else:
                    results.append({"name": rule.get("name", "comparison"), "status": "insufficient_data"})
                    
        return results

    def _calculate_overall_confidence(self, sub_domain_results: Dict[str, Any]) -> int:
        scores = []
        for res in sub_domain_results.values():
            if res and isinstance(res, dict) and "confidence_score" in res:
                scores.append(res["confidence_score"])
        if not scores:
            return 1
        return min(scores)

    def _generate_review_notes(self, checks: Dict[str, Any], issues: List[str], confidence: int, extraction: Dict[str, Any]) -> str:
        conf_map = {1: "Very low", 2: "Low", 3: "Moderate", 4: "Good", 5: "High"}
        lines = []
        lines.append(f"Confidence Level: {confidence} - {conf_map.get(confidence, 'Unknown')}")
        lines.append("\nConsistency Checks:")
        for name, status in checks.items():
            if status in [True, "ok"]:
                lines.append(f"✓ {name}: Passed")
            else:
                lines.append(f"⚠ {name}: {status}")
                
        lines.append("\nData Quality Issues:")
        if not issues:
            lines.append("✓ No issues found.")
        else:
            for iss in issues:
                lines.append(f"⚠ {iss}")
                
        return "\n".join(lines)

    def validate(self, extraction: Dict[str, Any], sub_domain_results: Dict[str, Any]) -> Dict[str, Any]:
        consistency_checks = {}
        data_quality_issues = []
        
        # Check bounds
        for sub, data in sub_domain_results.items():
            if data and isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        issue = self._check_bounds(sub, k, v)
                        if issue:
                            data_quality_issues.append(issue)
        
        # Run validation rules
        rule_results = self._run_validation_rules(extraction)
        for r in rule_results:
            consistency_checks[r["name"]] = r["status"]
            if r["status"] not in [True, "ok", "insufficient_data"]:
                data_quality_issues.append(f"Rule {r['name']} failed with status: {r['status']}")
                
        overall_confidence = self._calculate_overall_confidence(sub_domain_results)
        needs_review = overall_confidence < 4 or len(data_quality_issues) > 0
        review_notes = self._generate_review_notes(consistency_checks, data_quality_issues, overall_confidence, extraction)
        
        return {
            "consistency_checks": consistency_checks,
            "data_quality_issues": data_quality_issues,
            "overall_confidence": overall_confidence,
            "needs_review": needs_review,
            "review_notes": review_notes
        }
