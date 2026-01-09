"""Initialization Crew for story generation setup."""
from crewai import Crew, Process, Agent, Task
from storycrew.crew import Storycrew
import json
import re
import sys
from typing import Dict, Any


class InitCrew:
    """Crew responsible for initializing story generation (StorySpec, StoryBible, Outline)."""

    def __init__(self):
        self.base_crew = Storycrew()

    def _extract_json_from_output(self, output: str) -> Dict[str, Any]:
        """Extract JSON from LLM output."""
        # Import json_repair for robust JSON parsing
        try:
            from json_repair import repair_json
        except ImportError:
            repair_json = None
            print("⚠ Warning: json_repair library not available, using basic parsing", file=sys.stderr)

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

        # Fix A: Enhanced parsing - use json_repair to handle malformed JSON
        # This handles cases where LLM returns JSON with common formatting errors
        if result_dict.get("raw_output") and repair_json:
            try:
                raw_str = result_dict["raw_output"]

                # Use json_repair to fix common LLM JSON errors:
                # - Unquoted property names (e.g., "prop: value" → '"prop": value')
                # - Trailing commas
                # - Comments in JSON
                # - Missing quotes around string values
                # - Single quotes instead of double quotes
                repaired_json = repair_json(raw_str)
                inner_json = json.loads(repaired_json)

                # If it contains expected keys, use it
                if isinstance(inner_json, dict) and any(key in inner_json for key in ["novel_name", "story_spec", "outline", "plant_payoff_table"]):
                    import sys
                    print(f"✓ Successfully repaired malformed JSON using json_repair", file=sys.stderr)
                    return inner_json
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                # If parsing fails even after repair, return the original result_dict with raw_output
                # Log the error for debugging (but don't crash)
                import sys
                print(f"⚠ Warning: Failed to parse raw_output JSON even with json_repair: {e}", file=sys.stderr)
                pass

        return result_dict

    def _parse_crew_output(self, crew_output) -> Dict[str, Any]:
        """Parse CrewOutput object to extract JSON result."""
        # Convert CrewOutput to string
        if hasattr(crew_output, 'raw'):
            result_str = str(crew_output.raw)
        elif hasattr(crew_output, 'result'):
            result_str = str(crew_output.result)
        elif hasattr(crew_output, 'outputs'):
            # If it's a dict with outputs key
            outputs = crew_output.outputs
            if outputs and len(outputs) > 0:
                result_str = str(list(outputs.values())[0])
            else:
                result_str = str(crew_output)
        else:
            result_str = str(crew_output)

        return self._extract_json_from_output(result_str)

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the initialization phase.

        Args:
            inputs: Dictionary containing:
                - genre: "romance" or "mystery"
                - theme_statement: Core theme of the story
                - additional_preferences: Optional user preferences

        Returns:
            Dictionary containing:
                - story_spec: StorySpec object (as dict)
                - concept: Concept design (as dict)
                - outline: Complete 9-chapter outline (as dict)
                - story_bible: Initialized StoryBible (as dict)
        """
        # Add placeholder values for template variables that agents expect but don't exist yet
        inputs_with_placeholders = {
            **inputs,
            "StorySpec": "{}",  # Will be generated by first task
            "StyleGuide": "{}",  # Will be generated by first task
            "Concept": "{}",  # Will be generated by second task
            "StoryBible": "{}",  # Will be generated by fourth task
            "Outline": "{}",  # Will be generated by third task
            "PlantPayoffTable": "[]",  # Will be generated by third task
        }

        # Get agents
        theme_interpreter = self.base_crew.theme_interpreter()
        concept_designer = self.base_crew.concept_designer()
        plot_architect = self.base_crew.plot_architect()
        continuity_keeper = self.base_crew.continuity_keeper()

        # Task 1: Build StorySpec
        build_story_spec_task = Task(
            description=self.base_crew.tasks_config['build_story_spec']['description'],
            expected_output=self.base_crew.tasks_config['build_story_spec']['expected_output'],
            agent=theme_interpreter,
            callback=lambda output: self._extract_json_from_output(output) if isinstance(output, str) else output
        )

        crew1 = Crew(
            agents=[theme_interpreter],
            tasks=[build_story_spec_task],
            verbose=True
        )

        story_spec_result = crew1.kickoff(inputs=inputs_with_placeholders)
        story_spec_dict = self._parse_crew_output(story_spec_result)

        # Prepare inputs for next task
        # Note: need both lowercase (for tasks) and capitalized (for agents) versions
        inputs_2 = {
            **inputs,
            "story_spec": json.dumps(story_spec_dict.get("story_spec", story_spec_dict), ensure_ascii=False),
            "StorySpec": json.dumps(story_spec_dict.get("story_spec", story_spec_dict), ensure_ascii=False),
            "StyleGuide": json.dumps(story_spec_dict.get("story_spec", story_spec_dict).get("style", {}), ensure_ascii=False)
        }

        # Task 2: Build Concept
        build_concept_task = Task(
            description=self.base_crew.tasks_config['build_concept']['description'],
            expected_output=self.base_crew.tasks_config['build_concept']['expected_output'],
            agent=concept_designer
        )

        crew2 = Crew(
            agents=[concept_designer],
            tasks=[build_concept_task],
            verbose=True
        )

        concept_result = crew2.kickoff(inputs=inputs_2)
        concept_dict = self._parse_crew_output(concept_result)

        # Prepare inputs for next task
        inputs_3 = {
            **inputs_2,
            "concept": json.dumps(concept_dict, ensure_ascii=False),
            "Concept": json.dumps(concept_dict, ensure_ascii=False)
        }

        # Task 3: Build Outline
        build_outline_task = Task(
            description=self.base_crew.tasks_config['build_outline']['description'],
            expected_output=self.base_crew.tasks_config['build_outline']['expected_output'],
            agent=plot_architect
        )

        crew3 = Crew(
            agents=[plot_architect],
            tasks=[build_outline_task],
            verbose=True
        )

        outline_result = crew3.kickoff(inputs=inputs_3)
        outline_dict = self._parse_crew_output(outline_result)

        # Prepare inputs for next task
        # Optimize: Only pass data that init_bible actually needs
        # init_bible requires: plant_payoff_table and truth_card (for mystery)
        # It does NOT need the full outline with all chapter details
        outline_for_bible = {
            'plant_payoff_table': outline_dict.get('plant_payoff_table', []),
            'truth_card': outline_dict.get('truth_card')
        }

        inputs_4 = {
            **inputs_3,
            "outline": json.dumps(outline_for_bible, ensure_ascii=False),
            "Outline": json.dumps(outline_for_bible, ensure_ascii=False),
            "PlantPayoffTable": json.dumps(outline_dict.get("plant_payoff_table", []), ensure_ascii=False)
        }

        # Task 4: Initialize Bible
        init_bible_task = Task(
            description=self.base_crew.tasks_config['init_bible']['description'],
            expected_output=self.base_crew.tasks_config['init_bible']['expected_output'],
            agent=continuity_keeper
        )

        crew4 = Crew(
            agents=[continuity_keeper],
            tasks=[init_bible_task],
            verbose=True
        )

        bible_result = crew4.kickoff(inputs=inputs_4)
        bible_dict = self._parse_crew_output(bible_result)

        # Combine all results
        return {
            "novel_name": story_spec_dict.get("novel_name", "未命名小说"),
            "story_spec": story_spec_dict.get("story_spec", story_spec_dict),
            "concept": concept_dict,
            "outline": outline_dict,
            "story_bible": bible_dict,
            "StoryBible": bible_dict  # Capitalized version for agents
        }
