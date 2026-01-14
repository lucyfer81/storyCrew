# 选择性重试优化设计方案

**日期**: 2026-01-14
**作者**: Claude (Sonnet 4.5)
**状态**: 已批准，待实施

---

## 1. 问题陈述

### 1.1 现状问题

一旦 Judge 不通过，系统会重跑整个链路（Plan → Write → Edit）。如果是文笔问题，重跑 Plan 是巨大的浪费。

### 1.2 现有流程

```
plan_chapter (SceneList)
  → write_chapter (raw_text)
  → edit_chapter (revision_text)
  → judge_chapter (JudgeReport)
  → update_bible (StoryBible)
```

### 1.3 现有重试逻辑

- Judge 失败后，重新执行**全部5个任务**
- 仅通过 `revision_instructions` 传递反馈给下一轮
- **问题**：文笔问题也会重新跑 Plan 和 Write，浪费资源

---

## 2. 设计目标

**核心目标**: 根据 `judge_report.issues` 类型，选择性重试部分任务，降低 40-60% 的单章修正成本。

---

## 3. 方案A：三级精细重试（已选定）

### 3.1 重试级别定义

| 重试级别 | 触发条件 | 保留内容 | 重新执行 |
|---------|---------|---------|---------|
| **EDIT_ONLY** | prose, pacing, word_count | SceneList + draft_text | edit_chapter → judge_chapter |
| **WRITE_ONLY** | motivation, hook, clue_fairness, continuity | SceneList | write_chapter → edit_chapter → judge_chapter |
| **FULL_RETRY** | structure, safety(critical), max_retries exceeded | 无 | plan_chapter → write_chapter → edit_chapter → judge_chapter |

### 3.2 Issue 类型映射

```python
def determine_retry_level(judge_report: JudgeReport, attempt: int) -> RetryLevel:
    """
    映射规则：
    - prose/pacing/word_count → EDIT_ONLY
    - motivation/hook/clue_fairness/continuity → WRITE_ONLY
    - structure/safety(critical) → FULL_RETRY
    - 最后一次尝试失败 → FULL_RETRY
    """
```

### 3.3 预期收益

假设问题类型分布：
- 文笔/节奏/字数问题：50% → 节省 75%
- 动机/钩子/线索问题：30% → 节省 50%
- 结构问题：15% → 节省 0%
- 其他：5%

**加权平均节省**: `0.5 × 75% + 0.3 × 50% = 52.5%`

考虑多次重试的累积效应，实际节省可能达到 **40-60%**。

---

## 4. 核心数据结构

### 4.1 RetryLevel 枚举

**文件**: `src/storycrew/models/retry_level.py`

```python
from enum import Enum
from typing import Set, List

class RetryLevel(Enum):
    """重试级别枚举"""
    EDIT_ONLY = "edit_only"
    WRITE_ONLY = "write_only"
    FULL_RETRY = "full_retry"

    @property
    def preserved_outputs(self) -> Set[str]:
        """每个级别需要保留的中间结果"""
        if self == RetryLevel.EDIT_ONLY:
            return {"scene_list", "draft_text", "revision_text"}
        elif self == RetryLevel.WRITE_ONLY:
            return {"scene_list"}
        else:
            return set()

    @property
    def required_tasks(self) -> List[str]:
        """每个级别需要执行的任务"""
        if self == RetryLevel.EDIT_ONLY:
            return ["edit_chapter", "judge_chapter"]
        elif self == RetryLevel.WRITE_ONLY:
            return ["write_chapter", "edit_chapter", "judge_chapter"]
        else:
            return ["plan_chapter", "write_chapter", "edit_chapter", "judge_chapter"]
```

### 4.2 ChapterGenerationState

**文件**: `src/storycrew/models/chapter_generation_state.py`

```python
from typing import Optional, Dict, Any
from pydantic import BaseModel

class ChapterGenerationState(BaseModel):
    """章节生成过程中的中间状态"""
    scene_list: Optional[str] = None  # JSON 字符串
    draft_text: Optional[str] = None
    revision_text: Optional[str] = None
    current_attempt: int = 0
    last_retry_level: Optional[str] = None
    edit_retry_count: int = 0  # EDIT_ONLY 连续重试计数

    def to_preserve(self, retry_level: RetryLevel) -> Dict[str, Any]:
        """根据重试级别返回需要保留的输入字段"""
        preserved = {}

        if retry_level == RetryLevel.EDIT_ONLY:
            if self.scene_list:
                preserved["scene_list"] = self.scene_list
            if self.draft_text:
                preserved["draft_text_for_edit"] = self.draft_text

        elif retry_level == RetryLevel.WRITE_ONLY:
            if self.scene_list:
                preserved["scene_list"] = self.scene_list

        return preserved
```

