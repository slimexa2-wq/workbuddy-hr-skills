import logging
from typing import Dict, Any, List, Union
from ultra_modules.batch_commission_zip_exporter_core_engine import process_and_package_commissions

# Setup minimal logging for silent background tracking
logger = logging.getLogger(__name__)

# Predefined mappings for older or different schema versions
# Map variations to the target canonical fields
SCHEMA_MAPPINGS = {
    # Variations for supplier_name
    "vendor": "supplier_name",
    "vendor_id": "supplier_name",
    "vendor_name": "supplier_name",
    "supplier": "supplier_name",
    "provider": "supplier_name",
    "partner": "supplier_name",
    "partner_name": "supplier_name",

    # Variations for commission_amount
    "amount": "commission_amount",
    "value": "commission_amount",
    "commission_value": "commission_amount",
    "commission": "commission_amount",
    "fee": "commission_amount",
    "commission_fee": "commission_amount",
    "payout": "commission_amount",
    "bonus": "commission_amount"
}

def auto_convert_schema(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Silently converts old/different schema fields to the new expected schema.
    """
    if not isinstance(row, dict):
        return {}

    converted_row = {}
    for key, val in row.items():
        # Clean the key to make matching robust
        clean_key = str(key).strip().lower()

        # Check if the key needs to be mapped
        target_key = SCHEMA_MAPPINGS.get(clean_key, key)

        # In case of conflicts (e.g. both 'vendor' and 'supplier_name' exist),
        # we will prefer to keep both but ensure the canonical one is populated
        # correctly. The target_key takes precedence for mapping.

        if target_key not in converted_row or converted_row[target_key] in (None, ""):
            converted_row[target_key] = val

        # Also preserve original key just in case it's needed down the line
        if key not in converted_row:
            converted_row[key] = val

    return converted_row

def process_integration_payload(
    payload: Union[List[Dict[str, Any]], Dict[str, Any], None] = None,
    default_verifier: str = "System_Auto",
    default_audit_note: str = "Auto-verified by batch engine"
) -> bytes:
    """
    Integration bridge for multi-project supplier commission zip exporter.
    Automatically identifies schema differences between old and new versions,
    silently mappings/converting them without manual configuration.

    Args:
        payload: Cross-system integration payload (List of dicts, single dict, or None)
        default_verifier: The fallback verifier name for auditing
        default_audit_note: The fallback audit note for auditing

    Returns:
        bytes: The resulting ZIP archive payload returned by the core engine.
    """
    logger.info("Received integration payload for commission export.")

    # 1. Zero-configuration auto-healing: input normalization
    if payload is None:
        normalized_payload = []
    elif isinstance(payload, dict):
        # Could be a wrapper like {"data": [...]} or a single record
        if "data" in payload and isinstance(payload["data"], list):
            normalized_payload = payload["data"]
        elif "records" in payload and isinstance(payload["records"], list):
            normalized_payload = payload["records"]
        else:
            normalized_payload = [payload]
    elif isinstance(payload, list):
        normalized_payload = payload
    else:
        # Fallback for unexpected types
        try:
            normalized_payload = list(payload)
        except Exception:
            normalized_payload = []
            logger.warning("Failed to normalize payload, falling back to empty list.")

    # 2. Schema auto-conversion (forward compatibility)
    converted_records = []
    for item in normalized_payload:
        if not isinstance(item, dict):
            # Skip invalid items or convert to empty dict to let core engine handle
            continue

        converted_item = auto_convert_schema(item)
        converted_records.append(converted_item)

    # 3. Delegate to core engine
    logger.info(f"Delegating {len(converted_records)} converted records to core engine.")
    return process_and_package_commissions(
        records=converted_records,
        default_verifier=default_verifier,
        default_audit_note=default_audit_note
    )
