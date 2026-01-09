"""Final Assembly Crew for book completion."""
from crewai import Crew, Process, Task
from storycrew.crew import Storycrew
import json
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
        Perform final review and assembly of the complete novel.

        Args:
            book_text: Complete text of all 9 chapters
            story_bible: Final StoryBible state
            story_spec: StorySpec

        Returns:
            Dictionary containing:
                - final_book: Assembled novel with title, intro, TOC, and chapters
                - final_report: Final JudgeReport
                - success: Whether final quality gate was passed
        """
        # Prepare inputs
        inputs = {
            "book_text": book_text,
            "story_bible": json.dumps(story_bible, ensure_ascii=False),
            "story_spec": json.dumps(story_spec, ensure_ascii=False)
        }

        # Create tasks with proper context chaining
        judge_task = self.base_crew.judge_whole_book()
        assemble_task = self.base_crew.assemble_book()

        # Set up context chain
        assemble_task.context = [judge_task]

        # Create sequential crew using proper agent/task methods
        final_crew = Crew(
            agents=[
                self.base_crew.critic_judge(),
                self.base_crew.line_editor()
            ],
            tasks=[judge_task, assemble_task],
            process=Process.sequential,
            verbose=True
        )

        # Execute
        result = final_crew.kickoff(inputs=inputs)

        # Parse CrewOutput to dictionary using the new method
        result_dict = self._parse_crew_output(result)

        # Extract judge_whole_book output
        judge_output = result_dict.get('judge_whole_book_output', {})

        # Extract assemble_book output
        assemble_output = result_dict.get('assemble_book_output', book_text)

        # Parse final report from judge output
        final_report = judge_output if isinstance(judge_output, dict) else {}

        return {
            'final_book': assemble_output,
            'final_report': final_report,
            'success': final_report.get('passed', False) if final_report else False
        }

    def _extract_json_from_output(self, output: str) -> Dict[str, Any]:
        """Extract JSON from LLM output."""
        import sys
        # Import json_repair for robust JSON parsing
        try:
            from json_repair import repair_json
        except ImportError:
            repair_json = None
            print("⚠ Warning: json_repair library not available, using basic parsing", file=sys.stderr)

        import re

        # Try to extract JSON from markdown code blocks (enhanced to tolerate whitespace)
        json_pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(json_pattern, output, re.DOTALL)
        if matches:
            try:
                if repair_json:
                    return json.loads(repair_json(matches[0]))
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Try to extract JSON from plain code blocks (enhanced to tolerate whitespace)
        code_pattern = r'```\s*\n(.*?)\n```'
        matches = re.findall(code_pattern, output, re.DOTALL)
        if matches:
            try:
                if repair_json:
                    return json.loads(repair_json(matches[0]))
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Try to parse as plain JSON
        try:
            if repair_json:
                return json.loads(repair_json(output))
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # Return raw output if no JSON found
        result_dict = {"raw_output": output}

        # Enhanced parsing - use json_repair to handle malformed JSON
        if result_dict.get("raw_output") and repair_json:
            try:
                raw_str = result_dict["raw_output"]
                repaired_json = repair_json(raw_str)
                inner_json = json.loads(repaired_json)

                # If it contains expected keys, use it
                expected_keys = ["is_whole_book", "passed", "plant_payoff_coverage",
                                "theme_delivery", "ending_satisfaction", "issues"]
                if isinstance(inner_json, dict) and any(key in inner_json for key in expected_keys):
                    print(f"✓ Successfully repaired malformed JSON using json_repair", file=sys.stderr)
                    return inner_json
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"⚠ Warning: Failed to parse raw_output JSON even with json_repair: {e}", file=sys.stderr)
                pass

        return result_dict

    def _parse_crew_output(self, crew_output) -> Dict[str, Any]:
        """Parse CrewOutput object to extract results from judge_whole_book and assemble_book tasks.

        Args:
            crew_output: CrewOutput object from crew.kickoff()

        Returns:
            Dictionary with keys:
                - judge_whole_book_output: Dict with judge report
                - assemble_book_output: String with assembled book text
        """
        import sys
        result_dict = {}

        # Handle multiple task outputs
        if hasattr(crew_output, 'tasks_output'):
            outputs = crew_output.tasks_output
            if outputs and len(outputs) > 0:
                # Iterate through all outputs and identify by task properties
                for idx, task_output in enumerate(outputs):
                    # Try to get task description or name from the output
                    task_desc = ""

                    # Check if task_output has metadata about the task
                    if hasattr(task_output, 'description'):
                        task_desc = task_output.description
                    elif hasattr(task_output, 'task') and hasattr(task_output.task, 'description'):
                        task_desc = task_output.task.description

                    # Determine task type from description
                    is_judge_whole_book = '全书质量评审' in task_desc or 'judge_whole_book' in task_desc.lower()
                    is_assemble_book = '最终书籍组装' in task_desc or 'assemble_book' in task_desc.lower()

                    print(f"\n[{idx}] Task description: {task_desc[:80] if task_desc else 'N/A'}...", file=sys.stderr)
                    print(f"  Type: judge={is_judge_whole_book}, assemble={is_assemble_book}", file=sys.stderr)

                    # Extract the actual output value
                    if is_judge_whole_book:
                        # judge_whole_book returns JSON
                        if isinstance(task_output, str):
                            parsed = self._extract_json_from_output(task_output)
                            print(f"  -> judge_whole_book JSON parsed", file=sys.stderr)
                            result_dict['judge_whole_book_output'] = parsed
                        elif hasattr(task_output, 'raw'):
                            parsed = self._extract_json_from_output(str(task_output.raw))
                            print(f"  -> judge_whole_book using .raw", file=sys.stderr)
                            result_dict['judge_whole_book_output'] = parsed
                        elif hasattr(task_output, 'result'):
                            parsed = self._extract_json_from_output(str(task_output.result))
                            print(f"  -> judge_whole_book using .result", file=sys.stderr)
                            result_dict['judge_whole_book_output'] = parsed
                        else:
                            # Fallback: try to extract from string representation
                            parsed = self._extract_json_from_output(str(task_output))
                            result_dict['judge_whole_book_output'] = parsed

                    elif is_assemble_book:
                        # assemble_book returns plain text (assembled book)
                        if isinstance(task_output, str):
                            print(f"  -> assemble_book direct string, length: {len(task_output)}", file=sys.stderr)
                            result_dict['assemble_book_output'] = task_output
                        elif hasattr(task_output, 'raw'):
                            val = str(task_output.raw)
                            print(f"  -> assemble_book using .raw, length: {len(val)}", file=sys.stderr)
                            result_dict['assemble_book_output'] = val
                        elif hasattr(task_output, 'result'):
                            val = str(task_output.result)
                            print(f"  -> assemble_book using .result, length: {len(val)}", file=sys.stderr)
                            result_dict['assemble_book_output'] = val
                        else:
                            val = str(task_output)
                            print(f"  -> assemble_book using str(), length: {len(val)}", file=sys.stderr)
                            result_dict['assemble_book_output'] = val

        # Fallback: Try single task output pattern
        if not result_dict:
            print("\n=== Fallback: Trying single task output pattern ===", file=sys.stderr)
            if hasattr(crew_output, 'raw'):
                result_str = str(crew_output.raw)
                parsed = self._extract_json_from_output(result_str)
                result_dict['judge_whole_book_output'] = parsed
            elif hasattr(crew_output, 'result'):
                result_str = str(crew_output.result)
                parsed = self._extract_json_from_output(result_str)
                result_dict['judge_whole_book_output'] = parsed
            else:
                # Last resort
                result_str = str(crew_output)
                parsed = self._extract_json_from_output(result_str)
                result_dict['judge_whole_book_output'] = parsed

        print(f"\n=== Final parse_crew_output result keys: {list(result_dict.keys())} ===", file=sys.stderr)
        return result_dict

    def _extract_final_report(self, raw_output: str) -> Dict[str, Any]:
        """
        Extract final report from raw LLM output.

        Args:
            raw_output: Raw string output from LLM

        Returns:
            Parsed final report dictionary
        """
        import re

        # Try to extract JSON from markdown code blocks
        json_pattern = r'```json\\n(.*?)\\n```'
        matches = re.findall(json_pattern, raw_output, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Pattern 2: ```...```
        code_pattern = r'```\\n(.*?)\\n```'
        matches = re.findall(code_pattern, raw_output, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Fallback
        return {
            'is_whole_book': True,
            'passed': False,
            'plant_payoff_coverage': 0.0,
            'theme_delivery': 0,
            'ending_satisfaction': 0,
            'issues': [{'type': 'parsing_error', 'severity': 'critical',
                       'note': 'Failed to parse final report'}]
        }
