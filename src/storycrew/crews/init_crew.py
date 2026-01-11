"""Initialization Crew for story generation setup."""
from crewai import Crew, Process, Agent, Task
from storycrew.crew import Storycrew, repair_json
from storycrew.models import StorySpecWithResult, Concept, StoryBible
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


def _ensure_clue_fields(json_str: str) -> str:
    """
    Ensure all Clue objects have required fields.

    Fixes missing 'description' field in Clue objects by adding
    a meaningful placeholder that includes the clue_id.

    Args:
        json_str: JSON string potentially containing incomplete Clue objects

    Returns:
        JSON string with all Clue objects having required fields
    """
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return json_str  # If not valid JSON, return as-is

    # Fix clues.planted, clues.resolved, clues.open
    if 'clues' in data and isinstance(data['clues'], dict):
        for clue_list_key in ['planted', 'resolved', 'open']:
            if clue_list_key in data['clues'] and isinstance(data['clues'][clue_list_key], list):
                for clue in data['clues'][clue_list_key]:
                    if isinstance(clue, dict):
                        # Ensure description field exists
                        if 'description' not in clue or not clue['description']:
                            clue_id = clue.get('clue_id', 'unknown')
                            clue['description'] = f"[线索 {clue_id}: 详细描述待补充]"
                            logger.info(f"[CLUE REPAIR] Added missing description for clue {clue_id}")

                        # Ensure chapter_introduced is an integer
                        if 'chapter_introduced' in clue and not isinstance(clue['chapter_introduced'], int):
                            original_value = clue['chapter_introduced']
                            if isinstance(original_value, str):
                                # Try to extract number from string (e.g., "第5章" -> 5)
                                import re
                                match = re.search(r'\d+', str(original_value))
                                if match:
                                    clue['chapter_introduced'] = int(match.group())
                                    logger.info(f"[CLUE REPAIR] Converted chapter_introduced from string to int: '{original_value}' -> {clue['chapter_introduced']}")
                                else:
                                    # If no number found, set to 1 as default
                                    clue['chapter_introduced'] = 1
                                    logger.info(f"[CLUE REPAIR] Set chapter_introduced to 1 (could not parse number from '{original_value}')")
                            else:
                                # Non-string, non-integer value - set to 1
                                clue['chapter_introduced'] = 1
                                logger.info(f"[CLUE REPAIR] Set chapter_introduced to 1 (invalid type: {type(original_value).__name__})")

    return json.dumps(data, ensure_ascii=False)


def _ensure_timeline_event_fields(json_str: str) -> str:
    """
    Ensure all TimelineEvent objects have required fields.

    Fixes missing 'event' field and ensures 'scene' is an integer, not a string.

    Args:
        json_str: JSON string potentially containing incomplete TimelineEvent objects

    Returns:
        JSON string with all TimelineEvent objects having required fields
    """
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return json_str  # If not valid JSON, return as-is

    # Fix timeline events
    if 'timeline' in data and isinstance(data['timeline'], list):
        for i, event in enumerate(data['timeline']):
            if isinstance(event, dict):
                # Ensure event field exists
                if 'event' not in event or not event['event']:
                    chapter = event.get('chapter', '?')
                    event['event'] = f"[第{chapter}章事件描述待补充]"
                    logger.info(f"[TIMELINE REPAIR] Added missing event for timeline[{i}]")

                # Ensure scene is an integer, not a string
                if 'scene' in event and isinstance(event['scene'], str):
                    # Try to extract number from string like "plants7" -> 7
                    import re
                    match = re.search(r'\d+', event['scene'])
                    if match:
                        event['scene'] = int(match.group())
                        logger.info(f"[TIMELINE REPAIR] Converted scene from string to int: timeline[{i}]")
                    else:
                        # If no number found, set to None
                        event['scene'] = None
                        logger.info(f"[TIMELINE REPAIR] Set scene to None for timeline[{i}] (could not parse number)")

    return json.dumps(data, ensure_ascii=False)


