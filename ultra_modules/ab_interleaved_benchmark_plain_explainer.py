import math
import statistics
import json

class ABInterleavedBenchmarkPlainExplainer:
    """
    A plain explainer for AB/BA interleaved benchmarking using non-parametric statistics (Median/IQR).
    Prioritizes zero configuration, automatic fault tolerance, and sensible default values.
    """

    def __init__(self):
        pass

    def _clean_data(self, data):
        """Silently cleans dirty data (strings, nulls, NaNs, missing values)."""
        if not isinstance(data, (list, tuple)):
            return []

        cleaned = []
        for item in data:
            if isinstance(item, (int, float)):
                if not math.isnan(item) and not math.isinf(item):
                    cleaned.append(float(item))
            elif isinstance(item, str):
                try:
                    val = float(item)
                    if not math.isnan(val) and not math.isinf(val):
                        cleaned.append(val)
                except (ValueError, TypeError):
                    pass
        return cleaned

    def _calc_stats(self, data):
        """Calculates median and Interquartile Range (IQR)."""
        if not data:
            return {"median": 0.0, "iqr": 0.0, "q1": 0.0, "q3": 0.0, "count": 0}

        n = len(data)
        sorted_data = sorted(data)
        median = statistics.median(sorted_data)

        if n == 1:
            return {"median": median, "iqr": 0.0, "q1": median, "q3": median, "count": n}

        mid = n // 2
        if n % 2 == 0:
            q1 = statistics.median(sorted_data[:mid])
            q3 = statistics.median(sorted_data[mid:])
        else:
            q1 = statistics.median(sorted_data[:mid])
            q3 = statistics.median(sorted_data[mid+1:])

        iqr = q3 - q1
        return {"median": median, "iqr": iqr, "q1": q1, "q3": q3, "count": n}

    def analyze_and_explain(self, data_a=None, data_b=None, name_a="方案A", name_b="方案B", format_type="markdown", higher_is_better=True):
        """
        Analyzes two groups of benchmark data and returns a highly intuitive, plain-text conclusion card.
        format_type: 'markdown', 'html', or 'json'.
        higher_is_better: True if larger numbers mean better performance (e.g. throughput), False if smaller is better (e.g. latency).
        """
        # Sensible defaults for missing parameters
        if data_a is None:
            data_a = []
        if data_b is None:
            data_b = []

        clean_a = self._clean_data(data_a)
        clean_b = self._clean_data(data_b)

        stats_a = self._calc_stats(clean_a)
        stats_b = self._calc_stats(clean_b)

        # Determine statistical significance via median and IQR overlap
        diff = stats_b['median'] - stats_a['median']
        avg_iqr = (stats_a['iqr'] + stats_b['iqr']) / 2.0

        if avg_iqr > 0:
            effect_size = abs(diff) / avg_iqr
        else:
            effect_size = float('inf') if diff != 0 else 0

        is_b_better = (diff > 0) if higher_is_better else (diff < 0)
        better_name = name_b if is_b_better else name_a
        worse_name = name_a if is_b_better else name_b
        better_median = stats_b['median'] if is_b_better else stats_a['median']
        worse_median = stats_a['median'] if is_b_better else stats_b['median']

        if effect_size > 1.0:
            significance = "显著"
            explanation = f"结论：【{better_name}】表现明显更好！它的中位数（{better_median:.2f}）优于【{worse_name}】（{worse_median:.2f}），且差异远超正常的波动范围。"
            winner = better_name
        elif effect_size > 0.5:
            significance = "微弱"
            explanation = f"结论：【{better_name}】略微占优，但优势不够明显（中位数 {better_median:.2f} vs {worse_median:.2f}），两者差距与日常波动范围相当。"
            winner = better_name
        else:
            significance = "不显著"
            explanation = f"结论：两者性能表现几乎没有实质区别（中位数 {stats_a['median']:.2f} vs {stats_b['median']:.2f}）。建议直接根据成本或实现难度等非性能因素进行选择。"
            winner = "平局"

        warning = ""
        if stats_a['count'] < 3 or stats_b['count'] < 3:
            warning = "⚠️ 警告：有效数据样本太少（少于3个），评测结论可能存在误差，建议收集更多数据后再看。"

        result_dict = {
            "name_a": name_a,
            "name_b": name_b,
            "stats_a": stats_a,
            "stats_b": stats_b,
            "winner": winner,
            "significance": significance,
            "explanation": explanation,
            "warning": warning,
            "higher_is_better": higher_is_better
        }

        fmt = str(format_type).lower()
        if fmt == 'json':
            return json.dumps(result_dict, ensure_ascii=False, indent=2)
        elif fmt == 'html':
            warning_html = f'<p style="color:#d9534f; font-size:0.9em; font-weight:bold;">{warning}</p>' if warning else ''
            html = f'''<div class="benchmark-card" style="border:1px solid #e0e0e0; padding:20px; border-radius:12px; font-family:sans-serif; max-width: 600px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); background-color: #fff;">
    <h3 style="margin-top:0; color:#333; border-bottom:2px solid #007bff; padding-bottom:10px;">📊 A/B 对比评测一页纸结论卡</h3>
    <p style="font-size:1.1em; color:#1a1a1a; line-height:1.5;"><strong>{explanation}</strong></p>
    {warning_html}
    <div style="display:flex; justify-content:space-between; margin-top: 20px; padding: 10px; background-color: #f8f9fa; border-radius: 8px;">
        <div style="flex:1; text-align:center; border-right:1px solid #ddd;">
            <h4 style="margin:0 0 10px 0; color:#555;">{name_a}</h4>
            <p style="margin:5px 0;">样本数: <strong>{stats_a['count']}</strong></p>
            <p style="margin:5px 0; font-size:1.2em; color:#007bff;">中位数: <strong>{stats_a['median']:.2f}</strong></p>
            <p style="margin:5px 0; color:#777; font-size:0.9em;">波动区间(IQR): {stats_a['iqr']:.2f}</p>
        </div>
        <div style="flex:1; text-align:center;">
            <h4 style="margin:0 0 10px 0; color:#555;">{name_b}</h4>
            <p style="margin:5px 0;">样本数: <strong>{stats_b['count']}</strong></p>
            <p style="margin:5px 0; font-size:1.2em; color:#28a745;">中位数: <strong>{stats_b['median']:.2f}</strong></p>
            <p style="margin:5px 0; color:#777; font-size:0.9em;">波动区间(IQR): {stats_b['iqr']:.2f}</p>
        </div>
    </div>
</div>'''
            return html
        else:
            # Markdown fallback
            warning_md = f"\n> {warning}\n" if warning else ""
            md = f"""### 📊 A/B 对比评测一页纸结论卡

**{explanation}**{warning_md}

---
| 方案 | 样本数 | 中位数 | 波动区间 (IQR) |
| --- | --- | --- | --- |
| **{name_a}** | {stats_a['count']} | **{stats_a['median']:.2f}** | {stats_a['iqr']:.2f} |
| **{name_b}** | {stats_b['count']} | **{stats_b['median']:.2f}** | {stats_b['iqr']:.2f} |
"""
            return md.strip()
