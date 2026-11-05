import time
import socket
import json
import argparse
import os

try:
    import openpyxl
except ImportError:
    openpyxl = None

DEFAULT_TARGETS = [
    ("Proxy-7890", "127.0.0.1", 7890),
    ("Proxy-26801", "127.0.0.1", 26801),
    ("Direct-Google-DNS", "8.8.8.8", 53)
]

def probe_endpoint(host, port, timeout=1.0):
    """
    Probes a TCP endpoint and returns latency in ms. Returns -1.0 if failed.
    Handles missing parameters with defaults.
    """
    try:
        # Default fallbacks
        host = host or "127.0.0.1"
        port = int(port) if port is not None else 7890
        timeout = float(timeout) if timeout is not None else 1.0

        start = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        end = time.time()
        return round((end - start) * 1000, 2)
    except Exception:
        return -1.0

def probe_all(targets=None):
    if not targets:
        targets = DEFAULT_TARGETS

    results = []
    for target in targets:
        # Dirty data self-healing
        if not isinstance(target, (list, tuple)) or len(target) < 3:
            continue

        name, host, port = target[:3]
        if not name:
            name = f"{host}:{port}"

        latency = probe_endpoint(host, port)
        results.append({
            "name": name,
            "host": host,
            "port": port,
            "latency_ms": latency,
            "status": "Healthy" if latency >= 0 else "Unhealthy",
            "timestamp": time.time()
        })
    return results

def export_json(results, filepath=None):
    if not filepath:
        filepath = "probe_results.json"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        return filepath
    except Exception as e:
        print(f"Error exporting JSON: {e}")
        return None

def export_excel(results, filepath=None):
    if not openpyxl:
        print("openpyxl not installed, skipping Excel export.")
        return None

    if not filepath:
        filepath = "probe_results.xlsx"

    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Proxy Health Probe"

        headers = ["Name", "Host", "Port", "Latency (ms)", "Status", "Timestamp"]
        ws.append(headers)

        for r in results:
            # Dirty data scrubbing - avoid control characters in openpyxl
            name = str(r.get("name", "")).replace('\x00', '')
            host = str(r.get("host", "")).replace('\x00', '')
            port = r.get("port", 0)
            latency = r.get("latency_ms", -1.0)
            status = str(r.get("status", "")).replace('\x00', '')
            timestamp = r.get("timestamp", 0.0)

            ws.append([name, host, port, latency, status, timestamp])

        wb.save(filepath)
        return filepath
    except Exception as e:
        print(f"Error exporting Excel: {e}")
        return None

def run_cli():
    parser = argparse.ArgumentParser(description="One-click Mihomo Proxy Health Prober")
    parser.add_argument("--json", type=str, default="probe_results.json", help="JSON output file")
    parser.add_argument("--excel", type=str, default="probe_results.xlsx", help="Excel output file")

    # Tolerant parsing to allow zero-config run
    args, _ = parser.parse_known_args()

    print("Starting proxy health probe...")
    results = probe_all()

    print("\nResults:")
    for r in results:
        print(f"[{r['status']}] {r['name']} ({r['host']}:{r['port']}) - {r['latency_ms']} ms")

    json_path = export_json(results, args.json)
    if json_path:
        print(f"JSON exported to {json_path}")

    excel_path = export_excel(results, args.excel)
    if excel_path:
        print(f"Excel exported to {excel_path}")

    return results

if __name__ == "__main__":
    run_cli()
