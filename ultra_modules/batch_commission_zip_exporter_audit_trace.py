import csv
import io
import json
import logging
import zipfile
from collections import defaultdict
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

def process_commissions(raw_data: List[Dict[str, Any]]) -> Dict[str, bytes]:
    """
    Processes a list of raw commission records, applies auto-healing, deduplication,
    default fallbacks, and groups them by vendor. For each vendor, creates a ZIP archive
    containing the audited CSV and the audit trace JSON.

    Zero configuration: just pass the raw data, and we return a dict mapping
    vendor names to their respective ZIP file bytes.

    Expected raw_data fields (best effort):
    - vendor_name (fallback: 'Unknown_Vendor')
    - project_id (fallback: 'Unknown_Project')
    - amount (fallback: 0.0, string values auto-converted/cleaned)
    - record_id (used for deduplication, fallback: generated sequentially if missing)
    """
    if not raw_data:
        logger.warning("Empty raw data provided.")
        return {}

    vendor_grouped_records = defaultdict(list)
    audit_logs = defaultdict(list)
    seen_records = defaultdict(set)

    for i, record in enumerate(raw_data):
        trace = {"original_record": record.copy(), "modifications": [], "action": "kept"}

        # 1. vendor_name fallback
        vendor_name = record.get("vendor_name")
        if not vendor_name or not isinstance(vendor_name, str) or not vendor_name.strip():
            vendor_name = "Unknown_Vendor"
            trace["modifications"].append("Set default vendor_name to Unknown_Vendor")
        else:
            vendor_name = vendor_name.strip()

        # 2. project_id fallback
        project_id = record.get("project_id")
        if not project_id or not isinstance(project_id, str) or not project_id.strip():
            project_id = "Unknown_Project"
            trace["modifications"].append("Set default project_id to Unknown_Project")
        else:
            project_id = project_id.strip()

        # 3. amount cleaning and fallback
        raw_amount = record.get("amount", 0)
        cleaned_amount = 0.0
        try:
            if isinstance(raw_amount, (int, float)):
                cleaned_amount = float(raw_amount)
            elif isinstance(raw_amount, str):
                cleaned_amount = float(raw_amount.replace(",", "").strip())
        except ValueError:
            trace["modifications"].append(f"Failed to parse amount '{raw_amount}', defaulted to 0.0")
            cleaned_amount = 0.0

        if cleaned_amount != raw_amount:
            if isinstance(raw_amount, str):
                trace["modifications"].append(f"Cleaned string amount '{raw_amount}' to float {cleaned_amount}")

        # 4. record_id generation / deduplication
        record_id = record.get("record_id")
        if not record_id:
            record_id = f"generated_id_{i}"
            trace["modifications"].append(f"Generated missing record_id: {record_id}")

        if record_id in seen_records[vendor_name]:
            trace["action"] = "dropped_duplicate"
            trace["modifications"].append("Dropped duplicate record_id")
            audit_logs[vendor_name].append(trace)
            continue

        seen_records[vendor_name].add(record_id)

        # Build clean record
        clean_record = {
            "record_id": record_id,
            "vendor_name": vendor_name,
            "project_id": project_id,
            "amount": cleaned_amount,
            "audit_flag": "OK" if not trace["modifications"] else "HEALED"
        }

        vendor_grouped_records[vendor_name].append(clean_record)
        audit_logs[vendor_name].append(trace)

    # Generate ZIP archives per vendor
    result_zips = {}
    for vendor, records in vendor_grouped_records.items():
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Create CSV
            csv_buffer = io.StringIO()
            if records:
                fieldnames = ["record_id", "vendor_name", "project_id", "amount", "audit_flag"]
                writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                writer.writeheader()
                for rec in records:
                    writer.writerow(rec)

            zf.writestr(f"{vendor}_audited_commissions.csv", csv_buffer.getvalue())

            # Create Audit JSON
            audit_json = json.dumps(audit_logs[vendor], ensure_ascii=False, indent=2)
            zf.writestr(f"{vendor}_audit_trace.json", audit_json)

        result_zips[vendor] = zip_buffer.getvalue()

    return result_zips
