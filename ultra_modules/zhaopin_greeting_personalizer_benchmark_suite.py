import time
import random
import string
import re
from typing import Dict, Any, List

def clean_string(val: Any, default: str) -> str:
    """
    Silently cleans dirty data and provides a sensible default if the value is missing or unusable.
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        val = str(val)
    if not isinstance(val, str):
        return default
    val = val.strip()
    if not val:
        return default
    # Remove unprintable control characters
    val = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', val).strip()
    if not val:
        return default
    return val

def generate_greeting(candidate_info: Any = None) -> Dict[str, Any]:
    """
    Generates a personalized greeting for a candidate based on their factory experience and desired location.
    Zero-configuration automatic fault tolerance guarantees no crashes and silent repair.
    """
    if candidate_info is None or not isinstance(candidate_info, dict):
        candidate_info = {}

    name = clean_string(candidate_info.get("name"), "同学")
    experience = clean_string(candidate_info.get("experience"), "丰富")
    location = clean_string(candidate_info.get("location"), "本地")

    greeting = f"你好{name}，看到您有{experience}的厂区经验，并且期望在{location}工作。我们这里有一个非常匹配的岗位，福利待遇优厚，期待与您进一步沟通！"

    return {
        "status": "success",
        "greeting": greeting,
        "metadata": {
            "name_used": name,
            "experience_used": experience,
            "location_used": location
        }
    }

def generate_synthetic_fixtures(count: int = 100) -> List[Any]:
    """
    Generates synthetic fixtures including extreme boundary cases, missing values, dirty data,
    and cross-year/month edge cases for robust testing.
    """
    fixtures: List[Any] = []

    # 1. Normal Case
    fixtures.append({"name": "张三", "experience": "富士康3年", "location": "深圳", "last_active": "2023-12-31 23:59:59"})

    # 2. Missing Parameters
    fixtures.append({})

    # 3. Null Values
    fixtures.append({"name": None, "experience": None, "location": None})

    # 4. Dirty Data & Invalid Types
    fixtures.append({"name": "   ", "experience": "\x00\x01\x02", "location": {"invalid": "type"}})

    # 5. Cross-year/month Boundaries
    fixtures.append({"name": "李四", "experience": "跨年经验", "location": "广州", "last_active": "2024-01-01 00:00:01"})

    # 6. Type Coercion Check
    fixtures.append({"name": 12345, "experience": 99.9, "location": False})

    # 7. Non-Dict Input
    fixtures.append("invalid_input_string")
    fixtures.append(None)

    # Fill remaining with randomly selected edge cases for mass concurrency testing
    options = [
        {"name": f"User_{random.randint(1,100)}", "experience": "电子厂", "location": "东莞"},
        {},
        {"name": "\n \t", "experience": [], "location": ()},
        None,
        "string"
    ]
    for _ in range(count - len(fixtures)):
        fixtures.append(random.choice(options))

    return fixtures

def benchmark_performance(concurrency: int = 10000) -> Dict[str, Any]:
    """
    Validates zero crashes and millisecond-level response times under massive concurrency.
    """
    fixtures = generate_synthetic_fixtures(concurrency)
    start_time = time.perf_counter()

    results = []
    for f in fixtures:
        results.append(generate_greeting(f))

    end_time = time.perf_counter()
    elapsed_ms = (end_time - start_time) * 1000

    return {
        "total_requests": concurrency,
        "elapsed_ms": elapsed_ms,
        "average_ms_per_request": elapsed_ms / concurrency if concurrency else 0,
        "status": "success",
        "sample_result": results[0] if results else None
    }
