"""Chapter Generation Crew for writing individual chapters."""
import logging
from crewai import Crew, Process, Task
from storycrew.crew import Storycrew
from typing import Dict, Any, Optional
from copy import deepcopy

logger = logging.getLogger("StoryCrew")


class ChapterCrew:
    """Crew responsible for generating a single chapter with quality gates."""

    def __init__(self):
        self.base_crew = Storycrew()
        self.max_retries = 2

    def generate_chapter(
        self,
        chapter_number: int,
        chapter_outline: Dict[str, Any],
        story_bible: Dict[str, Any],
        story_spec: Dict[str, Any],
        revision_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single chapter with structured outputs and automatic retry.

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
        # For mystery genre, StoryBible may contain truth_card (final truth).
        # To avoid accidental leakage, we pass a "public" StoryBible (truth_card removed)
        # to chapter_planner / chapter_writer / line_editor.
        #
        # NOTE: As requested, we KEEP current behavior for critic_judge:
        # critic_judge continues to see the full StoryBible (including truth_card).
        story_bible_dict = story_bible.model_dump() if hasattr(story_bible, 'model_dump') else story_bible
        story_spec_dict = story_spec.model_dump() if hasattr(story_spec, 'model_dump') else story_spec

        story_bible_public = deepcopy(story_bible_dict)
        if isinstance(story_bible_public, dict) and "truth_card" in story_bible_public:
            story_bible_public.pop("truth_card", None)

        # Prepare inputs - convert Pydantic objects to dicts for CrewAI
        inputs = {
            "chapter_number": chapter_number,
            "chapter_outline": chapter_outline.model_dump() if hasattr(chapter_outline, 'model_dump') else chapter_outline,
            "scene_list": "",  # Placeholder for plan_chapter to generate
            "story_bible_public": story_bible_public,  # For planner/writer/editor
            "story_bible_full": story_bible_dict,      # For update_bible/judge
            "story_spec": story_spec_dict,
            "revision_instructions": revision_instructions or "",
        }

        # Get agents
        chapter_planner = self.base_crew.chapter_planner()
        chapter_writer = self.base_crew.chapter_writer()
        continuity_keeper = self.base_crew.continuity_keeper()
        line_editor = self.base_crew.line_editor()
        critic_judge = self.base_crew.critic_judge()

        # Create tasks using pre-configured tasks from base_crew
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

        # Create sequential crew
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

        # Execute with retry logic for both quality gates AND exceptions
        for attempt in range(self.max_retries + 1):
            try:
                result = chapter_crew.kickoff(inputs=inputs)

                # Access task outputs - mixed Pydantic and raw text outputs
                scene_list = result.tasks_output[0].pydantic  # SceneList (structured output)

                # write_chapter now returns plain text (no Pydantic wrapping)
                write_output = result.tasks_output[1]
                if hasattr(write_output, 'raw'):
                    draft_text = str(write_output.raw)
                elif hasattr(write_output, 'pydantic'):
                    # Fallback: if still has pydantic, extract raw_text field
                    draft_text = write_output.pydantic.raw_text
                else:
                    # Last resort: convert to string
                    draft_text = str(write_output)
                # Calculate word_count from actual text
                word_count = len(draft_text)

                # edit_chapter now returns plain text (no Pydantic wrapping)
                edit_output = result.tasks_output[2]
                if hasattr(edit_output, 'raw'):
                    revision_text = str(edit_output.raw)
                elif hasattr(edit_output, 'pydantic'):
                    # Fallback: if still has pydantic, extract revised_text field
                    revision_text = edit_output.pydantic.revised_text
                else:
                    # Last resort: convert to string
                    revision_text = str(edit_output)
                # Calculate word_count from actual text
                revision_word_count = len(revision_text)

                judge = result.tasks_output[3].pydantic  # JudgeReport (structured output)

                updated_bible = result.tasks_output[4].pydantic  # StoryBible (structured output)

                # Check if passed quality gate
                if judge.passed:
                    return {
                        'chapter_text': revision_text,  # Use extracted plain text
                        'updated_bible': updated_bible,
                        'judge_report': judge,
                        'attempts': attempt + 1
                    }

                # Failed quality gate - prepare for retry
                if attempt < self.max_retries:
                    # Update revision instructions for next attempt
                    inputs["revision_instructions"] = "\n".join(judge.revision_instructions)

            except Exception as e:
                # Exception during generation (timeout, validation error, etc.)
                error_type = type(e).__name__
                error_msg = str(e)

                # If this is the last attempt or a critical error, re-raise to main.py
                if attempt >= self.max_retries:
                    logger.error(f"Chapter {chapter_number} failed after {attempt + 1} attempts: {error_type}: {error_msg[:100]}")
                    raise

                # Log and retry
                logger.warning(f"Chapter {chapter_number} attempt {attempt + 1} failed with {error_type}: {error_msg[:100]}, retrying...")
                # Clear revision instructions for clean retry
                inputs["revision_instructions"] = ""
                # Continue to next iteration of retry loop
                continue

        # All retries exhausted
        return {
            'chapter_text': revision_text,  # Use extracted plain text
            'updated_bible': updated_bible,
            'judge_report': judge,
            'attempts': self.max_retries + 1,
            'success': False
        }
