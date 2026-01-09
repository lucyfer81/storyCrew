"""Chapter Generation Crew for writing individual chapters."""
from crewai import Crew, Process, Agent, Task
from storycrew.crew import Storycrew
import json
from typing import Dict, Any, Optional


class ChapterCrew:
    """Crew responsible for generating a single chapter with quality gates."""

    def __init__(self):
        self.base_crew = Storycrew()
        self.max_retries = 2

    def _extract_json_from_output(self, output: str) -> Dict[str, Any]:
        """Extract JSON from LLM output (handles markdown code blocks)."""
        import re

        # Pattern 1: ```json...```
        json_pattern = r'```json\n(.*?)\n```'
        matches = re.findall(json_pattern, output, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Pattern 2: ```...```
        code_pattern = r'```\n(.*?)\n```'
        matches = re.findall(code_pattern, output, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Pattern 3: Find JSON object
        json_obj_pattern = r'\{[^{}]*\{.*\}[^{}]*\}|\{.*\}'
        matches = re.findall(json_obj_pattern, output, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                pass

        # Return raw output if no JSON found
        return {"raw_output": output}

    def _parse_crew_output(self, crew_output) -> Dict[str, Any]:
        """Parse CrewOutput object to extract JSON result from all tasks.

        KEY FIX: Don't rely on task names as keys - use task descriptions to identify tasks.
        CrewAI uses UUIDs or other identifiers as keys, not task names.
        """
        import sys
        # DEBUG: Method entry
        print(f"\n=== _parse_crew_output CALLED ===", file=sys.stderr)
        print(f"crew_output type: {type(crew_output)}", file=sys.stderr)
        print(f"hasattr(crew_output, 'tasks_output'): {hasattr(crew_output, 'tasks_output')}", file=sys.stderr)
        if hasattr(crew_output, 'tasks_output'):
            print(f"tasks_output: {crew_output.tasks_output}", file=sys.stderr)

        # Handle multiple task outputs - this is the key fix for empty chapter files
        if hasattr(crew_output, 'tasks_output'):
            outputs = crew_output.tasks_output
            # DEBUG: Log outputs structure
            print(f"\n=== DEBUG _parse_crew_output ===", file=sys.stderr)
            print(f"outputs type: {type(outputs)}", file=sys.stderr)
            print(f"outputs length: {len(outputs) if outputs else 0}", file=sys.stderr)
            if outputs and len(outputs) > 0:
                result_dict = {}

                # NEW APPROACH: Iterate through all outputs and identify by task properties
                for idx, task_output in enumerate(outputs):
                    # Try to get task description or name from the output
                    task_desc = ""

                    # Check if task_output has metadata about the task
                    if hasattr(task_output, 'description'):
                        task_desc = task_output.description
                    elif hasattr(task_output, 'task') and hasattr(task_output.task, 'description'):
                        task_desc = task_output.task.description

                    # Determine task type from description
                    is_edit_chapter = '文风和节奏编辑' in task_desc or 'edit_chapter' in task_desc.lower()
                    is_write_chapter = '分章正文撰写' in task_desc or 'write_chapter' in task_desc.lower()
                    is_judge_chapter = '质量评审' in task_desc or 'judge_chapter' in task_desc.lower()
                    is_update_bible = '连续性与事实库' in task_desc or 'update_bible' in task_desc.lower()
                    is_plan_chapter = '场景规划' in task_desc or 'plan_chapter' in task_desc.lower()

                    # DEBUG
                    print(f"\n[{idx}] Task description: {task_desc[:80] if task_desc else 'N/A'}...", file=sys.stderr)
                    print(f"  Type: edit={is_edit_chapter}, write={is_write_chapter}, judge={is_judge_chapter}, update={is_update_bible}, plan={is_plan_chapter}", file=sys.stderr)

                    # Extract the actual output value
                    try:
                        # Special handling: edit_chapter returns plain text, not JSON
                        if is_edit_chapter:
                            if isinstance(task_output, str):
                                print(f"  -> Direct string, length: {len(task_output)}", file=sys.stderr)
                                result_dict['edit_chapter_output'] = task_output
                            elif hasattr(task_output, 'raw'):
                                val = str(task_output.raw)
                                print(f"  -> Using .raw, length: {len(val)}", file=sys.stderr)
                                result_dict['edit_chapter_output'] = val
                            elif hasattr(task_output, 'result'):
                                val = str(task_output.result)
                                print(f"  -> Using .result, length: {len(val)}", file=sys.stderr)
                                result_dict['edit_chapter_output'] = val
                            elif hasattr(task_output, 'description'):
                                val = str(task_output.description)
                                print(f"  -> Using .description, length: {len(val)}", file=sys.stderr)
                                result_dict['edit_chapter_output'] = val
                            else:
                                val = str(task_output)
                                print(f"  -> Using str(), length: {len(val)}", file=sys.stderr)
                                result_dict['edit_chapter_output'] = val

                        # Handle write_chapter (returns JSON with raw_output field)
                        elif is_write_chapter:
                            if isinstance(task_output, str):
                                parsed = self._extract_json_from_output(task_output)
                                print(f"  -> write_chapter JSON parsed", file=sys.stderr)
                                result_dict['write_chapter_output'] = parsed
                            elif hasattr(task_output, 'raw'):
                                parsed = self._extract_json_from_output(str(task_output.raw))
                                print(f"  -> write_chapter using .raw", file=sys.stderr)
                                result_dict['write_chapter_output'] = parsed
                            else:
                                result_dict['write_chapter_output'] = task_output

                        # Handle judge_chapter (returns JSON)
                        elif is_judge_chapter:
                            if isinstance(task_output, str):
                                parsed = self._extract_json_from_output(task_output)
                                print(f"  -> judge_chapter JSON parsed", file=sys.stderr)
                                result_dict['judge_chapter_output'] = parsed
                            elif hasattr(task_output, 'raw'):
                                parsed = self._extract_json_from_output(str(task_output.raw))
                                print(f"  -> judge_chapter using .raw", file=sys.stderr)
                                result_dict['judge_chapter_output'] = parsed
                            else:
                                result_dict['judge_chapter_output'] = task_output

                        # Handle update_bible (returns JSON)
                        elif is_update_bible:
                            if isinstance(task_output, str):
                                parsed = self._extract_json_from_output(task_output)
                                print(f"  -> update_bible JSON parsed", file=sys.stderr)
                                result_dict['update_bible_output'] = parsed
                            elif hasattr(task_output, 'raw'):
                                parsed = self._extract_json_from_output(str(task_output.raw))
                                print(f"  -> update_bible using .raw", file=sys.stderr)
                                result_dict['update_bible_output'] = parsed
                            else:
                                result_dict['update_bible_output'] = task_output

                        # Handle plan_chapter (returns JSON)
                        elif is_plan_chapter:
                            if isinstance(task_output, str):
                                parsed = self._extract_json_from_output(task_output)
                                print(f"  -> plan_chapter JSON parsed", file=sys.stderr)
                                result_dict['plan_chapter_output'] = parsed
                            elif hasattr(task_output, 'raw'):
                                parsed = self._extract_json_from_output(str(task_output.raw))
                                print(f"  -> plan_chapter using .raw", file=sys.stderr)
                                result_dict['plan_chapter_output'] = parsed
                            else:
                                result_dict['plan_chapter_output'] = task_output

                        # Default: treat as JSON for unknown tasks
                        else:
                            if isinstance(task_output, str):
                                result_dict[f'task_{idx}_output'] = self._extract_json_from_output(task_output)
                            elif hasattr(task_output, 'raw'):
                                result_dict[f'task_{idx}_output'] = self._extract_json_from_output(str(task_output.raw))
                            else:
                                result_dict[f'task_{idx}_output'] = task_output

                    except Exception as e:
                        print(f"  ERROR: {e}", file=sys.stderr)
                        result_dict[f'task_{idx}_output'] = {'raw_output': str(task_output), 'parse_error': str(e)}

                return result_dict
            else:
                # Fallback to single output parsing
                return self._extract_json_from_output(str(crew_output))
        elif hasattr(crew_output, 'raw'):
            return self._extract_json_from_output(str(crew_output.raw))
        elif hasattr(crew_output, 'result'):
            return self._extract_json_from_output(str(crew_output.result))
        else:
            return self._extract_json_from_output(str(crew_output))

    def generate_chapter(
        self,
        chapter_number: int,
        chapter_outline: Dict[str, Any],
        story_bible: Dict[str, Any],
        story_spec: Dict[str, Any],
        revision_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single chapter with quality gate and retry logic.

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
        # Prepare inputs for task chain
        inputs = {
            "chapter_number": chapter_number,
            "chapter_outline": json.dumps(chapter_outline, ensure_ascii=False),
            "scene_list": "",  # Placeholder for plan_chapter to generate
            "story_bible": json.dumps(story_bible, ensure_ascii=False),
            "story_spec": json.dumps(story_spec, ensure_ascii=False),
            "revision_instructions": revision_instructions or ""
        }

        # Create tasks with proper context chaining
        plan_task = self.base_crew.plan_chapter()
        write_task = self.base_crew.write_chapter()
        update_bible_task = self.base_crew.update_bible()
        edit_task = self.base_crew.edit_chapter()
        judge_task = self.base_crew.judge_chapter()

        # Set up context chain
        write_task.context = [plan_task]
        update_bible_task.context = [plan_task, write_task]
        edit_task.context = [plan_task, write_task, update_bible_task]
        judge_task.context = [plan_task, write_task, update_bible_task, edit_task]

        # Create sequential crew using proper agent/task methods
        chapter_crew = Crew(
            agents=[
                self.base_crew.chapter_planner(),
                self.base_crew.chapter_writer(),
                self.base_crew.continuity_keeper(),
                self.base_crew.line_editor(),
                self.base_crew.critic_judge()
            ],
            tasks=[plan_task, write_task, update_bible_task, edit_task, judge_task],
            process=Process.sequential,
            verbose=True
        )

        # Execute with retry logic
        for attempt in range(self.max_retries + 1):
            import sys
            print(f"\n=== generate_chapter: Attempt {attempt + 1} ===", file=sys.stderr)
            result = chapter_crew.kickoff(inputs=inputs)
            print(f"Result type: {type(result)}", file=sys.stderr)
            print(f"Calling _parse_crew_output...", file=sys.stderr)

            # Parse CrewOutput to dictionary
            result_dict = self._parse_crew_output(result)
            print(f"result_dict keys: {list(result_dict.keys())}", file=sys.stderr)

            # Fallback: if key outputs are missing, try to extract from raw CrewOutput
            # Don't rely on task names as keys - iterate and identify by description
            if 'edit_chapter_output' not in result_dict or not result_dict.get('edit_chapter_output'):
                if hasattr(result, 'tasks_output'):
                    outputs = result.tasks_output
                    # Iterate through all outputs to find edit_chapter by description
                    for task_output in outputs:
                        # Get task description
                        task_desc = ""
                        if hasattr(task_output, 'description'):
                            task_desc = task_output.description
                        elif hasattr(task_output, 'task') and hasattr(task_output.task, 'description'):
                            task_desc = task_output.task.description

                        # Check if this is edit_chapter
                        if '文风和节奏编辑' in task_desc or 'edit_chapter' in task_desc.lower():
                            # Found it! Extract the text
                            if isinstance(task_output, str):
                                result_dict['edit_chapter_output'] = task_output
                            elif hasattr(task_output, 'raw'):
                                result_dict['edit_chapter_output'] = str(task_output.raw)
                            elif hasattr(task_output, 'result'):
                                result_dict['edit_chapter_output'] = str(task_output.result)
                            elif hasattr(task_output, 'description'):
                                result_dict['edit_chapter_output'] = str(task_output.description)
                            else:
                                result_dict['edit_chapter_output'] = str(task_output)
                            break

                    # If still no edit_chapter, fallback to write_chapter
                    if not result_dict.get('edit_chapter_output'):
                        for task_output in outputs:
                            task_desc = ""
                            if hasattr(task_output, 'description'):
                                task_desc = task_output.description
                            elif hasattr(task_output, 'task') and hasattr(task_output.task, 'description'):
                                task_desc = task_output.task.description

                            if '分章正文撰写' in task_desc or 'write_chapter' in task_desc.lower():
                                # Handle write_chapter output
                                if isinstance(task_output, str):
                                    write_output = task_output
                                elif hasattr(task_output, 'raw'):
                                    write_output = str(task_output.raw)
                                elif hasattr(task_output, 'result'):
                                    write_output = str(task_output.result)
                                else:
                                    write_output = str(task_output)

                                # Extract text from JSON if wrapped
                                if write_output.startswith('{'):
                                    try:
                                        parsed = json.loads(write_output)
                                        result_dict['edit_chapter_output'] = parsed.get('raw_output', write_output)
                                    except:
                                        result_dict['edit_chapter_output'] = write_output
                                else:
                                    result_dict['edit_chapter_output'] = write_output
                                break

            # Ensure update_bible_output exists - use description-based identification
            if 'update_bible_output' not in result_dict:
                if hasattr(result, 'tasks_output'):
                    outputs = result.tasks_output
                    found = False
                    for task_output in outputs:
                        task_desc = ""
                        if hasattr(task_output, 'description'):
                            task_desc = task_output.description
                        elif hasattr(task_output, 'task') and hasattr(task_output.task, 'description'):
                            task_desc = task_output.task.description

                        if '连续性与事实库' in task_desc or 'update_bible' in task_desc.lower():
                            result_dict['update_bible_output'] = self._extract_json_from_output(str(task_output))
                            found = True
                            break
                    if not found:
                        result_dict['update_bible_output'] = story_bible
                else:
                    result_dict['update_bible_output'] = story_bible

            # Parse judge report
            try:
                judge_report_raw = result_dict.get('judge_chapter_output', '') or result_dict
                judge_report = json.loads(judge_report_raw) if isinstance(judge_report_raw, str) else judge_report_raw
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, extract from raw result
                judge_report = self._extract_judge_report(str(result_dict))

            # Check if passed
            if judge_report.get('passed', False):
                # Ensure chapter_text is always a string, extract from dict if needed
                chapter_text_output = result_dict.get('edit_chapter_output', '')
                if isinstance(chapter_text_output, dict) and 'raw_output' in chapter_text_output:
                    chapter_text_output = chapter_text_output['raw_output']
                elif not isinstance(chapter_text_output, str):
                    chapter_text_output = str(chapter_text_output)

                return {
                    'chapter_text': chapter_text_output,
                    'updated_bible': result_dict.get('update_bible_output', story_bible),
                    'judge_report': judge_report,
                    'attempts': attempt + 1
                }

            # Failed - prepare for retry
            if attempt < self.max_retries:
                # Determine revision strategy
                issues = judge_report.get('issues', [])
                revision_instructions_list = judge_report.get('revision_instructions', [])

                # Check if issues are structural or stylistic
                has_structural_issues = any(
                    issue.get('type') in ['structure', 'motivation', 'clue_fairness']
                    for issue in issues
                )

                if has_structural_issues:
                    # Rewrite from chapter writer level
                    inputs['revision_instructions'] = '\\n'.join(revision_instructions_list)
                    # Reset tasks for rewrite
                    write_task.context = [plan_task]
                else:
                    # Edit level (already covered by edit_task)
                    inputs['revision_instructions'] = '\\n'.join(revision_instructions_list)

        # All retries exhausted
        return {
            'chapter_text': result_dict.get('edit_chapter_output', ''),
            'updated_bible': result_dict.get('update_bible_output', story_bible),
            'judge_report': judge_report,
            'attempts': self.max_retries + 1,
            'success': False
        }

    def _extract_judge_report(self, raw_output: str) -> Dict[str, Any]:
        """
        Extract judge report from raw LLM output.

        Args:
            raw_output: Raw string output from LLM

        Returns:
            Parsed JudgeReport dictionary
        """
        # Try to extract JSON from markdown code blocks
        import re

        # Pattern 1: ```json...```
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

        # Pattern 3: Find JSON object
        json_obj_pattern = r'\\{[^{}]*\\{.*\\}[^{}]*\\}|\\{.*\\}'
        matches = re.findall(json_obj_pattern, raw_output, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                pass

        # Fallback: return minimal report
        return {
            'passed': False,
            'scores': {'continuity': 0, 'pacing': 0, 'character_motivation': 0,
                      'genre_fulfillment': 0, 'prose': 0, 'hook': 0},
            'hard_fail': {'safety_pass': True, 'continuity_conflicts': [],
                         'word_count_in_range': False},
            'issues': [{'type': 'parsing_error', 'severity': 'critical',
                       'note': 'Failed to parse judge report'}],
            'revision_instructions': ['Manual review required']
        }
