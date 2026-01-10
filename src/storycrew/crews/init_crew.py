"""Initialization Crew for story generation setup."""
from crewai import Crew, Process, Agent, Task
from storycrew.crew import Storycrew, repair_json
from storycrew.models import StorySpecWithResult, Concept
from typing import Dict, Any
import logging
import json

logger = logging.getLogger("StoryCrew")


def sanitize_concept_json(json_str: str) -> str:
    """
    Fix common LLM errors in Concept generation.

    Fixes the case where forbidden_phrases array is accidentally nested
    inside secrets array, causing Pydantic validation errors.

    Args:
        json_str: The JSON string to sanitize

    Returns:
        Sanitized JSON string
    """
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return json_str  # If not valid JSON, return as-is

    # Fix characters.secrets - flatten nested lists that shouldn't be there
    if 'characters' in data and isinstance(data['characters'], list):
        for char in data['characters']:
            if isinstance(char, dict) and 'secrets' in char:
                secrets = char['secrets']
                if isinstance(secrets, list):
                    sanitized_secrets = []
                    for item in secrets:
                        if isinstance(item, str):
                            sanitized_secrets.append(item)
                        elif isinstance(item, list):
                            # Convert nested list to comma-separated string
                            # This fixes the LLM error where forbidden_phrases gets nested in secrets
                            sanitized_secrets.append(", ".join(str(x) for x in item))
                        else:
                            # Fallback: convert to string
                            sanitized_secrets.append(str(item))
                    char['secrets'] = sanitized_secrets

    return json.dumps(data, ensure_ascii=False)

# Monkey-patch CrewAI's converter to apply JSON repairs
import crewai.utilities.converter as converter_module
_original_handle_partial_json = converter_module.handle_partial_json

def _patched_handle_partial_json(result: str, model: type, is_json_output: bool = False,
                                 agent=None, converter_cls=None):
    """Wrapper that applies JSON repairs before CrewAI parses.

    Args:
        result: The raw LLM output string
        model: The Pydantic model to validate against
        is_json_output: Whether this is JSON output mode
        agent: The agent instance (unused but passed by CrewAI)
        converter_cls: The converter class (unused but passed by CrewAI)

    Returns:
        Validated Pydantic model instance
    """
    # Apply Concept-specific sanitization for nested list bug
    working_result = result
    if model == Concept:
        working_result = sanitize_concept_json(str(result))
        if working_result != str(result):
            logger.info("[CONCEPT SANITIZE] Applied Concept-specific sanitization for nested list bug")

    try:
        # Try original parsing first
        return _original_handle_partial_json(working_result, model, is_json_output, agent, converter_cls)
    except Exception as e:
        # If parsing fails, try to repair and retry
        logger.info(f"[JSON REPAIR] Parse failed, attempting repair. Error: {str(e)[:100]}")
        logger.info(f"[JSON REPAIR] Original output (first 200 chars): {str(working_result)[:200]}")

        # Apply repairs
        repaired = repair_json(str(working_result))

        # For Concept model, apply sanitization again after repair
        if model == Concept:
            repaired = sanitize_concept_json(repaired)

        if repaired != str(working_result):
            logger.info(f"[JSON REPAIR] Repaired output (first 200 chars): {repaired[:200]}")
            # Retry with repaired JSON
            return _original_handle_partial_json(repaired, model, is_json_output, agent, converter_cls)
        else:
            logger.info("[JSON REPAIR] No repairs applied, re-raising original error")
            raise

# Apply the monkey-patch
converter_module.handle_partial_json = _patched_handle_partial_json
logger.info("[JSON REPAIR] Monkey-patch applied to CrewAI converter")


class InitCrew:
    """Crew responsible for initializing story generation (StorySpec, StoryBible, Outline)."""

    def __init__(self):
        self.base_crew = Storycrew()

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the initialization phase with structured outputs.

        Args:
            inputs: Dictionary containing:
                - genre: "romance" or "mystery"
                - theme_statement: Core theme of the story
                - additional_preferences: Optional user preferences

        Returns:
            Dictionary containing:
                - novel_name: Generated novel name
                - story_spec: StorySpec object
                - concept: Concept design object
                - outline: Complete 9-chapter outline object
                - story_bible: Initialized StoryBible object
        """
        # Get agents
        theme_interpreter = self.base_crew.theme_interpreter()
        concept_designer = self.base_crew.concept_designer()
        plot_architect = self.base_crew.plot_architect()
        continuity_keeper = self.base_crew.continuity_keeper()

        # Prepare inputs with placeholders
        inputs_with_placeholders = {
            **inputs,
            "StorySpec": None,
            "StyleGuide": None,
            "Concept": None,
            "StoryBible": None,
            "Outline": None,
            "PlantPayoffTable": None,
        }

        # Task 1: Build StorySpec - Use pre-configured task from base_crew
        build_story_spec_task = self.base_crew.build_story_spec()
        build_story_spec_task.agent = theme_interpreter

        crew1 = Crew(
            agents=[theme_interpreter],
            tasks=[build_story_spec_task],
            verbose=True
        )

        # The monkey-patched converter will automatically repair JSON on parse errors
        result1 = crew1.kickoff(inputs=inputs_with_placeholders)
        spec_result = result1.tasks_output[0].pydantic  # StorySpecWithResult
        novel_name = spec_result.novel_name
        story_spec = spec_result.story_spec

        # Prepare inputs for next task - convert Pydantic to dict for CrewAI
        inputs_2 = {
            **inputs,
            "story_spec": story_spec.model_dump(),
            "StorySpec": story_spec.model_dump(),
        }

        # Task 2: Build Concept - Use pre-configured task from base_crew
        build_concept_task = self.base_crew.build_concept()
        build_concept_task.agent = concept_designer

        crew2 = Crew(
            agents=[concept_designer],
            tasks=[build_concept_task],
            verbose=True
        )

        result2 = crew2.kickoff(inputs=inputs_2)
        concept = result2.tasks_output[0].pydantic  # Direct Pydantic object

        # Prepare inputs for next task - convert Pydantic to dict for CrewAI
        inputs_3 = {
            **inputs_2,
            "concept": concept.model_dump(),
            "Concept": concept.model_dump(),
        }

        # Task 3: Build Outline - Use pre-configured task from base_crew
        build_outline_task = self.base_crew.build_outline()
        build_outline_task.agent = plot_architect

        crew3 = Crew(
            agents=[plot_architect],
            tasks=[build_outline_task],
            verbose=True
        )

        result3 = crew3.kickoff(inputs=inputs_3)
        outline = result3.tasks_output[0].pydantic  # Direct Pydantic object

        # Prepare inputs for next task - convert Pydantic to dict for CrewAI
        inputs_4 = {
            **inputs_3,
            "outline": outline.model_dump(),
            "Outline": outline.model_dump(),
            "PlantPayoffTable": outline.plant_payoff_table,  # Already List[dict]
        }

        # Task 4: Initialize Bible - Use pre-configured task from base_crew
        init_bible_task = self.base_crew.init_bible()
        init_bible_task.agent = continuity_keeper

        crew4 = Crew(
            agents=[continuity_keeper],
            tasks=[init_bible_task],
            verbose=True
        )

        result4 = crew4.kickoff(inputs=inputs_4)
        story_bible = result4.tasks_output[0].pydantic  # Direct Pydantic object

        # Return all results
        return {
            "novel_name": novel_name,
            "story_spec": story_spec,
            "concept": concept,
            "outline": outline,
            "story_bible": story_bible,
            "StoryBible": story_bible,  # Capitalized for agents
        }
