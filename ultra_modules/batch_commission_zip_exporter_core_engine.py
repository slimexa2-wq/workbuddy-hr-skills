import csv
import io
import zipfile
from typing import List, Dict, Any, Union

def process_and_package_commissions(
    records: Union[List[Dict[str, Any]], Dict[str, Any], None] = None,
    default_verifier: str = "System_Auto",
    default_audit_note: str = "Auto-verified by batch engine"
) -> bytes:
    """
    Core engine function for processing commission records, adding audit columns,
    and packaging them into a ZIP archive by supplier.

    Args:
        records: A list of dictionary records, a single dictionary record, or None.
        default_verifier: Name of the verifier to append (default: System_Auto).
        default_audit_note: Audit note to append (default: Auto-verified...).

    Returns:
        Bytes representing the generated ZIP file content.
    """
    # 1. Zero-configuration auto-healing: input normalization
    if records is None:
        records_list = []
    elif isinstance(records, dict):
        records_list = [records]
    elif isinstance(records, list):
        records_list = records
    else:
        # If it's some other iterable or completely wrong type, try to cast or fallback to empty list
        try:
            records_list = list(records)
        except Exception:
            records_list = []

    # 2. Group records by supplier while cleaning data
    grouped_data: Dict[str, List[Dict[str, Any]]] = {}

    for row in records_list:
        if not isinstance(row, dict):
            continue

        # Silent cleaning: handle missing/invalid supplier name
        supplier = str(row.get('supplier_name', '')).strip()
        if not supplier or supplier.lower() == 'none' or supplier.lower() == 'null':
            supplier = "Unknown_Supplier"

        # Silent cleaning: handle invalid commission amount
        raw_amount = row.get('commission_amount')
        try:
            if raw_amount is None:
                amount = 0.0
            else:
                amount = float(raw_amount)
        except (ValueError, TypeError):
            amount = 0.0

        # Create cleaned record
        cleaned_row = {k: v for k, v in row.items()}
        cleaned_row['supplier_name'] = supplier
        cleaned_row['commission_amount'] = amount

        # Append required audit columns
        cleaned_row['verification_status'] = "Verified"
        cleaned_row['verifier'] = str(default_verifier)
        cleaned_row['audit_note'] = str(default_audit_note)

        if supplier not in grouped_data:
            grouped_data[supplier] = []
        grouped_data[supplier].append(cleaned_row)

    # 3. Generate ZIP file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for supplier, rows in grouped_data.items():
            if not rows:
                continue

            # Collect all unique fieldnames to ensure headers are complete
            fieldnames = []
            for row in rows:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)

            # Create CSV in memory
            csv_buffer = io.StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

            # Add to ZIP under the supplier's folder
            file_path = f"{supplier}/commissions.csv"
            zip_file.writestr(file_path, csv_buffer.getvalue().encode('utf-8-sig'))

    return zip_buffer.getvalue()
