"""Chapter Generation Crew for writing individual chapters."""
import logging
from crewai import Crew, Process, Task
from storycrew.crew import Storycrew
from typing import Dict, Any, Optional
from copy import deepcopy
from storycrew.models import (
    SceneList, ChapterDraft, ChapterRevision, JudgeReport,
    ChapterGenerationState, RetryLevel, determine_retry_level
)

logger = logging.getLogger("StoryCrew")

# Retry level limits
MAX_EDIT_RETRIES = 2
MAX_WRITE_RETRIES = 2


class ChapterCrew:
    """Crew responsible for generating a single chapter with quality gates."""

    def __init__(self):
        self.base_crew = Storycrew()
        self.max_retries = 2

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
        if state.current_attempt == 0 or state.last_retry_level in (None, RetryLevel.FULL_RETRY.value):
            # FULL_RETRY 或第一次：有 5 个输出
            if len(outputs) >= 5:
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
            if len(outputs) >= 4:
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
            if len(outputs) >= 3:
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
                            logger.warning("SceneList recovery failed, falling back to FULL_RETRY")
                            state.last_retry_level = RetryLevel.FULL_RETRY.value
                            result = self._run_full_pipeline(inputs, state)
                        else:
                            result = self._run_write_retry(inputs, state)
                    else:
                        logger.warning("scene_list missing, falling back to FULL_RETRY")
                        state.last_retry_level = RetryLevel.FULL_RETRY.value
                        result = self._run_full_pipeline(inputs, state)

                elif state.last_retry_level == RetryLevel.EDIT_ONLY.value:
                    result = self._run_edit_retry(inputs, state)

                else:
                    # Unknown retry level, default to full
                    logger.warning(f"Unknown retry level {state.last_retry_level}, using FULL_RETRY")
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
                elif retry_level == RetryLevel.WRITE_ONLY and state.last_retry_level == RetryLevel.WRITE_ONLY.value:
                    state.write_retry_count += 1
                    if state.write_retry_count >= MAX_WRITE_RETRIES:
                        logger.warning(f"WRITE_ONLY retry count reached max ({MAX_WRITE_RETRIES}), escalating to FULL_RETRY")
                        retry_level = RetryLevel.FULL_RETRY
                        state.write_retry_count = 0
                else:
                    # 重置计数器
                    state.edit_retry_count = 0
                    state.write_retry_count = 0

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