def _ensure_character_fields(json_str: str) -> str:
    """
    Ensure all Character objects have valid field types and correct structure.

    Fixes two types of issues:
    1. Corrupted integer fields (age) that may contain strings
    2. Wrong object types in characters array (e.g., TimelineEvent objects mixed in)

    This addresses the issue where LLM accidentally mixes timeline data into characters array,
    causing validation errors like "characters.3.name Field required".

    Args:
        json_str: JSON string potentially containing corrupted Character objects

    Returns:
        JSON string with all Character objects having valid field types and correct structure
    """
    import re
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return json_str  # If not valid JSON, return as-is

    # Fix characters list - filter out invalid objects and fix valid ones
    if 'characters' in data and isinstance(data['characters'], list):
        clean_characters = []
        for i, char in enumerate(data['characters']):
            if not isinstance(char, dict):
                logger.warning(f"[CHARACTER REPAIR] Skipping non-dict object at characters[{i}]: {type(char).__name__}")
                continue

            # Check if this is a valid Character object (must have name and role)
            has_name = 'name' in char and char['name']
            has_role = 'role' in char and char['role']

            # Detect TimelineEvent objects mixed into characters array
            if not has_name and not has_role:
                if 'chapter' in char and 'scene' in char:
                    # This is a TimelineEvent, not a Character - remove it
                    logger.warning(f"[CHARACTER REPAIR] Found TimelineEvent in characters[{i}] (chapter={char.get('chapter')}, scene={char.get('scene')}), removing")
                    continue
                else:
                    # Check if this is a completely corrupted/empty object
                    char_str = str(char).strip()
                    # Remove objects that are empty, only whitespace, or minimal corruption
                    if len(char_str) <= 10 or char_str in ['{}', '{', '', ' ', '\t', '\n', '\r', '\r\n']:
                        # Completely corrupted object - remove it
                        logger.warning(f"[CHARACTER REPAIR] Found corrupted/empty object in characters[{i}]: '{char_str[:20]}', removing")
                        continue
                    else:
                        # Unknown object type - add default values to make it valid
                        logger.warning(f"[CHARACTER REPAIR] Found invalid object in characters[{i}], adding default name/role")
                        char['name'] = f"Unknown Character {len(clean_characters)}"
                        char['role'] = "supporting"

            # Fix age field - must be integer
            if 'age' in char and not isinstance(char['age'], (int, type(None))):
                age_value = char['age']
                if isinstance(age_value, str):
                    # Try to extract number from string
                    match = re.search(r'\d+', age_value)
                    if match:
                        char['age'] = int(match.group())
                        logger.info(f"[CHARACTER REPAIR] Converted age from string to int: characters[{i}].age = {char['age']}")
                    else:
                        # If no number found, set to None
                        char['age'] = None
                        logger.info(f"[CHARACTER REPAIR] Set age to None for characters[{i}] (could not parse number from '{age_value}')")
                else:
                    # Non-string, non-integer value
                    char['age'] = None
                    logger.info(f"[CHARACTER REPAIR] Set age to None for characters[{i}] (invalid type: {type(age_value).__name__}, value: {age_value})")

            clean_characters.append(char)

        data['characters'] = clean_characters

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
    # Apply model-specific sanitization before parsing
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

        # Step 1: Apply JSON syntax repairs (missing quotes, trailing commas, etc.)
        repaired = repair_json(str(working_result))

        # Step 2: Apply model-specific field completion
        if repaired != str(working_result):
            logger.info(f"[JSON REPAIR] Applied syntax repairs (first 200 chars): {repaired[:200]}")

        # For Concept model, apply sanitization again after repair
        if model == Concept:
            repaired = sanitize_concept_json(repaired)

        # For StoryBible model, apply field completion for missing required fields
        if model == StoryBible:
            logger.info("[STORYBIBLE REPAIR] Applying field completion for StoryBible")

            # Fix Clue objects (missing description)
            repaired_after_clues = _ensure_clue_fields(repaired)
            if repaired_after_clues != repaired:
                logger.info("[STORYBIBLE REPAIR] Fixed missing Clue.description fields")
                repaired = repaired_after_clues

            # Fix TimelineEvent objects (missing event, wrong scene type)
            repaired_after_timeline = _ensure_timeline_event_fields(repaired)
            if repaired_after_timeline != repaired:
                logger.info("[STORYBIBLE REPAIR] Fixed TimelineEvent field issues")
                repaired = repaired_after_timeline

            # Fix Character objects (corrupted age field type)
            repaired_after_characters = _ensure_character_fields(repaired)
            if repaired_after_characters != repaired:
                logger.info("[STORYBIBLE REPAIR] Fixed Character field issues")
                repaired = repaired_after_characters

        # Step 3: Retry parsing with repaired JSON
        try:
            return _original_handle_partial_json(repaired, model, is_json_output, agent, converter_cls)
        except Exception as e2:
            # If still failing after all repairs, log and re-raise
            logger.info(f"[JSON REPAIR] Parse failed even after repairs. Error: {str(e2)[:100]}")
            logger.info("[JSON REPAIR] Re-raising original error")
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
