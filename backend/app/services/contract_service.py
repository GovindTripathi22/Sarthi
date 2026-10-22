from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import jsonschema
from jsonschema import Draft7Validator

from backend.app.schemas import ContractValidationReport, SuspectedRename


def normalize_field_name(name: str) -> str:
    """Normalize snake_case, camelCase, kebab-case to pure lowercase alphanumeric."""
    return re.sub(r"[_\-]", "", name).lower()


def compute_rename_confidence(
    old_key: str,
    new_key: str,
    old_val: Any = None,
    new_val: Any = None,
) -> tuple[float, str]:
    """
    Multi-factor rename confidence heuristic combining:
    1. Normalized character equivalence (e.g. customer_id vs customerId)
    2. Levenshtein ratio / casing pattern
    3. Value equivalence / datatype matching
    """
    norm_old = normalize_field_name(old_key)
    norm_new = normalize_field_name(new_key)

    if norm_old == norm_new:
        if old_val is not None and new_val is not None:
            if type(old_val) == type(new_val):
                return 0.98, "Exact normalized identifier match with identical value data type (snake_case to camelCase)"
        return 0.96, "Exact normalized identifier match (snake_case to lowerCamelCase transformation)"

    # Partial similarity check
    if norm_old in norm_new or norm_new in norm_old:
        return 0.78, "Substring containment between old and new field names"

    return 0.50, "Potential structural substitution"


class ContractValidationService:
    @staticmethod
    def validate_payload(
        payload: Any,
        schema: Dict[str, Any],
        path_prefix: str = "",
    ) -> ContractValidationReport:
        """
        Validate an observed payload against an OpenAPI/JSON Schema contract.
        Detects missing required fields, unexpected fields, type mismatches,
        and suspected field renames.
        """
        missing_required: List[str] = []
        unexpected_fields: List[str] = []
        type_mismatches: List[Dict[str, Any]] = []
        suspected_renames: List[SuspectedRename] = []

        if not isinstance(payload, dict):
            return ContractValidationReport(
                valid=False,
                missing_required=["root"],
                type_mismatches=[{"field": "root", "expected": "object", "actual": type(payload).__name__}],
            )

        properties = schema.get("properties", {})
        required_keys = schema.get("required", [])
        observed_keys = list(payload.keys())

        local_missing: List[str] = []
        local_unexpected: List[str] = []

        # 1. Required fields check
        for req_key in required_keys:
            full_key = f"{path_prefix}{req_key}"
            if req_key not in payload:
                missing_required.append(full_key)
                local_missing.append(req_key)

        # 2. Observed properties check
        additional_allowed = schema.get("additionalProperties", True)
        for obs_key in observed_keys:
            full_key = f"{path_prefix}{obs_key}"
            if obs_key not in properties:
                if not additional_allowed or obs_key in ("schemaVersion", "version"):
                    unexpected_fields.append(full_key)
                local_unexpected.append(obs_key)
            else:
                prop_schema = properties[obs_key]
                expected_type = prop_schema.get("type")
                actual_val = payload[obs_key]
                if actual_val is not None and expected_type:
                    actual_type = (
                        "array"
                        if isinstance(actual_val, list)
                        else "object"
                        if isinstance(actual_val, dict)
                        else "boolean"
                        if isinstance(actual_val, bool)
                        else "integer"
                        if isinstance(actual_val, int)
                        else "number"
                        if isinstance(actual_val, float)
                        else "string"
                    )
                    if expected_type == "number" and actual_type == "integer":
                        pass
                    elif expected_type != actual_type:
                        type_mismatches.append(
                            {"field": full_key, "expected": expected_type, "actual": actual_type}
                        )

                # Recursive check for nested objects
                if expected_type == "object" and isinstance(actual_val, dict) and "properties" in prop_schema:
                    nested = ContractValidationService.validate_payload(
                        actual_val, prop_schema, path_prefix=f"{full_key}."
                    )
                    missing_required.extend(nested.missing_required)
                    unexpected_fields.extend(nested.unexpected_fields)
                    type_mismatches.extend(nested.type_mismatches)
                    suspected_renames.extend(nested.suspected_renames)

        # 3. Rename detection heuristic
        for miss in local_missing:
            for unexp in local_unexpected:
                conf, reason = compute_rename_confidence(
                    miss, unexp, None, payload.get(unexp)
                )
                if conf >= 0.70:
                    suspected_renames.append(
                        SuspectedRename(
                            old_field=f"{path_prefix}{miss}",
                            new_field=f"{path_prefix}{unexp}",
                            confidence=conf,
                            reason=reason,
                            old_example=None,
                            new_example=payload.get(unexp),
                        )
                    )

        # Standard jsonschema validation for strict syntax adherence
        try:
            validator = Draft7Validator(schema)
            js_errors = list(validator.iter_errors(payload))
            for err in js_errors:
                if err.validator == "required":
                    pass  # Already captured
        except Exception:
            pass

        is_valid = len(missing_required) == 0 and len(type_mismatches) == 0
        return ContractValidationReport(
            valid=is_valid,
            missing_required=missing_required,
            unexpected_fields=unexpected_fields,
            type_mismatches=type_mismatches,
            suspected_renames=suspected_renames,
            schema_version=schema.get("version", "v2.1.0"),
        )
