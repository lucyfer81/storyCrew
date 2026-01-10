"""Final Assembly Crew for book completion."""
from crewai import Crew, Process, Task
from storycrew.crew import Storycrew
from typing import Dict, Any


class FinalCrew:
    """Crew responsible for final review and assembly of the complete novel."""

    def __init__(self):
        self.base_crew = Storycrew()

    def finalize_book(
        self,
        book_text: str,
        story_bible: Dict[str, Any],
        story_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform final review and assembly with structured outputs.

        Args:
            book_text: Complete text of all 9 chapters
            story_bible: Final StoryBible state
            story_spec: StorySpec

        Returns:
            Dictionary containing:
                - final_book: FinalBook object
                - final_report: Final JudgeReport
                - success: Whether final quality gate was passed
        """
        # Prepare inputs - convert Pydantic objects to dicts for CrewAI
        inputs = {
            "book_text": book_text,
            "story_bible": story_bible.model_dump() if hasattr(story_bible, 'model_dump') else story_bible,
            "story_spec": story_spec.model_dump() if hasattr(story_spec, 'model_dump') else story_spec,
        }

        # Get agents
        critic_judge = self.base_crew.critic_judge()
        line_editor = self.base_crew.line_editor()

        # Create tasks using pre-configured tasks from base_crew
        judge_task = self.base_crew.judge_whole_book()
        judge_task.agent = critic_judge

        assemble_task = self.base_crew.assemble_book()
        assemble_task.agent = line_editor
        assemble_task.context = [judge_task]

        # Create sequential crew
        final_crew = Crew(
            agents=[
                critic_judge,
                line_editor
            ],
            tasks=[judge_task, assemble_task],
            process=Process.sequential,
            verbose=True
        )

        # Execute
        result = final_crew.kickoff(inputs=inputs)

        # Direct access to Pydantic objects
        final_report = result.tasks_output[0].pydantic  # JudgeReport
        final_book = result.tasks_output[1].pydantic  # FinalBook

        return {
            'final_book': final_book,
            'final_report': final_report,
            'success': final_report.passed
        }
