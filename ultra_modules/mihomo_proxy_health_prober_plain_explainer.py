import time
import urllib.request
import urllib.error
import json
from typing import List, Dict, Any

class MihomoProxyHealthProberPlainExplainer:
    """
    Mihomo Proxy Health Prober Plain Explainer
    A highly robust, zero-configuration prober that measures the latency of direct
    connections vs proxy connections (e.g., Mihomo local proxy on ports 7890, 26801),
    and outputs a plain-language summary for business users.

    Supreme Design Principles:
    - Zero configuration: Missing params automatically default to sensible values.
    - Dirty data healing: Invalid types or values are silently healed.
    - One-click explanation: Generates simple, human-readable conclusions in HTML, Markdown, and JSON.
    """

    def __init__(self, target_url: Any = None, proxy_ports: Any = None, timeout: Any = None):
        # 脏数据自愈与缺参兜底 (Dirty data healing and fallback)
        self.target_url = self._heal_url(target_url)
        self.proxy_ports = self._heal_ports(proxy_ports)
        self.timeout = self._heal_timeout(timeout)

    def _heal_url(self, url: Any) -> str:
        """Heals the target URL. If missing or invalid, defaults to a reliable endpoint."""
        if not url or not isinstance(url, str) or not url.startswith('http'):
            return "http://www.gstatic.com/generate_204"
        return url

    def _heal_ports(self, ports: Any) -> List[int]:
        """Heals proxy ports. Accepts int, string of comma-separated ints, or lists."""
        default_ports = [7890, 26801]
        if ports is None:
            return default_ports

        if isinstance(ports, int):
            return [ports] if 0 < ports <= 65535 else default_ports

        if isinstance(ports, str):
            try:
                parsed_ports = [int(p.strip()) for p in ports.split(',') if p.strip().isdigit()]
                valid_ports = [p for p in parsed_ports if 0 < p <= 65535]
                return valid_ports if valid_ports else default_ports
            except Exception:
                return default_ports

        if isinstance(ports, list):
            valid_ports = []
            for p in ports:
                try:
                    val = int(p)
                    if 0 < val <= 65535:
                        valid_ports.append(val)
                except Exception:
                    continue
            return valid_ports if valid_ports else default_ports

        return default_ports

    def _heal_timeout(self, timeout: Any) -> float:
        """Heals timeout. Ensures it is a positive float, defaulting to 3.0s."""
        if timeout is None:
            return 3.0
        try:
            val = float(timeout)
            if val <= 0:
                return 3.0
            return val
        except Exception:
            return 3.0

    def _measure_latency(self, proxy_port: int = None) -> float:
        """
        Measures latency to the target_url.
        If proxy_port is provided, uses HTTP proxy.
        Returns latency in milliseconds, or -1.0 if failed/timeout.
        """
        handlers = []
        if proxy_port:
            proxy_url = f"http://127.0.0.1:{proxy_port}"
            handlers.append(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))
        else:
            handlers.append(urllib.request.ProxyHandler({})) # Force direct connection

        opener = urllib.request.build_opener(*handlers)

        start_time = time.time()
        try:
            req = urllib.request.Request(self.target_url, headers={'User-Agent': 'Mozilla/5.0 (MihomoHealthProber)'})
            with opener.open(req, timeout=self.timeout) as response:
                _ = response.read(1) # Try reading a single byte to ensure a complete roundtrip
            end_time = time.time()
            return (end_time - start_time) * 1000.0
        except Exception:
            return -1.0

    def probe(self) -> Dict[str, str]:
        """
        Executes the network probe across direct and all configured proxy ports.
        Returns a dictionary with plain-language reports in JSON, Markdown, and HTML formats.
        """
        results = {}

        # 1. Measure Direct Connection
        results['direct'] = self._measure_latency(None)

        # 2. Measure Proxies
        for port in self.proxy_ports:
            results[f'proxy_{port}'] = self._measure_latency(port)

        # 3. Generate Reports
        return self._generate_report(results)

    def _generate_report(self, results: Dict[str, float]) -> Dict[str, str]:
        valid_results = {k: v for k, v in results.items() if v >= 0}

        if not valid_results:
            conclusion = "⚠️ 哎呀，网络好像彻底断了！无论是直连还是代理都无法连接，请检查您的本地网络或 WiFi 状态。"
            best_mode = "none"
        else:
            best_mode = min(valid_results, key=valid_results.get)
            best_latency = valid_results[best_mode]

            if best_mode == 'direct':
                conclusion = f"✅ 当前网络状态绝佳！直连速度最快（{best_latency:.0f} 毫秒）。无需开启代理，直接冲浪即可！"
            else:
                port = best_mode.split('_')[1]
                conclusion = f"🚀 推荐使用代理！当前通过 {port} 端口代理的速度最快（{best_latency:.0f} 毫秒）。已为您自动推荐最佳连通路线。"

        json_data = {
            "conclusion": conclusion,
            "best_mode": best_mode,
            "details": results
        }

        md_lines = [
            "# 🌐 网络测速大白话报告",
            "",
            f"**一句话总结：** {conclusion}",
            "",
            "### 详细测速数据："
        ]

        direct_latency = results["direct"]
        md_lines.append(f"- **直连 (Direct):** {f'{direct_latency:.0f} 毫秒' if direct_latency >= 0 else '超时/失败 ❌'}")

        for port in self.proxy_ports:
            latency = results[f'proxy_{port}']
            md_lines.append(f"- **代理端口 {port}:** {f'{latency:.0f} 毫秒' if latency >= 0 else '超时/失败 ❌'}")

        html_lines = [
            '<div style="font-family: sans-serif; max-width: 600px; margin: 20px auto; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); background: #ffffff;">',
            '    <h2 style="color: #333; margin-top: 0;">🌐 网络测速状态</h2>',
            '    <div style="background: #f0f7ff; border-left: 4px solid #0066cc; padding: 15px; margin: 15px 0; border-radius: 4px;">',
            f'        <p style="margin: 0; font-size: 16px; color: #004499; font-weight: bold;">{conclusion}</p>',
            '    </div>',
            '    <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">',
            '        <tr style="background: #f8f9fa;">',
            '            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">连接方式</th>',
            '            <th style="padding: 12px; text-align: right; border-bottom: 2px solid #ddd;">延迟 (毫秒)</th>',
            '        </tr>',
            '        <tr>',
            '            <td style="padding: 12px; border-bottom: 1px solid #eee;">🔌 直连 (Direct)</td>',
            f'            <td style="padding: 12px; text-align: right; border-bottom: 1px solid #eee; color: {"#28a745" if direct_latency >= 0 else "#dc3545"};">',
            f'                {f"{direct_latency:.0f} ms" if direct_latency >= 0 else "超时/失败 ❌"}',
            '            </td>',
            '        </tr>'
        ]

        for port in self.proxy_ports:
            latency = results[f'proxy_{port}']
            color = "#28a745" if latency >= 0 else "#dc3545"
            html_lines.extend([
                '        <tr>',
                f'            <td style="padding: 12px; border-bottom: 1px solid #eee;">🛡️ 代理 (Port {port})</td>',
                f'            <td style="padding: 12px; text-align: right; border-bottom: 1px solid #eee; color: {color};">',
                f'                {f"{latency:.0f} ms" if latency >= 0 else "超时/失败 ❌"}',
                '            </td>',
                '        </tr>'
            ])

        html_lines.extend([
            '    </table>',
            '    <p style="font-size: 12px; color: #888; text-align: center; margin-top: 20px;">由 Mihomo Proxy Health Prober 自动生成</p>',
            '</div>'
        ])

        return {
            "json": json.dumps(json_data, ensure_ascii=False, indent=2),
            "markdown": "\n".join(md_lines),
            "html": "\n".join(html_lines)
        }
