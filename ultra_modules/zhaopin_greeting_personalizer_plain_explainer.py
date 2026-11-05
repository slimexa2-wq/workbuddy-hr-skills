import json

class ZhaopinGreetingPersonalizer:
    def __init__(self):
        self.default_location = "我们公司"
        self.default_company_type = "优质企业"

    def _sanitize_data(self, data):
        """Sanitizes input data, handling missing or dirty inputs."""
        if not isinstance(data, dict):
            return {}

        sanitized = {}

        # Name
        name = data.get('name')
        sanitized['name'] = str(name).strip() if name and isinstance(name, (str, int)) else "同学"

        # Expected locations
        locations = data.get('expected_locations')
        if isinstance(locations, list):
            sanitized['expected_locations'] = [str(l).strip() for l in locations if isinstance(l, (str, int)) and str(l).strip()]
        elif isinstance(locations, (str, int)):
            sanitized['expected_locations'] = [str(locations).strip()] if str(locations).strip() else []
        else:
            sanitized['expected_locations'] = []

        # Past companies
        companies = data.get('past_companies')
        if isinstance(companies, list):
            sanitized['past_companies'] = [str(c).strip() for c in companies if isinstance(c, (str, int)) and str(c).strip()]
        elif isinstance(companies, (str, int)):
            sanitized['past_companies'] = [str(companies).strip()] if str(companies).strip() else []
        else:
            sanitized['past_companies'] = []

        return sanitized

    def generate_greeting(self, candidate_data):
        """Generates a plain, conversational greeting based on candidate data."""
        data = self._sanitize_data(candidate_data)

        name = data.get('name', '同学')
        companies = data.get('past_companies', [])
        locations = data.get('expected_locations', [])

        greeting = f"你好，{name}！"

        if companies:
            past_exp = "、".join(companies[:2])
            if len(companies) > 2:
                past_exp += "等"
            greeting += f"我看你在{past_exp}做过，经验挺丰富的。"
        else:
            greeting += "我看你的简历挺不错的。"

        if locations:
            loc = locations[0]
            greeting += f"刚好我们在{loc}这边有合适的岗位，待遇不错，"
        else:
            greeting += "刚好我们这边有几个合适的岗位，"

        greeting += "你要不要了解一下？期待你的回复！"

        return greeting

    def generate_explainer_card(self, candidate_data, output_format="json"):
        """
        Generates a plain explainer card for HRs.
        output_format can be 'json', 'html', or 'markdown'.
        Defaults to 'json' if an unknown format is provided.
        """
        data = self._sanitize_data(candidate_data)
        greeting = self.generate_greeting(candidate_data)

        # Fallback for unknown formats
        if output_format not in ["json", "html", "markdown"]:
            output_format = "json"

        card_data = {
            "title": "候选人打招呼策略卡",
            "candidate_name": data.get("name", "未知候选人"),
            "key_highlights": [],
            "generated_greeting": greeting
        }

        companies = data.get("past_companies", [])
        locations = data.get("expected_locations", [])

        if companies:
            card_data["key_highlights"].append(f"有【{', '.join(companies)}】等厂区经验，可重点强调我们岗位的稳定性和晋升机会。")
        else:
            card_data["key_highlights"].append("暂无具体厂区经验记录，可主打新人培训和福利。")

        if locations:
            card_data["key_highlights"].append(f"候选人期望地包含【{', '.join(locations)}】，我们优先推相关地域的岗位。")
        else:
            card_data["key_highlights"].append("候选人未明确期望地，可先推重点缺人且福利好的基地。")

        if output_format == "json":
            return json.dumps(card_data, ensure_ascii=False, indent=2)

        elif output_format == "html":
            highlights_html = "".join([f"<li>{h}</li>" for h in card_data["key_highlights"]])
            html = f"""
            <div class="explainer-card" style="border: 1px solid #ddd; padding: 16px; border-radius: 8px; font-family: sans-serif;">
                <h2 style="color: #333; margin-top: 0;">{card_data['title']}</h2>
                <p><strong>候选人：</strong>{card_data['candidate_name']}</p>
                <div style="background: #f9f9f9; padding: 12px; border-radius: 4px; margin: 12px 0;">
                    <p style="margin: 0 0 8px 0;"><strong>💡 策略分析：</strong></p>
                    <ul style="margin: 0; padding-left: 20px;">
                        {highlights_html}
                    </ul>
                </div>
                <div>
                    <p style="margin: 0 0 8px 0;"><strong>💬 一键打招呼话术：</strong></p>
                    <blockquote style="margin: 0; padding: 10px; border-left: 4px solid #007bff; background: #f0f7ff;">
                        {card_data['generated_greeting']}
                    </blockquote>
                </div>
            </div>
            """
            return html.strip()

        elif output_format == "markdown":
            highlights_md = "\n".join([f"- {h}" for h in card_data["key_highlights"]])
            md = f"""
## {card_data['title']}

**候选人：** {card_data['candidate_name']}

### 💡 策略分析
{highlights_md}

### 💬 一键打招呼话术
> {card_data['generated_greeting']}
            """
            return md.strip()
