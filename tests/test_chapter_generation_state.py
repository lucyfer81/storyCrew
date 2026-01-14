"""Tests for ChapterGenerationState model."""
import pytest
from storycrew.models.chapter_generation_state import ChapterGenerationState
from storycrew.models.retry_level import RetryLevel

def test_state_initialization():
    """State should initialize with default None values"""
    state = ChapterGenerationState()
    assert state.scene_list is None
    assert state.draft_text is None
    assert state.revision_text is None
    assert state.current_attempt == 0
    assert state.last_retry_level is None
    assert state.edit_retry_count == 0

def test_state_with_values():
    """State should store provided values"""
    state = ChapterGenerationState(
        scene_list='{"scenes": []}',
        draft_text="草稿文本",
        revision_text="修订文本",
        current_attempt=1,
        last_retry_level="edit_only",
        edit_retry_count=2
    )
    assert state.scene_list == '{"scenes": []}'
    assert state.draft_text == "草稿文本"
    assert state.revision_text == "修订文本"
    assert state.current_attempt == 1
    assert state.last_retry_level == "edit_only"
    assert state.edit_retry_count == 2

def test_to_preserve_edit_only():
    """EDIT_ONLY should preserve scene_list and draft_text_for_edit"""
    state = ChapterGenerationState(
        scene_list='{"scenes": []}',
        draft_text="草稿文本",
        revision_text="修订文本"
    )
    preserved = state.to_preserve(RetryLevel.EDIT_ONLY)
    assert "scene_list" in preserved
    assert preserved["scene_list"] == '{"scenes": []}'
    assert "draft_text_for_edit" in preserved
    assert preserved["draft_text_for_edit"] == "草稿文本"

def test_to_preserve_edit_only_missing_draft():
    """EDIT_ONLY with missing draft_text should not include it"""
    state = ChapterGenerationState(
        scene_list='{"scenes": []}'
    )
    preserved = state.to_preserve(RetryLevel.EDIT_ONLY)
    assert "scene_list" in preserved
    assert "draft_text_for_edit" not in preserved

def test_to_preserve_write_only():
    """WRITE_ONLY should preserve only scene_list"""
    state = ChapterGenerationState(
        scene_list='{"scenes": []}',
        draft_text="草稿文本",
        revision_text="修订文本"
    )
    preserved = state.to_preserve(RetryLevel.WRITE_ONLY)
    assert "scene_list" in preserved
    assert "draft_text_for_edit" not in preserved

def test_to_preserve_full_retry():
    """FULL_RETRY should preserve nothing"""
    state = ChapterGenerationState(
        scene_list='{"scenes": []}',
        draft_text="草稿文本"
    )
    preserved = state.to_preserve(RetryLevel.FULL_RETRY)
    assert len(preserved) == 0

def test_to_preserve_missing_scene_list():
    """Missing scene_list should result in empty preserved dict"""
    state = ChapterGenerationState(
        draft_text="草稿文本"
    )
    preserved = state.to_preserve(RetryLevel.WRITE_ONLY)
    assert len(preserved) == 0
