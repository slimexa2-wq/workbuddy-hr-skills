import csv
import io
import zipfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

def sanitize_data(record: Dict[str, Any]) -> Dict[str, Any]:
    """Silently cleans dirty data for a commission record."""
    clean_record = {}

    # 供应商 (Vendor)
    vendor = record.get("vendor")
    if not isinstance(vendor, str) or not vendor.strip():
        clean_record["vendor"] = "UNKNOWN_VENDOR"
    else:
        clean_record["vendor"] = vendor.strip()

    # 项目 (Project)
    project = record.get("project")
    if not isinstance(project, str) or not project.strip():
        clean_record["project"] = "UNKNOWN_PROJECT"
    else:
        clean_record["project"] = project.strip()

    # 提成金额 (Commission Amount)
    amount = record.get("amount")
    try:
        clean_record["amount"] = float(amount)
    except (ValueError, TypeError):
        clean_record["amount"] = 0.0

    # 附加一些默认列 (例如 核对列)
    clean_record["audit_status"] = "PENDING"

    return clean_record

def process_batch_worker(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Worker function to process a batch of records and group them by vendor."""
    grouped_data = {}
    for raw_record in records:
        if not isinstance(raw_record, dict):
            continue
        clean_record = sanitize_data(raw_record)
        vendor = clean_record["vendor"]
        if vendor not in grouped_data:
            grouped_data[vendor] = []
        grouped_data[vendor].append(clean_record)
    return grouped_data

def run_pipeline(
    records: Optional[List[Dict[str, Any]]] = None,
    concurrency: int = 4
) -> bytes:
    """
    Main pipeline:
    1. Zero-configuration missing params fallback.
    2. Batch processing via ThreadPoolExecutor.
    3. Memory ZIP generation.
    Returns: Bytes of the ZIP file.
    """
    if records is None:
        records = []

    if not isinstance(records, list):
        records = []

    if not records:
        # Create an empty ZIP if no data
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("empty.txt", b"No records provided.")
        return mem_zip.getvalue()

    # Split records into batches for workers
    batch_size = max(1, len(records) // concurrency)
    batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]

    # Thread-safe dictionary for aggregating results
    vendor_groups: Dict[str, List[Dict[str, Any]]] = {}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_batch_worker, batch): batch for batch in batches}
        for future in as_completed(futures):
            try:
                result_group = future.result()
                with lock:
                    for vendor, items in result_group.items():
                        if vendor not in vendor_groups:
                            vendor_groups[vendor] = []
                        vendor_groups[vendor].extend(items)
            except Exception:
                # Silently ignore worker failures in favor of fault tolerance
                pass

    # Create ZIP file in memory
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        if not vendor_groups:
            zf.writestr("empty.txt", b"No valid records processed.")
        else:
            for vendor, items in vendor_groups.items():
                csv_buffer = io.StringIO()
                if items:
                    fieldnames = list(items[0].keys())
                    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(items)

                # Append 《（审核版）》 to the filename
                filename = f"{vendor}_《（审核版）》.csv"
                zf.writestr(filename, csv_buffer.getvalue().encode('utf-8-sig'))

    return mem_zip.getvalue()
