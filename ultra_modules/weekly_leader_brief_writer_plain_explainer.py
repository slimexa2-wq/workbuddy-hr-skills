import json

def _clean_count(val) -> int:
    """Helper to convert and clean count values."""
    try:
        if val is None:
            return 0
        v = int(val)
        return v if v >= 0 else 0
    except (ValueError, TypeError):
        return 0

def generate_brief(data: dict = None) -> dict:
    """
    Generates a weekly leader brief summary in multiple formats.
    Transforms complex backend calculations into plain language conclusion cards.
    """
    if data is None:
        data = {}

    # Extract and clean data with zero configuration fault tolerance
    onboarding_count = _clean_count(data.get('onboarding_count'))
    offboarding_count = _clean_count(data.get('offboarding_count'))
    total_headcount = _clean_count(data.get('total_headcount'))

    # Simple semantic data block
    cleaned_data = {
        "onboarding_count": onboarding_count,
        "offboarding_count": offboarding_count,
        "total_headcount": total_headcount
    }

    # HTML generation (simple page/div)
    html_str = (
        "<div>"
        "<h1>每周人员流动摘要</h1>"
        "<ul>"
        f"<li><strong>本周入职人数:</strong> {onboarding_count}人</li>"
        f"<li><strong>本周离职人数:</strong> {offboarding_count}人</li>"
        f"<li><strong>当前总人数:</strong> {total_headcount}人</li>"
        "</ul>"
        "</div>"
    )

    # Markdown generation
    markdown_str = (
        "# 每周人员流动摘要\n"
        f"- **本周入职人数:** {onboarding_count}人\n"
        f"- **本周离职人数:** {offboarding_count}人\n"
        f"- **当前总人数:** {total_headcount}人\n"
    )

    # JSON generation
    json_str = json.dumps(cleaned_data, ensure_ascii=False)

    return {
        "html": html_str,
        "markdown": markdown_str,
        "json": json_str
    }
