def generate_greeting(candidate_name=None, expected_location=None, past_companies=None, role=None):
    """
    Generates a personalized greeting message for a candidate based on their background.

    Args:
        candidate_name (str): Name of the candidate. Defaults to "同学".
        expected_location (str): Expected working location. Defaults to "".
        past_companies (list, str): List of past companies or a string. Defaults to empty list.
        role (str): The role being hired for. Defaults to "核心岗位".

    Returns:
        str: A personalized greeting message.
    """
    # 1. Cleanse and default the simple string arguments
    name = candidate_name.strip() if isinstance(candidate_name, str) and candidate_name.strip() else "同学"
    location = expected_location.strip() if isinstance(expected_location, str) and expected_location.strip() else ""
    role_name = role.strip() if isinstance(role, str) and role.strip() else "核心岗位"

    # 2. Process past_companies
    companies = []
    if isinstance(past_companies, str):
        # Split by common delimiters like comma, semicolon, space
        import re
        parts = re.split(r'[,;，；\s]+', past_companies)
        companies = [p.strip() for p in parts if p.strip()]
    elif isinstance(past_companies, list):
        companies = [str(c).strip() for c in past_companies if c is not None and str(c).strip() and str(c).strip().lower() != 'none']

    # Remove duplicates while preserving order
    seen = set()
    unique_companies = []
    for c in companies:
        if c not in seen:
            seen.add(c)
            unique_companies.append(c)

    companies = unique_companies

    # 3. Truncate to top 2 companies
    if len(companies) > 2:
        companies_str = "、".join(companies[:2]) + "等厂区"
    elif len(companies) > 0:
        companies_str = "、".join(companies) + "厂区"
    else:
        companies_str = ""

    # 4. Construct the greeting
    # Format:
    # [name]你好！
    # 关注到你有[companies_str]的经验，[同时也期望在[location]发展，]
    # 我们目前正在热招[role_name]，觉得你的过往履历非常匹配。
    # 期待进一步交流！

    greeting = f"{name}你好！\n"

    context_parts = []
    if companies_str:
        context_parts.append(f"关注到你有{companies_str}的经验")

    if location:
        if companies_str:
            context_parts.append(f"同时也期望在{location}发展")
        else:
            context_parts.append(f"关注到你期望在{location}发展")

    if context_parts:
        greeting += "，".join(context_parts) + "，\n"

    greeting += f"我们目前正在热招{role_name}，觉得你的过往履历非常匹配。\n期待进一步交流！"

    return greeting
