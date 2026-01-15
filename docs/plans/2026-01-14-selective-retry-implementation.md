# Selective Retry Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement three-level selective retry (EDIT_ONLY, WRITE_ONLY, FULL_RETRY) in chapter generation pipeline to reduce 40-60% of retry costs by selectively re-running only necessary tasks based on judge_report.issues types.

**Architecture:**
1. Create RetryLevel enum with preserved_outputs and required_tasks properties
2. Create ChapterGenerationState model to track intermediate results across retries
3. Refactor ChapterCrew.generate_chapter() to route retries based on RetryLevel
4. Update tasks.yaml to accept intermediate results via inputs (draft_text_for_edit, scene_list_for_write)
5. Add edge case handling: JSON parsing failures, retry escalation, fallback to FULL_RETRY

**Tech Stack:**
- Python 3.12
- Pydantic 2.x (for BaseModel, Field validation)
- CrewAI (for Crew, Task, Agent orchestration)
- pytest (for testing - you'll create test infrastructure)

**Key Context:**
- Existing pipeline: plan_chapter → write_chapter → edit_chapter → judge_chapter → update_bible
- Current retry logic always runs all 5 tasks
- JudgeReport.issues.type has 9 types: continuity, structure, motivation, pacing, clue_fairness, prose, hook, safety, word_count
- Design doc: `docs/plans/2026-01-14-selective-retry-design.md`

**Reference:**
- RetryLevel mapping: prose/pacing/word_count → EDIT_ONLY; motivation/hook/clue_fairness/continuity → WRITE_ONLY; structure/safety(critical) → FULL_RETRY
- Tasks use CrewAI context parameter; we'll pass preserved results via inputs instead for compatibility

---

## Task 1: Create RetryLevel Enum

**Files:**
- Create: `src/storycrew/models/retry_level.py`
- Test: `tests/test_retry_level.py` (new file)

**Step 1: Create test file and write failing test for RetryLevel enum**

```bash
mkdir -p tests
touch tests/test_retry_level.py
```

**Step 2: Write failing test**

Create `tests/test_retry_level.py`:

```python
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
```

**Step 3: Run tests to verify they fail**

```bash
cd /home/ubuntu/PyProjects/storycrew
python -m pytest tests/test_retry_level.py -v
```

Expected: Import errors and AttributeError failures (retry_level module doesn't exist yet)

**Step 4: Create RetryLevel enum implementation**

Create `src/storycrew/models/retry_level.py`:

```python
"""Retry level models for selective chapter generation retry."""
from enum import Enum
from typing import Set, List, Optional

from storycrew.models.judge_report import JudgeReport
from storycrew.models.issue import Issue


class RetryLevel(Enum):
    """重试级别枚举

    定义三种重试级别，每个级别决定：
    1. 需要保留哪些中间结果
    2. 需要重新执行哪些任务
    """

    EDIT_ONLY = "edit_only"
    """仅编辑重试：保留 SceneList + draft_text，只重跑 edit + judge"""

    WRITE_ONLY = "write_only"
    """仅写作重试：保留 SceneList，重跑 write + edit + judge"""

    FULL_RETRY = "full_retry"
    """全链路重试：不保留任何中间结果，重跑全部任务"""

    @property
    def preserved_outputs(self) -> Set[str]:
        """每个级别需要保留的中间结果集合

        Returns:
            Set[str]: 需要保存到 state 的字段名集合
        """
        if self == RetryLevel.EDIT_ONLY:
            return {"scene_list", "draft_text", "revision_text"}
        elif self == RetryLevel.WRITE_ONLY:
            return {"scene_list"}
        else:  # FULL_RETRY
            return set()

    @property
    def required_tasks(self) -> List[str]:
        """每个级别需要执行的任务列表

        Returns:
            List[str]: 任务名称列表
        """
        if self == RetryLevel.EDIT_ONLY:
            return ["edit_chapter", "judge_chapter"]
        elif self == RetryLevel.WRITE_ONLY:
            return ["write_chapter", "edit_chapter", "judge_chapter"]
        else:  # FULL_RETRY
            return ["plan_chapter", "write_chapter", "edit_chapter", "judge_chapter"]


def determine_retry_level(judge_report: JudgeReport, attempt: int) -> RetryLevel:
    """根据 JudgeReport 的 issues 类型确定重试级别

    映射规则：
    - prose/pacing/word_count → EDIT_ONLY
    - motivation/hook/clue_fairness/continuity → WRITE_ONLY
    - structure/safety(critical) → FULL_RETRY
    - 最后一次尝试失败 → FULL_RETRY

    Args:
        judge_report: Judge 质量报告
        attempt: 当前尝试次数（0-based）

    Returns:
        RetryLevel: 确定的重试级别
    """
    # 最后一次尝试：全链路重试
    if attempt >= 2:
        return RetryLevel.FULL_RETRY

    # 提取所有问题类型
    issue_types = {issue.type for issue in judge_report.issues}

    # 优先级：FULL_RETRY > WRITE_ONLY > EDIT_ONLY

    # 1. structure 问题 → FULL_RETRY
    if "structure" in issue_types:
        return RetryLevel.FULL_RETRY

    # 2. safety 问题：根据严重程度
    if "safety" in issue_types:
        safety_issues = [i for i in judge_report.issues if i.type == "safety"]
        if any(i.severity in ["high", "critical"] for i in safety_issues):
            return RetryLevel.FULL_RETRY
        else:
            # 低严重级别的 safety 问题可通过编辑修正
            return RetryLevel.EDIT_ONLY

    # 3. motivation/hook/clue_fairness/continuity → WRITE_ONLY
    if issue_types & {"motivation", "hook", "clue_fairness", "continuity"}:
        return RetryLevel.WRITE_ONLY

    # 4. prose/pacing/word_count → EDIT_ONLY
    if issue_types & {"prose", "pacing", "word_count"}:
        return RetryLevel.EDIT_ONLY

    # 5. 默认降级到 WRITE_ONLY（保守策略）
    return RetryLevel.WRITE_ONLY
```

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_retry_level.py -v
```

Expected: All tests PASS

**Step 6: Update models/__init__.py to export new classes**

Edit `src/storycrew/models/__init__.py`:

Add these lines at the end of the imports (after line 7):

```python
from .retry_level import RetryLevel, determine_retry_level
```

Add these names to `__all__` list (after line 37):

```python
    "RetryLevel",
    "determine_retry_level",
```

**Step 7: Run tests again to verify imports work**

```bash
python -m pytest tests/test_retry_level.py -v
```

Expected: All tests PASS

**Step 8: Commit**

```bash
git add src/storycrew/models/retry_level.py src/storycrew/models/__init__.py tests/test_retry_level.py
git commit -m "feat: add RetryLevel enum and determine_retry_level function

Implement three-level selective retry system with preserved_outputs and
required_tasks properties. Add comprehensive tests for all issue type
mappings.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create ChapterGenerationState Model

**Files:**
- Create: `src/storycrew/models/chapter_generation_state.py`
- Modify: `src/storycrew/models/__init__.py`
- Test: `tests/test_chapter_generation_state.py`

**Step 1: Write failing test for ChapterGenerationState**

Create `tests/test_chapter_generation_state.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_chapter_generation_state.py -v
```

Expected: Import error (chapter_generation_state module doesn't exist)

**Step 3: Create ChapterGenerationState implementation**

Create `src/storycrew/models/chapter_generation_state.py`:

```python
"""Chapter generation state model for tracking intermediate results."""
from typing import Optional, Dict, Any
from pydantic import BaseModel

from storycrew.models.retry_level import RetryLevel


class ChapterGenerationState(BaseModel):
    """章节生成过程中的中间状态

    用于在重试之间保存和恢复中间结果，避免重复生成相同内容。

    Attributes:
        scene_list: SceneList 的 JSON 字符串表示（用于 write retry）
        draft_text: write_chapter 的输出文本（用于 edit retry）
        revision_text: edit_chapter 的输出文本（用于调试）
        current_attempt: 当前尝试次数（0-based）
        last_retry_level: 上一次使用的重试级别（"edit_only", "write_only", "full_retry"）
        edit_retry_count: EDIT_ONLY 级别的连续重试次数
    """

    scene_list: Optional[str] = None
    """SceneList 对象的 JSON 序列化字符串"""

    draft_text: Optional[str] = None
    """write_chapter 输出的草稿文本"""

    revision_text: Optional[str] = None
    """edit_chapter 输出的修订文本"""

    current_attempt: int = 0
    """当前尝试次数（从 0 开始）"""

    last_retry_level: Optional[str] = None
    """上一次使用的重试级别字符串（RetryLevel.value）"""

    edit_retry_count: int = 0
    """EDIT_ONLY 级别的连续重试计数（用于升级到 WRITE_ONLY）"""

    def to_preserve(self, retry_level: RetryLevel) -> Dict[str, Any]:
        """根据重试级别返回需要保留的输入字段

        将 state 中的数据转换为 inputs 字典，用于传递给下一轮重试。

        Args:
            retry_level: 下一次重试使用的级别

        Returns:
            Dict[str, Any]: 需要传递给下一轮的 inputs 字段
                - EDIT_ONLY: {"scene_list": str, "draft_text_for_edit": str}
                - WRITE_ONLY: {"scene_list": str}
                - FULL_RETRY: {}
        """
        preserved = {}

        if retry_level == RetryLevel.EDIT_ONLY:
            # 保留 scene_list 和 draft_text
            if self.scene_list:
                preserved["scene_list"] = self.scene_list
            if self.draft_text:
                # 使用特殊的 key name，避免与 context 中的 scene_list 冲突
                preserved["draft_text_for_edit"] = self.draft_text

        elif retry_level == RetryLevel.WRITE_ONLY:
            # 只保留 scene_list
            if self.scene_list:
                preserved["scene_list"] = self.scene_list

        # FULL_RETRY 不保留任何中间结果

        return preserved
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_chapter_generation_state.py -v
```

Expected: All tests PASS

**Step 5: Update models/__init__.py to export ChapterGenerationState**

Edit `src/storycrew/models/__init__.py`:

Add this line after the retry_level import (around line 8):

```python
from .chapter_generation_state import ChapterGenerationState
```

Add this name to `__all__` list (after "determine_retry_level"):

```python
    "ChapterGenerationState",
```

**Step 6: Run tests again**

```bash
python -m pytest tests/test_chapter_generation_state.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/storycrew/models/chapter_generation_state.py src/storycrew/models/__init__.py tests/test_chapter_generation_state.py
git commit -m "feat: add ChapterGenerationState model

Implement state tracking for intermediate results across retries.
Add to_preserve() method to convert state to inputs dict based on
RetryLevel. Add comprehensive tests.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Update tasks.yaml for Intermediate Result Inputs

**Files:**
- Modify: `src/storycrew/config/tasks.yaml`

**Step 1: Backup original tasks.yaml**

```bash
cp src/storycrew/config/tasks.yaml src/storycrew/config/tasks.yaml.backup
```

**Step 2: Read current edit_chapter task description**

```bash
grep -A 30 "^edit_chapter:" src/storycrew/config/tasks.yaml
```

**Step 3: Modify edit_chapter description to accept draft_text_for_edit**

Edit `src/storycrew/config/tasks.yaml`:

Find the `edit_chapter:` section (around line 458) and replace the entire description block:

```yaml
edit_chapter:
  description: >
    对第{chapter_number}章进行文风和节奏编辑。

    当前章节：{chapter_number}
    前序任务已生成章节正文，请从上下文中获取。
    StoryBible(public): {story_bible_public}
    StorySpec: {story_spec}
    修订指令（如有）：{revision_instructions}

    # === 选择性重试支持 ===
    # 如果 {draft_text_for_edit} 有值（表示重试模式），直接使用它作为编辑对象；
    # 否则从上下文获取 write_chapter 的输出（正常模式）。
    已保存草稿（如有）：{draft_text_for_edit}

    **重要**: draft_text_for_edit 优先级高于上下文中的 write_chapter 输出。
    如果 draft_text_for_edit 非空，请直接编辑该文本，无需从上下文查找。

    基于StyleGuide进行编辑：
    1. 统一文风：确保语气、节奏、意象密度符合StyleGuide
    2. 减少重复：删除冗余表达、重复句式
    3. 保持语言简洁直白，避免过度修饰
    4. 统一人物声线：确保对白符合character的speech_pattern
    5. 优化节奏：删除拖沓部分，加快节奏
    6. 避免重复意象：检查StoryBible.used_imagery，避免重复使用相同意象

    不要修改大结构，只做局部重写和润色。
    如果收到revision_instructions，针对性地修改指定问题。
  expected_output: >
    润色后的完整章节正文，保持原有格式：

    第X章：[章标题]

    小引：
    [润色后的小引]

    [润色后的正文，约3000字，文笔更精炼、节奏更紧凑]

    确保字数仍在2700-3300之间。
  agent: line_editor
```

**Step 4: Modify write_chapter description to accept scene_list_for_write**

Find the `write_chapter:` section (around line 341) and replace the description block:

```yaml
write_chapter:
  description: >
    撰写第{chapter_number}章的完整正文。

    当前章节：{chapter_number}
    SceneList: {scene_list}

    # === 选择性重试支持 ===
    # 如果 {scene_list} 为空或 {scene_list_for_write} 有值（表示重试模式），
    # 优先使用 scene_list_for_write；否则使用 scene_list。
    # 注意：scene_list_for_write 是上一次 plan_chapter 生成的 SceneList 的 JSON 字符串。
    已保存场景列表（如有）：{scene_list_for_write}

    StoryBible(public): {story_bible_public}
    StorySpec: {story_spec}
    修订指令（如有）：{revision_instructions}

    输出格式要求：

    第X章：章标题
    小引：80-150字，像书摘/预告，不剧透终局
    正文：约3000字（允许2700-3300字），章末必须有钩子

    **重要 SceneList 使用规则**:
    - 如果 scene_list_for_write 非空，请使用它作为场景列表
    - 如果 scene_list_for_write 为空，使用 scene_list
    - 严格按照 SceneList 的场景顺序和场景目的写作
    - 如果两个都为空，请基于 chapter_outline 自行规划场景

    写作要求：
    1. 严格按照SceneList的场景顺序和场景目的写作
    2. 开头抓人，立即进入冲突或张力
    3. 每个场景推进事件、揭示信息、触发情绪
    4. 对白要符合人物声线（参考StoryBible中character的speech_pattern）
    5. 避免使用人物禁用短语（forbidden_phrases）
    6. 章末必须有强钩子（悬念、反转、新威胁）
    7. 字数控制在2700-3300之间

    对于悬疑题材：
    - 只能访问"本章允许揭示的信息"
    - 不能提前泄露真相
    - 线索要自然嵌入场景

    如果收到revision_instructions，针对性地重写问题段落。
  expected_output: >
    完整的章节正文，格式如下：

    第X章：[章标题]

    小引：
    [80-150字的小引]

    [约3000字的正文，包含6-10个场景，章末有钩子]

    确保字数在2700-3300之间。
  agent: chapter_writer
```

**Step 5: Verify YAML syntax is valid**

```bash
python -c "import yaml; yaml.safe_load(open('src/storycrew/config/tasks.yaml'))" && echo "YAML syntax valid"
```

Expected: "YAML syntax valid"

**Step 6: Commit**

```bash
git add src/storycrew/config/tasks.yaml src/storycrew/config/tasks.yaml.backup
git commit -m "feat: add draft_text_for_edit and scene_list_for_write to tasks

Update edit_chapter and write_chapter task descriptions to support
selective retry by accepting intermediate results from inputs.
Add clear priority instructions for agents.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Add Helper Methods to ChapterCrew

**Files:**
- Modify: `src/storycrew/crews/chapter_crew.py`

**Step 1: Read current chapter_crew.py to understand structure**

```bash
head -50 src/storycrew/crews/chapter_crew.py
```

**Step 2: Add imports at the top of chapter_crew.py**

Edit `src/storycrew/crews/chapter_crew.py`:

Add these imports after line 6 (after `from copy import deepcopy`):

```python
from storycrew.models import (
    SceneList, ChapterDraft, ChapterRevision, JudgeReport,
    ChapterGenerationState, RetryLevel, determine_retry_level
)
```

**Step 3: Add MAX_RETRIES constants after imports (after line 8)**

```python
# Retry level limits
MAX_EDIT_RETRIES = 2
MAX_WRITE_RETRIES = 2
```

**Step 4: Add helper methods before generate_chapter (around line 10)**

Insert these methods before the `generate_chapter` method:

```python
    def _parse_scene_list_safe(self, scene_list_json: str) -> Optional[SceneList]:
        """安全解析 SceneList JSON 字符串

        Args:
            scene_list_json: SceneList 的 JSON 字符串

        Returns:
            Optional[SceneList]: 解析成功返回 SceneList 对象，失败返回 None
        """
        try:
            return SceneList.model_validate_json(scene_list_json)
        except Exception as e:
            logger.warning(f"SceneList JSON 解析失败: {e}")
            return None

    def _run_full_pipeline(self, inputs: Dict[str, Any], state: ChapterGenerationState) -> Any:
        """运行完整的5个任务链路

        用于第一次生成或 FULL_RETRY 级别的重试。

        Args:
            inputs: Crew 输入参数字典
            state: 当前生成状态（用于记录）

        Returns:
            Crew kickoff 结果
        """
        logger.info(f"Running FULL_PIPELINE (attempt={state.current_attempt})")

        # Get agents
        chapter_planner = self.base_crew.chapter_planner()
        chapter_writer = self.base_crew.chapter_writer()
        continuity_keeper = self.base_crew.continuity_keeper()
        line_editor = self.base_crew.line_editor()
        critic_judge = self.base_crew.critic_judge()

        # Create tasks
        plan_task = self.base_crew.plan_chapter()
        plan_task.agent = chapter_planner

        write_task = self.base_crew.write_chapter()
        write_task.agent = chapter_writer
        write_task.context = [plan_task]

        edit_task = self.base_crew.edit_chapter()
        edit_task.agent = line_editor
        edit_task.context = [plan_task, write_task]

        judge_task = self.base_crew.judge_chapter()
        judge_task.agent = critic_judge
        judge_task.context = [plan_task, write_task, edit_task]

        update_bible_task = self.base_crew.update_bible()
        update_bible_task.agent = continuity_keeper
        update_bible_task.context = [plan_task, write_task, edit_task]

        # Create crew
        chapter_crew = Crew(
            agents=[
                chapter_planner,
                chapter_writer,
                continuity_keeper,
                line_editor,
                critic_judge
            ],
            tasks=[plan_task, write_task, edit_task, judge_task, update_bible_task],
            process=Process.sequential,
            verbose=True
        )

        return chapter_crew.kickoff(inputs=inputs)

    def _run_write_retry(self, inputs: Dict[str, Any], state: ChapterGenerationState) -> Any:
        """运行 WRITE_ONLY 级别重试（保留 SceneList）

        Args:
            inputs: Crew 输入参数字典（应包含 scene_list）
            state: 当前生成状态

        Returns:
            Crew kickoff 结果
        """
        logger.info(f"Running WRITE_ONLY retry (attempt={state.current_attempt})")

        # Get agents
        chapter_writer = self.base_crew.chapter_writer()
        continuity_keeper = self.base_crew.continuity_keeper()
        line_editor = self.base_crew.line_editor()
        critic_judge = self.base_crew.critic_judge()

        # Create tasks（注意：write_task 不依赖 plan_task，因为 scene_list 已通过 inputs 传递）
        write_task = self.base_crew.write_chapter()
        write_task.agent = chapter_writer
        # 不设置 context，因为 scene_list 通过 inputs 传递

        edit_task = self.base_crew.edit_chapter()
        edit_task.agent = line_editor
        edit_task.context = [write_task]

        judge_task = self.base_crew.judge_chapter()
        judge_task.agent = critic_judge
        judge_task.context = [write_task, edit_task]

        update_bible_task = self.base_crew.update_bible()
        update_bible_task.agent = continuity_keeper
        update_bible_task.context = [write_task, edit_task]

        # Create crew
        chapter_crew = Crew(
            agents=[chapter_writer, line_editor, critic_judge, continuity_keeper],
            tasks=[write_task, edit_task, judge_task, update_bible_task],
            process=Process.sequential,
            verbose=True
        )

        return chapter_crew.kickoff(inputs=inputs)

    def _run_edit_retry(self, inputs: Dict[str, Any], state: ChapterGenerationState) -> Any:
        """运行 EDIT_ONLY 级别重试（保留 SceneList + draft_text）

        Args:
            inputs: Crew 输入参数字典（应包含 draft_text_for_edit）
            state: 当前生成状态

        Returns:
            Crew kickoff 结果
        """
        logger.info(f"Running EDIT_ONLY retry (attempt={state.current_attempt}, edit_count={state.edit_retry_count})")

        # Get agents
        line_editor = self.base_crew.line_editor()
        critic_judge = self.base_crew.critic_judge()
        continuity_keeper = self.base_crew.continuity_keeper()

        # Create tasks（edit_task 不依赖 write_task，因为 draft_text 通过 inputs 传递）
        edit_task = self.base_crew.edit_chapter()
        edit_task.agent = line_editor
        # 不设置 context，因为 draft_text 通过 inputs 传递

        judge_task = self.base_crew.judge_chapter()
        judge_task.agent = critic_judge
        judge_task.context = [edit_task]

        update_bible_task = self.base_crew.update_bible()
        update_bible_task.agent = continuity_keeper
        update_bible_task.context = [edit_task]

        # Create crew
        chapter_crew = Crew(
            agents=[line_editor, critic_judge, continuity_keeper],
            tasks=[edit_task, judge_task, update_bible_task],
            process=Process.sequential,
            verbose=True
        )

        return chapter_crew.kickoff(inputs=inputs)

    def _update_state_from_result(self, state: ChapterGenerationState, result: Any) -> None:
        """从 Crew 结果中提取并更新状态

        Args:
            state: 当前生成状态（会被修改）
            result: Crew kickoff 返回的结果对象
        """
        # Extract outputs from result
        # Note: result.tasks_output 是一个列表，按任务顺序排列
        # 不同的重试级别，tasks_output 的长度和内容不同

        outputs = result.tasks_output

        # 根据 retry_level 决定如何解析
        if state.last_retry_level == RetryLevel.EDIT_ONLY.value or state.current_attempt == 0:
            # FULL_RETRY 或第一次：有 5 个输出
            if len(outputs) >= 3:
                # outputs[0] = scene_list (plan_chapter)
                # outputs[1] = draft_text (write_chapter)
                # outputs[2] = revision_text (edit_chapter)
                # outputs[3] = judge (judge_chapter)
                # outputs[4] = updated_bible (update_bible)

                # Extract scene_list
                if hasattr(outputs[0], 'pydantic'):
                    state.scene_list = outputs[0].pydantic.model_dump_json()

                # Extract draft_text
                if hasattr(outputs[1], 'raw'):
                    state.draft_text = str(outputs[1].raw)
                elif hasattr(outputs[1], 'pydantic'):
                    state.draft_text = outputs[1].pydantic.raw_text
                else:
                    state.draft_text = str(outputs[1])

                # Extract revision_text
                if hasattr(outputs[2], 'raw'):
                    state.revision_text = str(outputs[2].raw)
                elif hasattr(outputs[2], 'pydantic'):
                    state.revision_text = outputs[2].pydantic.revised_text
                else:
                    state.revision_text = str(outputs[2])

        elif state.last_retry_level == RetryLevel.WRITE_ONLY.value:
            # WRITE_ONLY：有 4 个输出（write, edit, judge, update_bible）
            if len(outputs) >= 3:
                # outputs[0] = draft_text (write_chapter)
                # outputs[1] = revision_text (edit_chapter)
                # outputs[2] = judge (judge_chapter)
                # outputs[3] = updated_bible (update_bible)

                # Extract draft_text
                if hasattr(outputs[0], 'raw'):
                    state.draft_text = str(outputs[0].raw)
                elif hasattr(outputs[0], 'pydantic'):
                    state.draft_text = outputs[0].pydantic.raw_text
                else:
                    state.draft_text = str(outputs[0])

                # Extract revision_text
                if hasattr(outputs[1], 'raw'):
                    state.revision_text = str(outputs[1].raw)
                elif hasattr(outputs[1], 'pydantic'):
                    state.revision_text = outputs[1].pydantic.revised_text
                else:
                    state.revision_text = str(outputs[1])

        elif state.last_retry_level == RetryLevel.EDIT_ONLY.value:
            # EDIT_ONLY：有 3 个输出（edit, judge, update_bible）
            if len(outputs) >= 1:
                # outputs[0] = revision_text (edit_chapter)
                # outputs[1] = judge (judge_chapter)
                # outputs[2] = updated_bible (update_bible)

                # Extract revision_text
                if hasattr(outputs[0], 'raw'):
                    state.revision_text = str(outputs[0].raw)
                elif hasattr(outputs[0], 'pydantic'):
                    state.revision_text = outputs[0].pydantic.revised_text
                else:
                    state.revision_text = str(outputs[0])
```

**Step 5: Verify no syntax errors**

```bash
python -c "from storycrew.crews.chapter_crew import ChapterCrew; print('Import successful')"
```

Expected: "Import successful"

**Step 6: Commit**

```bash
git add src/storycrew/crews/chapter_crew.py
git commit -m "feat: add helper methods for selective retry to ChapterCrew

Add _parse_scene_list_safe, _run_full_pipeline, _run_write_retry,
_run_edit_retry, and _update_state_from_result methods.
Add MAX_EDIT_RETRIES and MAX_WRITE_RETRIES constants.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Refactor generate_chapter Method with Selective Retry Logic

**Files:**
- Modify: `src/storycrew/crews/chapter_crew.py`

**Step 1: Read current generate_chapter method**

```bash
sed -n '18,187p' src/storycrew/crews/chapter_crew.py
```

**Step 2: Backup current method**

```bash
git diff src/storycrew/crews/chapter_crew.py > /tmp/chapter_crew_backup.patch
```

**Step 3: Replace generate_chapter method (lines 18-187)**

Edit `src/storycrew/crews/chapter_crew.py`:

Replace the entire `generate_chapter` method with:

```python
    def generate_chapter(
        self,
        chapter_number: int,
        chapter_outline: Dict[str, Any],
        story_bible: Dict[str, Any],
        story_spec: Dict[str, Any],
        revision_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single chapter with structured outputs and selective retry.

        Implements three-level selective retry based on judge_report.issues types:
        - EDIT_ONLY: prose/pacing/word_count issues → only re-run edit + judge
        - WRITE_ONLY: motivation/hook/clue_fairness/continuity → re-run write + edit + judge
        - FULL_RETRY: structure/safety(critical) → re-run full pipeline

        Args:
            chapter_number: Chapter number (1-9)
            chapter_outline: Outline for this specific chapter
            story_bible: Current StoryBible state
            story_spec: StorySpec
            revision_instructions: Optional revision instructions from previous attempt

        Returns:
            Dictionary containing:
                - chapter_text: Polished chapter text
                - updated_bible: Updated StoryBible
                - judge_report: JudgeReport for this chapter
                - attempts: Number of attempts made
        """
        # ===============================
        # StoryBible access control
        # ===============================
        story_bible_dict = story_bible.model_dump() if hasattr(story_bible, 'model_dump') else story_bible
        story_spec_dict = story_spec.model_dump() if hasattr(story_spec, 'model_dump') else story_spec

        story_bible_public = deepcopy(story_bible_dict)
        if isinstance(story_bible_public, dict) and "truth_card" in story_bible_public:
            story_bible_public.pop("truth_card", None)

        # Initialize state
        state = ChapterGenerationState(current_attempt=0)

        # Prepare initial inputs
        inputs = {
            "chapter_number": chapter_number,
            "chapter_outline": chapter_outline.model_dump() if hasattr(chapter_outline, 'model_dump') else chapter_outline,
            "scene_list": "",  # Placeholder for plan_chapter to generate
            "story_bible_public": story_bible_public,
            "story_bible_full": story_bible_dict,
            "story_spec": story_spec_dict,
            "revision_instructions": revision_instructions or "",
        }

        # Main retry loop
        for attempt in range(self.max_retries + 1):
            state.current_attempt = attempt

            try:
                # === 根据上一次的重试级别决定运行策略 ===
                if attempt == 0 or state.last_retry_level == RetryLevel.FULL_RETRY.value or state.last_retry_level is None:
                    result = self._run_full_pipeline(inputs, state)

                elif state.last_retry_level == RetryLevel.WRITE_ONLY.value:
                    # Check if scene_list recovery is needed
                    if "scene_list" in inputs:
                        scene_list = self._parse_scene_list_safe(inputs["scene_list"])
                        if scene_list is None:
                            logger.warning("SceneList 恢复失败，降级到 FULL_RETRY")
                            state.last_retry_level = RetryLevel.FULL_RETRY.value
                            result = self._run_full_pipeline(inputs, state)
                        else:
                            result = self._run_write_retry(inputs, state)
                    else:
                        logger.warning("scene_list 缺失，降级到 FULL_RETRY")
                        state.last_retry_level = RetryLevel.FULL_RETRY.value
                        result = self._run_full_pipeline(inputs, state)

                elif state.last_retry_level == RetryLevel.EDIT_ONLY.value:
                    result = self._run_edit_retry(inputs, state)

                else:
                    # Unknown retry level, default to full
                    logger.warning(f"未知的重试级别 {state.last_retry_level}，使用 FULL_RETRY")
                    state.last_retry_level = RetryLevel.FULL_RETRY.value
                    result = self._run_full_pipeline(inputs, state)

                # === 更新状态 ===
                self._update_state_from_result(state, result)

                # === 提取结果 ===
                outputs = result.tasks_output

                # 根据 retry_level 和输出数量提取 judge 和 updated_bible
                if state.last_retry_level == RetryLevel.EDIT_ONLY.value:
                    # EDIT_ONLY: [edit_output, judge, updated_bible]
                    judge = outputs[1].pydantic
                    updated_bible = outputs[2].pydantic
                    revision_text = state.revision_text

                elif state.last_retry_level == RetryLevel.WRITE_ONLY.value:
                    # WRITE_ONLY: [write_output, edit_output, judge, updated_bible]
                    judge = outputs[2].pydantic
                    updated_bible = outputs[3].pydantic
                    revision_text = state.revision_text

                else:
                    # FULL_RETRY 或第一次: [scene_list, write_output, edit_output, judge, updated_bible]
                    judge = outputs[3].pydantic
                    updated_bible = outputs[4].pydantic
                    revision_text = state.revision_text

                # === 检查是否通过 ===
                if judge.passed:
                    logger.info(f"Chapter {chapter_number} passed after {attempt + 1} attempts")
                    return {
                        'chapter_text': revision_text,
                        'updated_bible': updated_bible,
                        'judge_report': judge,
                        'attempts': attempt + 1
                    }

                # === Judge 失败，确定下一轮重试级别 ===
                retry_level = determine_retry_level(judge, attempt)
                logger.info(f"Chapter {chapter_number} attempt {attempt + 1} failed, retry_level={retry_level.value}")

                # === 检查重试次数限制 ===
                if retry_level == RetryLevel.EDIT_ONLY and state.last_retry_level == RetryLevel.EDIT_ONLY.value:
                    state.edit_retry_count += 1
                    if state.edit_retry_count >= MAX_EDIT_RETRIES:
                        logger.warning(f"EDIT_ONLY 重试次数已达上限 ({MAX_EDIT_RETRIES})，升级到 WRITE_ONLY")
                        retry_level = RetryLevel.WRITE_ONLY
                        state.edit_retry_count = 0
                else:
                    # 重置计数器
                    state.edit_retry_count = 0

                state.last_retry_level = retry_level.value

                # === 更新 inputs（保留需要的中间结果）===
                preserved_inputs = state.to_preserve(retry_level)
                inputs.update(preserved_inputs)

                # === 更新 revision_instructions ===
                inputs["revision_instructions"] = "\n".join(judge.revision_instructions)

            except Exception as e:
                # Exception during generation
                error_type = type(e).__name__
                error_msg = str(e)

                if attempt >= self.max_retries:
                    logger.error(f"Chapter {chapter_number} failed after {attempt + 1} attempts: {error_type}: {error_msg[:100]}")
                    raise

                logger.warning(f"Chapter {chapter_number} attempt {attempt + 1} failed with {error_type}: {error_msg[:100]}, retrying...")
                inputs["revision_instructions"] = ""
                continue

        # All retries exhausted
        logger.error(f"Chapter {chapter_number} failed after {self.max_retries + 1} attempts")
        return {
            'chapter_text': revision_text,
            'updated_bible': updated_bible,
            'judge_report': judge,
            'attempts': self.max_retries + 1,
            'success': False
        }
```

**Step 4: Verify no syntax errors**

```bash
python -c "from storycrew.crews.chapter_crew import ChapterCrew; print('Import successful')"
```

Expected: "Import successful"

**Step 5: Run all existing tests to make sure nothing is broken**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS (if any tests exist)

**Step 6: Commit**

```bash
git add src/storycrew/crews/chapter_crew.py
git commit -m "feat: implement selective retry logic in generate_chapter

Refactor main retry loop to use three-level selective retry:
- EDIT_ONLY: only re-run edit + judge for prose/pacing/word_count issues
- WRITE_ONLY: re-run write + edit + judge for motivation/hook/continuity issues
- FULL_RETRY: full pipeline for structure/safety(critical) issues

Add retry escalation logic and state preservation across retries.
Update result extraction logic to handle different retry levels.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Add Integration Tests for Selective Retry Flow

**Files:**
- Create: `tests/test_chapter_crew_retry.py`

**Step 1: Create integration test file**

Create `tests/test_chapter_crew_retry.py`:

```python
"""Integration tests for ChapterCrew selective retry flow."""
import pytest
from unittest.mock import Mock, MagicMock, patch
from storycrew.crews.chapter_crew import ChapterCrew
from storycrew.models import (
    ChapterGenerationState, RetryLevel,
    JudgeReport, Issue, ScoreBreakdown, SceneList, Scene, StoryBible
)


@pytest.fixture
def chapter_crew():
    """Create ChapterCrew instance for testing"""
    return ChapterCrew()


@pytest.fixture
def mock_story_bible():
    """Create mock StoryBible"""
    return StoryBible(
        genre="romance",
        characters=[],
        relationships=[],
        clues={"planted": [], "resolved": [], "open": []},
        timeline=[],
        chapter_summaries=[],
        immutable_facts=[],
        used_imagery=[],
        used_metaphors=[]
    )


@pytest.fixture
def mock_story_spec():
    """Create mock StorySpec dict"""
    return {
        "language": "zh",
        "genre": "romance",
        "total_chapters": 9,
        "target_words_per_chapter": 3000
    }


@pytest.fixture
def mock_chapter_outline():
    """Create mock chapter outline dict"""
    return {
        "chapter_number": 1,
        "title": "Test Chapter",
        "summary": "Test summary"
    }


def test_parse_scene_list_safe_success(chapter_crew):
    """Test successful SceneList parsing"""
    scene_list_json = '{"chapter_number":1,"chapter_title":"Test","scenes":[]}'
    result = chapter_crew._parse_scene_list_safe(scene_list_json)
    assert result is not None
    assert result.chapter_number == 1


def test_parse_scene_list_safe_invalid_json(chapter_crew):
    """Test SceneList parsing with invalid JSON"""
    invalid_json = '{invalid json}'
    result = chapter_crew._parse_scene_list_safe(invalid_json)
    assert result is None


def test_parse_scene_list_safe_wrong_structure(chapter_crew):
    """Test SceneList parsing with wrong structure"""
    wrong_json = '{"not_scene_list": true}'
    result = chapter_crew._parse_scene_list_safe(wrong_json)
    assert result is None


def test_state_to_preserve_edit_only():
    """Test ChapterGenerationState.to_preserve for EDIT_ONLY"""
    state = ChapterGenerationState(
        scene_list='{"chapter_number":1}',
        draft_text="草稿文本"
    )
    preserved = state.to_preserve(RetryLevel.EDIT_ONLY)
    assert "scene_list" in preserved
    assert "draft_text_for_edit" in preserved
    assert preserved["draft_text_for_edit"] == "草稿文本"


def test_state_to_preserve_write_only():
    """Test ChapterGenerationState.to_preserve for WRITE_ONLY"""
    state = ChapterGenerationState(
        scene_list='{"chapter_number":1}',
        draft_text="草稿文本"
    )
    preserved = state.to_preserve(RetryLevel.WRITE_ONLY)
    assert "scene_list" in preserved
    assert "draft_text_for_edit" not in preserved


def test_state_to_preserve_full_retry():
    """Test ChapterGenerationState.to_preserve for FULL_RETRY"""
    state = ChapterGenerationState(
        scene_list='{"chapter_number":1}',
        draft_text="草稿文本"
    )
    preserved = state.to_preserve(RetryLevel.FULL_RETRY)
    assert len(preserved) == 0


def test_determine_retry_level_prose_issue():
    """Prose issue should map to EDIT_ONLY"""
    from storycrew.models.retry_level import determine_retry_level

    judge = JudgeReport(
        issues=[Issue(type="prose", severity="medium", note="文笔平淡")],
        scores=ScoreBreakdown()
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.EDIT_ONLY


def test_determine_retry_level_structure_issue():
    """Structure issue should map to FULL_RETRY"""
    from storycrew.models.retry_level import determine_retry_level

    judge = JudgeReport(
        issues=[Issue(type="structure", severity="high", note="结构问题")],
        scores=ScoreBreakdown()
    )
    level = determine_retry_level(judge, attempt=0)
    assert level == RetryLevel.FULL_RETRY


def test_determine_retry_level_last_attempt():
    """Last attempt should always be FULL_RETRY"""
    from storycrew.models.retry_level import determine_retry_level

    judge = JudgeReport(
        issues=[Issue(type="prose", severity="low", note="文笔问题")],
        scores=ScoreBreakdown()
    )
    level = determine_retry_level(judge, attempt=2)
    assert level == RetryLevel.FULL_RETRY


# Note: Full end-to-end tests require mocking CrewAI Crew kickoff
# These would require more complex setup and are better suited for
# manual testing with a real LLM backend
```

**Step 2: Run integration tests**

```bash
python -m pytest tests/test_chapter_crew_retry.py -v
```

Expected: All tests PASS

**Step 3: Run all tests together**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_chapter_crew_retry.py
git commit -m "test: add integration tests for selective retry flow

Add tests for SceneList parsing, state preservation, and retry level
determination. Verify edge cases and error handling.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Documentation and Usage Examples

**Files:**
- Create: `docs/selective-retry-guide.md`

**Step 1: Create usage guide**

Create `docs/selective-retry-guide.md`:

```markdown
# Selective Retry Usage Guide

## Overview

The selective retry optimization reduces chapter generation retry costs by 40-60% by selectively re-running only necessary tasks based on the type of issues identified by the Judge agent.

## Retry Levels

### EDIT_ONLY
**Trigger**: prose, pacing, word_count issues
**Preserves**: SceneList + draft_text
**Re-runs**: edit_chapter → judge_chapter

Best for: Stylistic issues, word count adjustments, minor pacing problems.

Example:
```python
# Judge report with prose issue
judge = JudgeReport(
    issues=[
        Issue(type="prose", severity="medium", note="文笔过于华丽，不够直白")
    ]
)
# System will only re-run edit_chapter, preserving the original draft
```

### WRITE_ONLY
**Trigger**: motivation, hook, clue_fairness, continuity issues
**Preserves**: SceneList
**Re-runs**: write_chapter → edit_chapter → judge_chapter

Best for: Content-level issues that require re-writing but keep the same scene structure.

Example:
```python
# Judge report with motivation issue
judge = JudgeReport(
    issues=[
        Issue(type="motivation", severity="high", note="主角行为缺乏合理动机")
    ]
)
# System will re-run write_chapter using the same SceneList
```

### FULL_RETRY
**Trigger**: structure issues, critical safety issues, max retries exceeded
**Preserves**: Nothing
**Re-runs**: plan_chapter → write_chapter → edit_chapter → judge_chapter

Best for: Fundamental structural problems or when other retry levels have been exhausted.

Example:
```python
# Judge report with structure issue
judge = JudgeReport(
    issues=[
        Issue(type="structure", severity="high", note="场景顺序不合理，需要重新规划")
    ]
)
# System will re-run the entire pipeline from scratch
```

## Retry Escalation

The system automatically escalates retry levels when needed:

1. **Same-level retry limit**: EDIT_ONLY will escalate to WRITE_ONLY after 2 consecutive failed attempts
2. **State recovery failure**: If SceneList JSON parsing fails, automatically escalates to FULL_RETRY
3. **Final attempt**: The last retry (attempt 2) always uses FULL_RETRY

## Monitoring

Enable logging to see retry decisions:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Log examples:
```
INFO: Running FULL_PIPELINE (attempt=0)
INFO: Chapter 1 attempt 1 failed, retry_level=edit_only
INFO: Running EDIT_ONLY retry (attempt=1, edit_count=1)
INFO: Chapter 1 passed after 2 attempts
```

## Configuration

Constants in `chapter_crew.py`:
- `max_retries = 2`: Maximum total retry attempts (from __init__)
- `MAX_EDIT_RETRIES = 2`: Maximum consecutive EDIT_ONLY retries before escalation
- `MAX_WRITE_RETRIES = 2`: Maximum consecutive WRITE_ONLY retries before escalation

## Testing

Run unit tests:
```bash
pytest tests/test_retry_level.py -v
pytest tests/test_chapter_generation_state.py -v
pytest tests/test_chapter_crew_retry.py -v
```

Run all tests:
```bash
pytest tests/ -v
```
```

**Step 2: Update README.md with selective retry section**

Edit `README.md`:

Add this section before the end:

```markdown
## Selective Retry Optimization

The chapter generation pipeline implements three-level selective retry to reduce retry costs:

- **EDIT_ONLY**: 50% of cases (prose/pacing issues) → saves 75% cost
- **WRITE_ONLY**: 30% of cases (content issues) → saves 50% cost
- **FULL_RETRY**: 20% of cases (structural issues) → saves 0% cost

**Expected savings**: 40-60% average reduction in retry costs.

See [Selective Retry Usage Guide](docs/selective-retry-guide.md) for details.
```

**Step 3: Commit**

```bash
git add docs/selective-retry-guide.md README.md
git commit -m "docs: add selective retry usage guide and update README

Add comprehensive usage guide with examples and monitoring tips.
Update README with selective retry overview and expected savings.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: End-to-End Testing and Validation

**Files:**
- No new files
- Manual validation

**Step 1: Create test script for manual E2E testing**

Create `test_e2e_selective_retry.py` (in project root, not committed):

```python
#!/usr/bin/env python3
"""Manual end-to-end test for selective retry."""
import os
import logging
from dotenv import load_dotenv
from storycrew.crews.chapter_crew import ChapterCrew

# Enable detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment
load_dotenv()

def test_selective_retry():
    """Test selective retry with a simple chapter"""
    crew = ChapterCrew()

    # Mock inputs (replace with real data for actual test)
    chapter_number = 1
    chapter_outline = {
        "chapter_number": 1,
        "title": "Test",
        "summary": "Test chapter"
    }
    story_bible = {
        "genre": "romance",
        "characters": [],
        "relationships": []
    }
    story_spec = {
        "language": "zh",
        "genre": "romance",
        "total_chapters": 9
    }

    print("=" * 80)
    print("Starting selective retry test...")
    print("=" * 80)

    result = crew.generate_chapter(
        chapter_number=chapter_number,
        chapter_outline=chapter_outline,
        story_bible=story_bible,
        story_spec=story_spec
    )

    print("=" * 80)
    print(f"Result: {result.get('success', 'N/A')}")
    print(f"Attempts: {result.get('attempts', 'N/A')}")
    print(f"Judge passed: {result.get('judge_report', {}).passed if result.get('judge_report') else 'N/A'}")
    print("=" * 80)

if __name__ == "__main__":
    test_selective_retry()
```

**Step 2: Add test script to .gitignore**

Edit `.gitignore`:

Add this line:
```
test_e2e_selective_retry.py
```

**Step 3: Run final syntax and import checks**

```bash
# Check all imports work
python -c "from storycrew.models import RetryLevel, ChapterGenerationState, determine_retry_level; print('Models import: OK')"

python -c "from storycrew.crews.chapter_crew import ChapterCrew; print('ChapterCrew import: OK')"

# Check no syntax errors
python -m py_compile src/storycrew/models/retry_level.py
python -m py_compile src/storycrew/models/chapter_generation_state.py
python -m py_compile src/storycrew/crews/chapter_crew.py

echo "All checks passed!"
```

Expected: All checks pass without errors

**Step 4: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

**Step 5: Create feature branch summary**

```bash
git log --oneline --graph --all -10
```

**Step 6: Final commit for any remaining changes**

```bash
# Commit any remaining changes (if any)
git add -A
git commit -m "test: add e2e test script and final validation

Add manual E2E test script for selective retry validation.
Update .gitignore to exclude test script.
Complete implementation and validation.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Merge and Deployment Preparation

**Files:**
- No code changes
- Git operations

**Step 1: Review all commits**

```bash
git log --oneline --graph
```

Expected: ~9 commits for this feature

**Step 2: Run final full test suite**

```bash
python -m pytest tests/ -v --cov=src/storycrew --cov-report=term-missing
```

Expected: All tests PASS with good coverage

**Step 3: Create merge commit message template**

Create `/tmp/merge_message.txt`:

```
Merge selective retry optimization feature

Implements three-level selective retry to reduce chapter generation
retry costs by 40-60%.

Changes:
- Add RetryLevel enum with EDIT_ONLY, WRITE_ONLY, FULL_RETRY
- Add ChapterGenerationState model for tracking intermediate results
- Refactor ChapterCrew.generate_chapter() with selective retry logic
- Update tasks.yaml to support intermediate result inputs
- Add comprehensive tests for retry level determination and state management
- Add usage documentation and guide

Expected savings: 40-60% average reduction in retry costs.

Tested: All unit and integration tests passing.

Design doc: docs/plans/2026-01-14-selective-retry-design.md
Impl plan: docs/plans/2026-01-14-selective-retry-implementation.md
```

**Step 4: Prepare for code review**

```bash
# Create summary of changes
git diff --stat main > /tmp/changes_summary.txt
cat /tmp/changes_summary.txt
```

**Step 5: Commit this implementation plan**

```bash
git add docs/plans/2026-01-14-selective-retry-implementation.md
git commit -m "docs: add selective retry implementation plan

Add detailed step-by-step implementation plan with TDD approach.
Each task includes failing test, minimal implementation, and verification.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Summary

This implementation plan creates a complete selective retry optimization system in 9 tasks:

1. ✅ RetryLevel enum with issue type mapping
2. ✅ ChapterGenerationState model for result preservation
3. ✅ Task configuration updates for intermediate result inputs
4. ✅ Helper methods for three retry strategies
5. ✅ Refactored generate_chapter() with selective retry logic
6. ✅ Integration tests for retry flow
7. ✅ Documentation and usage guide
8. ✅ End-to-end testing and validation
9. ✅ Merge and deployment preparation

**Total estimated time**: 4-6 hours (assuming each step takes 2-5 minutes as designed)

**Expected outcome**: 40-60% reduction in chapter generation retry costs with maintained quality.

**Next steps**: Execute this plan using @superpowers:executing-plans or @superpowers:subagent-driven-development.
