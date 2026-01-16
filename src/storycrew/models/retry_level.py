"""Retry level models for selective chapter generation retry."""
from enum import Enum
from typing import Set, List, Optional

from storycrew.models.judge_report import JudgeReport, Issue


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