---

## 5. 状态保存与恢复机制

### 5.1 核心流程改造

**文件**: `src/storycrew/crews/chapter_crew.py`

```python
def generate_chapter(self, chapter_number, chapter_outline, story_bible, story_spec, revision_instructions=None):
    """改造后的生成方法"""
    state = ChapterGenerationState(current_attempt=0)

    for attempt in range(self.max_retries + 1):
        state.current_attempt = attempt

        # === 根据上一次的重试级别决定运行策略 ===
        if attempt == 0 or state.last_retry_level == RetryLevel.FULL_RETRY:
            result = self._run_full_pipeline(inputs, state)
        elif state.last_retry_level == RetryLevel.WRITE_ONLY:
            result = self._run_write_retry(inputs, state)
        elif state.last_retry_level == RetryLevel.EDIT_ONLY:
            result = self._run_edit_retry(inputs, state)

        # === 更新状态 ===
        self._update_state_from_result(state, result)

        # === 检查是否通过 ===
        if judge.passed:
            return {...}

        # === Judge 失败，确定下一轮重试级别 ===
        retry_level = determine_retry_level(judge, attempt)
        state.last_retry_level = retry_level

        # 更新 inputs（保留需要的中间结果）
        preserved_inputs = state.to_preserve(retry_level)
        inputs.update(preserved_inputs)

    return {...}
```

### 5.2 三个辅助方法

```python
def _run_full_pipeline(self, inputs, state):
    """运行完整的5个任务"""
    crew = Crew(
        agents=[chapter_planner, chapter_writer, line_editor, critic_judge, continuity_keeper],
        tasks=[plan_task, write_task, edit_task, judge_task, update_bible_task],
        process=Process.sequential
    )
    return crew.kickoff(inputs=inputs)

def _run_write_retry(self, inputs, state):
    """只运行 write + edit + judge + update_bible"""
    crew = Crew(
        agents=[chapter_writer, line_editor, critic_judge, continuity_keeper],
        tasks=[write_task, edit_task, judge_task, update_bible_task],
        process=Process.sequential
    )
    return crew.kickoff(inputs=inputs)

def _run_edit_retry(self, inputs, state):
    """只运行 edit + judge + update_bible"""
    crew = Crew(
        agents=[line_editor, critic_judge, continuity_keeper],
        tasks=[edit_task, judge_task, update_bible_task],
        process=Process.sequential
    )
    return crew.kickoff(inputs=inputs)
```

---

## 6. Task 配置修改

### 6.1 方案选择：通过 inputs 传递中间结果

**理由**：
- 更简单直接，不依赖 CrewAI 内部 API
- Agent 只需从 inputs 读取，无需区分是否重试
- 兼容性好，不易受 CrewAI 版本升级影响

### 6.2 修改 tasks.yaml

**edit_chapter**:
```yaml
description: >
  对第{chapter_number}章进行文风和节奏编辑。

  当前章节：{chapter_number}
  前序任务已生成章节正文，请从上下文中获取。
  StoryBible(public): {story_bible_public}
  StorySpec: {story_spec}
  修订指令（如有）：{revision_instructions}

  # 新增：支持从 inputs 接收已保存的 draft_text
  已保存草稿（如有）：{draft_text_for_edit}

  如果 {draft_text_for_edit} 有值，直接使用它作为编辑对象；
  否则从上下文获取 write_chapter 的输出。
```

**write_chapter**:
```yaml
description: >
  撰写第{chapter_number}章的完整正文。

  当前章节：{chapter_number}
  SceneList: {scene_list}
  已保存场景列表（如有）：{scene_list_for_write}

  如果 {scene_list_for_write} 有值，优先使用它；
  否则使用 {scene_list}。
```

---

## 7. 边界情况处理

### 7.1 SceneList JSON 反序列化失败

```python
def _parse_scene_list_safe(self, scene_list_json: str) -> Optional[SceneList]:
    """安全解析 SceneList，失败则返回 None"""
    try:
        return SceneList.model_validate_json(scene_list_json)
    except Exception as e:
        logger.warning(f"SceneList 解析失败: {e}")
        return None
```

