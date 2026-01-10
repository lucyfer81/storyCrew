"""Chapter Generation Crew for writing individual chapters."""
from crewai import Crew, Process, Task
from storycrew.crew import Storycrew
from typing import Dict, Any, Optional


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
        # Prepare inputs - convert Pydantic objects to dicts for CrewAI
        inputs = {
            "chapter_number": chapter_number,
            "chapter_outline": chapter_outline.model_dump() if hasattr(chapter_outline, 'model_dump') else chapter_outline,
            "scene_list": "",  # Placeholder for plan_chapter to generate
            "story_bible": story_bible.model_dump() if hasattr(story_bible, 'model_dump') else story_bible,
            "story_spec": story_spec.model_dump() if hasattr(story_spec, 'model_dump') else story_spec,
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

        update_bible_task = self.base_crew.update_bible()
        update_bible_task.agent = continuity_keeper
        update_bible_task.context = [plan_task, write_task]

        edit_task = self.base_crew.edit_chapter()
        edit_task.agent = line_editor
        edit_task.context = [plan_task, write_task, update_bible_task]

        judge_task = self.base_crew.judge_chapter()
        judge_task.agent = critic_judge
        judge_task.context = [plan_task, write_task, update_bible_task, edit_task]

        # Create sequential crew
        chapter_crew = Crew(
            agents=[
                chapter_planner,
                chapter_writer,
                continuity_keeper,
                line_editor,
                critic_judge
            ],
            tasks=[plan_task, write_task, update_bible_task, edit_task, judge_task],
            process=Process.sequential,
            verbose=True
        )

        # Execute with retry logic
        for attempt in range(self.max_retries + 1):
            result = chapter_crew.kickoff(inputs=inputs)

            # Direct access to Pydantic objects
            scene_list = result.tasks_output[0].pydantic  # SceneList
            draft = result.tasks_output[1].pydantic  # ChapterDraft
            updated_bible = result.tasks_output[2].pydantic  # StoryBible
            revision = result.tasks_output[3].pydantic  # ChapterRevision
            judge = result.tasks_output[4].pydantic  # JudgeReport

            # Check if passed quality gate
            if judge.passed:
                return {
                    'chapter_text': revision.revised_text,
                    'updated_bible': updated_bible,
                    'judge_report': judge,
                    'attempts': attempt + 1
                }

            # Failed - prepare for retry
            if attempt < self.max_retries:
                # Update revision instructions for next attempt
                inputs["revision_instructions"] = "\n".join(judge.revision_instructions)

        # All retries exhausted
        return {
            'chapter_text': revision.revised_text,
            'updated_bible': updated_bible,
            'judge_report': judge,
            'attempts': self.max_retries + 1,
            'success': False
        }
