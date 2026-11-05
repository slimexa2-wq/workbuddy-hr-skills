import math
import statistics
import time
import urllib.request
from typing import List, Dict, Any, Optional

def _measure_latency(url: str, proxy_url: Optional[str] = None, timeout: float = 2.0) -> Optional[float]:
    """Measure latency to a given URL, optionally via an HTTP proxy."""
    start_time = time.time()
    try:
        handlers = []
        if proxy_url:
            handlers.append(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))
        else:
            handlers.append(urllib.request.ProxyHandler({})) # explicit direct

        opener = urllib.request.build_opener(*handlers)
        req = urllib.request.Request(url, method='HEAD')
        # Add a dummy User-Agent
        req.add_header('User-Agent', 'Mozilla/5.0')
        with opener.open(req, timeout=timeout) as _:
            return (time.time() - start_time) * 1000
    except Exception:
        return None

def run_anomaly_radar(
    target_url: str = "http://www.google.com/generate_204",
    proxy_ports: Optional[List[int]] = None,
    timeout: float = 2.0
) -> Dict[str, Any]:
    """
    One-click prober. Scans proxy ports and direct connections by routing requests.
    Calculates anomalies using Z-Score/IQR and highlights Top 3% worst issues.
    Provides auto-switching recommendation.
    """
    # Dirty data repair
    if not isinstance(target_url, str) or not target_url.strip():
        target_url = "http://www.google.com/generate_204"
    else:
        target_url = target_url.strip()
        if not target_url.startswith('http'):
            target_url = 'http://' + target_url

    if proxy_ports is None:
        proxy_ports = [7890, 26801]

    cleaned_proxy_ports = []
    for p in proxy_ports:
        try:
            cleaned_proxy_ports.append(int(p))
        except (ValueError, TypeError):
            pass
    if not cleaned_proxy_ports:
        cleaned_proxy_ports = [7890, 26801]

    try:
        timeout = float(timeout) if timeout is not None else 2.0
        if math.isnan(timeout) or timeout <= 0:
            timeout = 2.0
    except (ValueError, TypeError):
        timeout = 2.0

    results = []

    # 1. Direct connection
    direct_latency = _measure_latency(target_url, None, timeout=timeout)
    results.append({
        "type": "direct",
        "port": None,
        "latency": direct_latency
    })

    # 2. Proxy ports
    for p in cleaned_proxy_ports:
        latency = _measure_latency(target_url, f"http://127.0.0.1:{p}", timeout=timeout)
        results.append({
            "type": "proxy",
            "port": p,
            "latency": latency
        })

    valid_latencies = [r["latency"] for r in results if r["latency"] is not None]

    anomalies = []
    normal = []

    if not valid_latencies:
        for r in results:
            r.update({
                "status": "Red",
                "is_anomaly": True,
                "reason": "节点完全无法连接，请检查网络或代理客户端是否运行"
            })
            anomalies.append(r)

        top_k = max(1, math.ceil(len(results) * 0.03))
        highlighted_anomalies = anomalies[:top_k]
        silenced = anomalies[top_k:]
        for r in silenced:
            r["status"] = "Red"
            r["is_anomaly"] = False
            r["reason"] = "静默放行 (全部离线，仅高亮Top 3%警报)"
            normal.append(r)

        return {
            "overall_status": "Red",
            "anomalies": highlighted_anomalies,
            "normal": normal,
            "best_connection": None,
            "switch_suggestion": "所有节点均离线，无法切换，请检查本地网络设置",
            "message": "所有连接均失败，请检查本机网络或代理状态。"
        }

    # Determine the best connection
    valid_results = [r for r in results if r["latency"] is not None]
    best_connection = min(valid_results, key=lambda x: x["latency"])

    # Anomaly detection (Z-score / IQR)
    anomaly_thresholds = set()
    n = len(valid_latencies)
    if n >= 4:
        q1 = statistics.quantiles(valid_latencies, n=4)[0]
        q3 = statistics.quantiles(valid_latencies, n=4)[2]
        iqr = q3 - q1
        if iqr > 0:
            anomaly_thresholds = {x for x in valid_latencies if x > q3 + 1.5 * iqr}
    elif n >= 2:
        mean = sum(valid_latencies) / n
        std = statistics.stdev(valid_latencies) if n > 1 else 0
        if std > 0:
            # For small samples, a lower Z-score threshold to catch outliers
            anomaly_thresholds = {x for x in valid_latencies if (x - mean) / std > 1.0}

    # Score and categorize
    for r in results:
        latency = r["latency"]
        if latency is None:
            r.update({
                "status": "Red",
                "is_anomaly": True,
                "reason": "连接超时或拒绝，代理节点宕机或被封锁"
            })
        else:
            is_anomaly = latency in anomaly_thresholds or latency > 2000
            if is_anomaly:
                r.update({
                    "status": "Yellow" if latency < 1000 else "Red",
                    "is_anomaly": True,
                    "reason": "延迟显著高于平均水平(存在拥堵)，建议避开此节点"
                })
            else:
                r.update({
                    "status": "Green",
                    "is_anomaly": False,
                    "reason": "连接顺畅，延迟极佳"
                })

    # Separate anomalies and normals
    all_anomalies = [r for r in results if r["is_anomaly"]]
    normal = [r for r in results if not r["is_anomaly"]]

    # "Top 3%" logic: highlighting only the worst few anomalies
    all_anomalies.sort(key=lambda x: x["latency"] if x["latency"] is not None else float('inf'), reverse=True)
    top_k = max(1, math.ceil(len(results) * 0.03))

    highlighted_anomalies = all_anomalies[:top_k]
    silenced = all_anomalies[top_k:]

    for r in silenced:
        r["status"] = "Green"
        r["is_anomaly"] = False
        r["reason"] = "静默放行 (非Top 3%严重异常)"
        normal.append(r)

    overall_status = "Green"
    if any(a["status"] == "Red" for a in highlighted_anomalies):
        overall_status = "Red"
    elif any(a["status"] == "Yellow" for a in highlighted_anomalies):
        overall_status = "Yellow"

    best_name = "直连" if best_connection["type"] == "direct" else f"代理端口 {best_connection['port']}"
    suggestion = f"建议自动切换至{best_name}，当前延迟最优 ({best_connection['latency']:.0f}ms)"

    return {
        "overall_status": overall_status,
        "anomalies": highlighted_anomalies,
        "normal": normal,
        "best_connection": best_connection,
        "switch_suggestion": suggestion,
        "message": "检测完成" if overall_status == "Green" else "发现部分网络节点异常，请关注"
    }

class MihomoProxyHealthProberAnomalyRadar:
    """
    Extremely simple object-oriented wrapper for the one-click anomaly radar.
    """
    def __init__(self, target_url: str = "http://www.google.com/generate_204"):
        self.target_url = target_url

    def check(self) -> Dict[str, Any]:
        return run_anomaly_radar(target_url=self.target_url)