### 7.2 状态恢复失败时的降级策略

```python
# 如果 scene_list 解析失败，降级到 FULL_RETRY
if retry_level == RetryLevel.WRITE_ONLY:
    scene_list = self._parse_scene_list_safe(state.scene_list)
    if scene_list is None:
        logger.warning("SceneList 恢复失败，降级到 FULL_RETRY")
        retry_level = RetryLevel.FULL_RETRY
```

### 7.3 连续相同级别重试的次数限制

```python
MAX_EDIT_RETRIES = 2
MAX_WRITE_RETRIES = 2

if state.last_retry_level == retry_level:
    if retry_level == RetryLevel.EDIT_ONLY and state.edit_retry_count >= MAX_EDIT_RETRIES:
        retry_level = RetryLevel.WRITE_ONLY  # 升级重试级别
```

---

## 8. 测试策略

### 8.1 单元测试

**文件**: `tests/test_retry_level.py`

```python
def test_determine_retry_level_prose_issue():
    judge_report = JudgeReport(
        issues=[Issue(type="prose", severity="medium", note="文笔平淡")]
    )
    level = determine_retry_level(judge_report, attempt=0)
    assert level == RetryLevel.EDIT_ONLY

def test_determine_retry_level_structure_issue():
    judge_report = JudgeReport(
        issues=[Issue(type="structure", severity="high", note="场景顺序不合理")]
    )
    level = determine_retry_level(judge_report, attempt=0)
    assert level == RetryLevel.FULL_RETRY
```

### 8.2 集成测试

**文件**: `tests/test_chapter_crew_retry.py`

```python
def test_edit_only_retry_flow():
    """模拟文笔问题的重试流程"""
    # Mock 第一次运行结果（Judge 不通过，prose 问题）
    # 验证选择了 EDIT_ONLY
    # Mock 第二次运行（只跑 edit + judge）
    # 验证没有重新 plan 和 write

def test_write_only_retry_flow():
    """模拟动机问题的重试流程"""
    # 验证 WRITE_ONLY 保留了 scene_list
    # 验证重新运行了 write + edit + judge
```

### 8.3 端到端测试

- 选择1-2个已完成小说，对比新旧流程的输出质量
- 记录每次重试的级别和耗时
- 验证最终质量没有下降

---

## 9. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|-----|------|-----|---------|
| SceneList JSON 序列化失败 | 低 | 中 | 增加 JSON repair 逻辑；失败时降级到 FULL_RETRY |
| Agent 无法正确理解 inputs 中的中间结果 | 中 | 高 | 在 tasks.yaml 中添加清晰的说明和示例 |
| 状态恢复导致信息丢失 | 低 | 高 | 每次重试前验证必需字段是否完整 |
| CrewAI 版本升级导致兼容性问题 | 中 | 中 | 方案1 已最小化对内部 API 的依赖 |
| 重试级别选择不合理导致死循环 | 低 | 高 | 增加同级别重试次数限制（MAX_EDIT_RETRIES=2） |

---

## 10. 回滚计划

1. **保留原有代码分支**：创建新分支 `selective-retry`
2. **Feature Flag 控制**：通过环境变量 `USE_SELECTIVE_RETRY=true/false` 控制是否启用
3. **渐进式发布**：先在 1-2 个测试小说上验证，再推广到全部
4. **回滚触发条件**：
   - 质量通过率下降超过 5%
   - 新增异常导致流程卡死
   - 节省效果低于 20%

---

## 11. 实施步骤

1. ✅ 创建设计文档
2. ⏳ 提交 git commit（设计文档）
3. ⏳ 创建详细实施计划（使用 `superpowers:writing-plans`）
4. ⏳ 实施代码修改
5. ⏳ 编写单元测试
6. ⏳ 集成测试
7. ⏳ 端到端测试
8. ⏳ 渐进式发布
9. ⏳ 监控和优化

---

## 12. 总结

本设计方案通过三级精细重试机制（EDIT_ONLY、WRITE_ONLY、FULL_RETRY），根据 Judge 报告的问题类型选择性重试部分任务，预期可降低 40-60% 的单章修正成本，同时保证输出质量不下降。

方案已完成详细设计，包括数据结构、状态管理、Task 配置、边界情况处理、测试策略和风险评估，已获批准进入实施阶段。
