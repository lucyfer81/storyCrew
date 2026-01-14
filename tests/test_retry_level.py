"""Tests for RetryLevel enum and determine_retry_level function."""
import pytest
from storycrew.models.retry_level import RetryLevel, determine_retry_level
from storycrew.models import JudgeReport, Issue

def test_retry_level_edit_only_preserved_outputs():
    """EDIT_ONLY should preserve scene_list, draft_text, revision_text"""
    result = RetryLevel.EDIT_ONLY.preserved_outputs
    assert result == {"scene_list", "draft_text", "revision_text"}

def test_retry_level_write_only_preserved_outputs():
    """WRITE_ONLY should preserve only scene_list"""
    result = RetryLevel.WRITE_ONLY.preserved_outputs
    assert result == {"scene_list"}

def test_retry_level_full_retry_preserved_outputs():
    """FULL_RETRY should preserve nothing"""
    result = RetryLevel.FULL_RETRY.preserved_outputs
    assert result == set()

def test_retry_level_edit_only_required_tasks():
    """EDIT_ONLY requires edit_chapter and judge_chapter"""
    result = RetryLevel.EDIT_ONLY.required_tasks
    assert result == ["edit_chapter", "judge_chapter"]

def test_retry_level_write_only_required_tasks():
    """WRITE_ONLY requires write, edit, judge"""
    result = RetryLevel.WRITE_ONLY.required_tasks
    assert result == ["write_chapter", "edit_chapter", "judge_chapter"]

def test_retry_level_full_retry_required_tasks():
    """FULL_RETRY requires all tasks"""
    result = RetryLevel.FULL_RETRY.required_tasks
    assert result == ["plan_chapter", "write_chapter", "edit_chapter", "judge_chapter"]

def test_determine_retry_level_prose_issue():
    """prose issue should map to EDIT_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="prose", severity="medium", note="文笔平淡")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.EDIT_ONLY

def test_determine_retry_level_pacing_issue():
    """pacing issue should map to EDIT_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="pacing", severity="medium", note="节奏拖沓")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.EDIT_ONLY

def test_determine_retry_level_word_count_issue():
    """word_count issue should map to EDIT_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="word_count", severity="high", note="字数不足")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.EDIT_ONLY

def test_determine_retry_level_motivation_issue():
    """motivation issue should map to WRITE_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="motivation", severity="high", note="人物动机不合理")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.WRITE_ONLY

def test_determine_retry_level_hook_issue():
    """hook issue should map to WRITE_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="hook", severity="medium", note="章末钩子不够强")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.WRITE_ONLY

def test_determine_retry_level_clue_fairness_issue():
    """clue_fairness issue should map to WRITE_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="clue_fairness", severity="high", note="线索不够公平")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.WRITE_ONLY

def test_determine_retry_level_continuity_issue():
    """continuity issue should map to WRITE_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="continuity", severity="high", note="前后矛盾")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.WRITE_ONLY

def test_determine_retry_level_structure_issue():
    """structure issue should map to FULL_RETRY"""
    judge = JudgeReport(
        issues=[Issue(type="structure", severity="high", note="场景顺序不合理")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.FULL_RETRY

def test_determine_retry_level_safety_critical_issue():
    """critical safety issue should map to FULL_RETRY"""
    judge = JudgeReport(
        issues=[Issue(type="safety", severity="critical", note="严重违规内容")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.FULL_RETRY

def test_determine_retry_level_safety_low_issue():
    """low severity safety issue should map to EDIT_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="safety", severity="low", note="轻微不当表述")]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.EDIT_ONLY

def test_determine_retry_level_last_attempt():
    """Last attempt (attempt >= 2) should always be FULL_RETRY"""
    judge = JudgeReport(
        issues=[Issue(type="prose", severity="low", note="文笔问题")]
    )
    level = determine_retry_level(judge, attempt=2)
    assert level == RetryLevel.FULL_RETRY

def test_determine_retry_level_multiple_issues():
    """Multiple issues should prioritize highest severity level"""
    # structure (FULL_RETRY) takes precedence
    judge = JudgeReport(
        issues=[
            Issue(type="prose", severity="low", note="文笔问题"),
            Issue(type="structure", severity="medium", note="结构问题")
        ]
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.FULL_RETRY

def test_determine_retry_level_unknown_issue():
    """Unknown issue types should default to WRITE_ONLY"""
    judge = JudgeReport(
        issues=[Issue(type="prose", severity="low", note="已知问题")]
    )
    level = determine_retry_level(judge, attempt=0)
    # prose is known, so EDIT_ONLY
    assert level == RetryLevel.EDIT_ONLY
