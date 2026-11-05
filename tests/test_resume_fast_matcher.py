import pytest
from scripts.resume_fast_matcher import ResumeFastMatcher

@pytest.fixture
def matcher():
    return ResumeFastMatcher()

def test_extract_elements_noisy_text(matcher):
    text = "联系电话 13812345678  电子邮箱 test.user@example.com，姓名：张三，28岁。高中毕业，后来又读了大专。有5年经验"
    result = matcher.extract_elements(text)

    assert result["phone"] == "13812345678"
    assert result["email"] == "test.user@example.com"
    assert result["name"] == "张三"
    assert result["age"] == 28
    assert result["education"] == "大专"
    assert result["experience_years"] == 5

def test_match_roles_blue_collar(matcher):
    text = "我想找一份工作，以前在车间做过流水线普工，也会装配和包装。"
    profile = matcher.extract_elements(text)
    result = matcher.match_roles(text, profile)

    assert result["recommended_role"] == "蓝领岗位"
    assert result["scores"]["蓝领岗位"] == 5
    assert "5 个蓝领相关关键词" in result["recommendation_reason"]

def test_match_roles_manufacturing(matcher):
    text = "我是一名焊工，有5年工作经验，精通数控机床，也懂模具维修和CNC操作。"
    profile = matcher.extract_elements(text)
    result = matcher.match_roles(text, profile)

    assert result["recommended_role"] == "制造岗位"
    assert result["scores"]["制造岗位"] == 6
    assert "丰富的经验，可考虑作为资深员工或组长" in result["recommendation_reason"]

def test_match_roles_hr(matcher):
    text = "姓名：李四 硕士 负责公司招聘、培训以及绩效管理，有HR工作经验。"
    profile = matcher.extract_elements(text)
    result = matcher.match_roles(text, profile)

    assert result["recommended_role"] == "人事岗位"
    assert result["scores"]["人事岗位"] == 4
    assert "学历较高，符合该岗位的进阶要求" in result["recommendation_reason"]

def test_process_resume_end_to_end(matcher):
    text = "简历 姓名：王五 电话 13987654321，想做保安或保洁。"
    result = matcher.process_resume(text)

    assert result["profile"]["name"] == "王五"
    assert result["profile"]["phone"] == "13987654321"
    assert result["recommended_role"] == "蓝领岗位"
    assert result["scores"]["蓝领岗位"] == 2

def test_general_role_no_match(matcher):
    text = "我刚毕业，什么都不懂，希望能找到一份能学习的工作。"
    result = matcher.process_resume(text)

    assert result["recommended_role"] == "通用岗位"
    assert "未提取到明显的专业技能关键词" in result["recommendation_reason"]
