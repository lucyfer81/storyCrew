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
