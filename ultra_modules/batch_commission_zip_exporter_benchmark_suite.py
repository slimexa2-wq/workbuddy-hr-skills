import csv
import io
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

def process_commission_data(data: List[Dict[str, Any]], default_supplier: str = "Unknown Supplier") -> Dict[str, bytes]:
    """
    Processes a batch of commission data, adding reconciliation columns (e.g. status, and audit column).
    Groups data by supplier and creates an in-memory zip file for each supplier containing a CSV.

    Args:
        data: List of dictionaries representing commission data rows.
        default_supplier: Default supplier name if 'supplier' is missing or dirty.

    Returns:
        Dict mapping supplier name to the zip file bytes.
    """
    if not data:
        return {}

    # Grouping data
    grouped_data = defaultdict(list)
    fieldnames = set()

    for row in data:
        # Fallback/Dirty data self-healing
        if not isinstance(row, dict):
            continue

        supplier = row.get("supplier")
        if not supplier or not isinstance(supplier, str) or not supplier.strip():
            supplier = default_supplier

        clean_row = {}
        for k, v in row.items():
            if not isinstance(k, str) or not k.strip():
                continue # ignore dirty keys
            clean_row[k] = "" if v is None else str(v)

        # Add reconciliation columns
        clean_row["supplier"] = supplier
        clean_row["《（审核版）》"] = "已核对"
        if not clean_row.get("status"):
            clean_row["status"] = "processed"

        grouped_data[supplier].append(clean_row)
        fieldnames.update(clean_row.keys())

    if not grouped_data:
        return {}

    # Sort fieldnames to have deterministic order, but put supplier and new columns first
    sorted_fieldnames = sorted(list(fieldnames))

    # We always add these columns, so we can safely remove and re-insert them
    sorted_fieldnames.remove("supplier")
    sorted_fieldnames.insert(0, "supplier")

    sorted_fieldnames.remove("《（审核版）》")
    sorted_fieldnames.append("《（审核版）》")

    sorted_fieldnames.remove("status")
    sorted_fieldnames.append("status")

    def _create_zip_for_supplier(supplier_name: str, rows: List[Dict[str, str]]) -> tuple[str, bytes]:
        # Create CSV
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=sorted_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        csv_data = csv_buffer.getvalue().encode('utf-8-sig') # with BOM for Excel compatibility

        # Create Zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{supplier_name}_commissions.csv", csv_data)

        return supplier_name, zip_buffer.getvalue()

    # Process in parallel
    results = {}
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(_create_zip_for_supplier, supplier, rows)
            for supplier, rows in grouped_data.items()
        ]

        for future in futures:
            supplier_name, zip_bytes = future.result()
            results[supplier_name] = zip_bytes

    return results
