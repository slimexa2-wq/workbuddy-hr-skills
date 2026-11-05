import json

def generate_plain_explainer_card(commissions=None, format_type='json'):
    """
    Generates a plain text summary card for multi-project supplier commissions.
    Auto-heals dirty data, aggregates amounts by supplier, and outputs in the requested format.
    """
    if commissions is None:
        commissions = []

    if not isinstance(commissions, list):
        commissions = []

    if format_type not in ('json', 'html', 'markdown'):
        format_type = 'json'

    # Auto-heal and Aggregate
    aggregated = {}

    for item in commissions:
        if not isinstance(item, dict):
            continue

        supplier_name = item.get('supplier_name')
        if not supplier_name or not isinstance(supplier_name, str):
            supplier_name = 'Unknown Supplier'

        amount = item.get('amount')
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0.0

        if supplier_name not in aggregated:
            aggregated[supplier_name] = 0.0

        aggregated[supplier_name] += amount

    # Formatting
    # Sort for deterministic output
    sorted_suppliers = sorted(aggregated.items(), key=lambda x: x[0])

    if format_type == 'json':
        summary = [{"supplier": name, "total_commission": round(total, 2)} for name, total in sorted_suppliers]
        return json.dumps(summary, ensure_ascii=False)

    elif format_type == 'html':
        html_lines = ["<div class='commission-card'>", "  <h2>Supplier Commission Summary</h2>", "  <ul>"]
        for name, total in sorted_suppliers:
            html_lines.append(f"    <li><strong>{name}</strong>: {round(total, 2)}</li>")
        html_lines.append("  </ul>")
        html_lines.append("</div>")
        return "\n".join(html_lines)

    elif format_type == 'markdown':
        md_lines = ["# Supplier Commission Summary", ""]
        if not sorted_suppliers:
            md_lines.append("No commissions to report.")
        else:
            for name, total in sorted_suppliers:
                md_lines.append(f"- **{name}**: {round(total, 2)}")
        return "\n".join(md_lines)
