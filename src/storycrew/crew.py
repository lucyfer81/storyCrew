"""Base crew configuration for StoryCrew."""
import os
import logging
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List, Dict, Any

logger = logging.getLogger("StoryCrew")


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common LLM JSON mistakes before parsing.

    Uses the json_repair library to handle:
    - Missing quotes on keys
    - Trailing commas
    - Single quotes instead of double
    - Invalid escape sequences
    - Trailing characters after JSON (markdown, comments, etc.)
    - And many other JSON formatting issues

    Returns:
        Repaired JSON string, or original if repair fails
    """
    if not json_str:
        return json_str

    try:
        from json_repair import repair_json as lib_repair_json
        import re

        original = json_str

        # Step 1: Remove common trailing content that LLMs add after JSON
        # This includes markdown code blocks, comments, explanatory text, etc.

        # Find the first complete JSON object by counting braces
        cleaned = json_str
        brace_count = 0
        in_string = False
        escape_next = False
        last_valid_pos = 0

        for i, char in enumerate(cleaned):
            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    # When we return to brace_count=0, we've found a complete JSON object
                    if brace_count == 0:
                        # Try to parse up to this position
                        try:
                            import json
                            test_parse = cleaned[:i+1]
                            json.loads(test_parse)  # Verify it's valid JSON
                            last_valid_pos = i + 1
                            logger.info(f"[JSON REPAIR] Found complete JSON object at position {last_valid_pos}")
                        except json.JSONDecodeError:
                            # Not valid JSON yet, keep looking
                            pass

        # If we found a complete JSON object, truncate everything after it
        if last_valid_pos > 0 and last_valid_pos < len(cleaned):
            cleaned = cleaned[:last_valid_pos]
            logger.info(f"[JSON REPAIR] Removed trailing content after JSON (removed {len(json_str) - last_valid_pos} chars)")

        # Step 2: Use the json_repair library to fix common LLM JSON mistakes
        repaired = lib_repair_json(cleaned, skip_json_loads=True)

        if repaired != original:
            logger.info("[JSON REPAIR] Applied repairs using json_repair library")

        return repaired
    except ImportError:
        logger.warning("[JSON REPAIR] json_repair library not available, using original output")
        return json_str
    except Exception as e:
        logger.info(f"[JSON REPAIR] Repair failed with error: {str(e)[:100]}")
        return json_str


# Simple interceptor to log LLM responses for debugging
class LoggingInterceptor:
    """Intercepts LLM responses to log raw output and token usage for debugging."""

    def __init__(self):
        self.request_count = 0
        self.llm_instance = None  # Will be set to track token usage

    def set_llm(self, llm_instance):
        """Set the LLM instance to track token usage."""
        self.llm_instance = llm_instance

    def __call__(self, request, response):
        """Called by CrewAI after each LLM request/response."""
        self.request_count += 1
        logger.info(f"=" * 80)
        logger.info(f"[LLM INTERCEPTOR] Request #{self.request_count}")
        logger.info(f"[LLM INTERCEPTOR] Request URL: {request.url}")
        logger.info(f"[LLM INTERCEPTOR] Request Method: {request.method}")
        logger.info(f"[LLM INTERCEPTOR] Response Status: {response.status_code}")

        # Try to extract and log token usage from response
        try:
            if hasattr(response, 'headers'):
                # Some APIs include token usage in headers (like OpenAI)
                logger.info(f"[LLM INTERCEPTOR] Response Headers: {dict(response.headers)}")

            # Try to parse JSON response for usage field
            if hasattr(response, 'text'):
                import json
                try:
                    response_json = json.loads(response.text)
                    if 'usage' in response_json:
                        usage = response_json['usage']
                        prompt_tokens = usage.get('prompt_tokens', usage.get('input_tokens', 0))
                        completion_tokens = usage.get('completion_tokens', usage.get('output_tokens', 0))
                        total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)

                        logger.info(f"[LLM TOKENS] 📊 Token Usage:")
                        logger.info(f"[LLM TOKENS]   Input (prompt):  {prompt_tokens:,} tokens")
                        logger.info(f"[LLM TOKENS]   Output (completion): {completion_tokens:,} tokens")
                        logger.info(f"[LLM TOKENS]   Total: {total_tokens:,} tokens")

                        # Calculate cost estimate (rough estimate: $0.50 per 1M tokens)
                        input_cost = (prompt_tokens / 1_000_000) * 0.50
                        output_cost = (completion_tokens / 1_000_000) * 1.50
                        total_cost = input_cost + output_cost
                        logger.info(f"[LLM TOKENS]   Est. Cost: ${total_cost:.4f}")
                except json.JSONDecodeError:
                    pass  # Response is not JSON, skip parsing

        except Exception as e:
            logger.debug(f"[LLM INTERCEPTOR] Could not extract token usage: {e}")

        # Try to get the response content
        try:
            if hasattr(response, 'text'):
                content_preview = response.text[:500]
                logger.info(f"[LLM INTERCEPTOR] Response Text (first 500 chars): {content_preview}")
            elif hasattr(response, 'content'):
                content = response.content.decode('utf-8', errors='ignore')
                content_preview = content[:500]
                logger.info(f"[LLM INTERCEPTOR] Response Content (first 500 chars): {content_preview}")
        except Exception as e:
            logger.info(f"[LLM INTERCEPTOR] Could not extract response content: {e}")

        logger.info(f"=" * 80)
        return response


# Import Pydantic models for structured outputs
from storycrew.models import (
    StorySpec, StorySpecWithResult, Concept, BookOutline, StoryBible,
    SceneList, ChapterDraft, ChapterRevision, JudgeReport, NovelMetadata
    # FinalBook removed - assemble_book now outputs plain Markdown text
)

# Load environment variables
load_dotenv()

# Configure LLM from environment variables
_llm = None
_outline_llm = None
_llm_cache = {}  # Cache for LLM instances by env var name

def get_llm():
    """Get or create LLM instance from environment variables."""
    global _llm
    if _llm is None:
        # Ensure env vars are loaded
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

        # LiteLLM requires provider prefix for OpenAI-compatible APIs
        # Format: openai/{model_name}
        llm_model = f"openai/{model_name}"

        print(f"[DEBUG] Creating LLM with model: {llm_model}")
        print(f"[DEBUG] Base URL: {base_url}")

        # Create interceptor for debugging
        interceptor = LoggingInterceptor()

        _llm = LLM(
            model=llm_model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=65536,  # Set both for compatibility
            max_completion_tokens=65536,  # Set both for compatibility
            temperature=0.0,  # Make output more deterministic
            timeout=1800,  # 30 minutes - accommodate complex chapters (6-9) with validation overhead
            interceptor=interceptor  # Add logging interceptor
        )
    return _llm

def get_outline_llm():
    """Get or create LLM instance for outline generation (long text output)."""
    global _outline_llm
    if _outline_llm is None:
        # Ensure env vars are loaded
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("OPENAI_MODEL_OUTLINE", os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"))

        # LiteLLM requires provider prefix for OpenAI-compatible APIs
        # Format: openai/{model_name}
        llm_model = f"openai/{model_name}"

        print(f"[DEBUG] Creating Outline LLM with model: {llm_model}")
        print(f"[DEBUG] Base URL: {base_url}")

        _outline_llm = LLM(
            model=llm_model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=65536,  # Set both for compatibility
            max_completion_tokens=65536,  # Set both for compatibility
            temperature=0.0,  # Make output more deterministic
            timeout=1800  # 30 minutes - accommodate long outline generation
        )
    return _outline_llm

def get_llm_by_env(env_var_name: str, default: str = "gpt-4o-mini"):
    """Get or create LLM instance from a specific environment variable."""
    global _llm_cache

    if env_var_name not in _llm_cache:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv(env_var_name, default)

        # LiteLLM requires provider prefix for OpenAI-compatible APIs
        llm_model = f"openai/{model_name}"

        print(f"[DEBUG] Creating LLM from {env_var_name}: {llm_model}")
        print(f"[DEBUG] Base URL: {base_url}")

        _llm_cache[env_var_name] = LLM(
            model=llm_model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=65536,  # Set both for compatibility
            max_completion_tokens=65536,  # Set both for compatibility
            temperature=0.0,  # Make output more deterministic
            timeout=1800  # 30 minutes - accommodate complex chapter generation
        )

    return _llm_cache[env_var_name]

@CrewBase
class Storycrew():
    """Base StoryCrew configuration - provides access to agents and tasks."""

    agents: List[BaseAgent]
    tasks: List[Task]

    # ==================== AGENTS ====================
    @agent
    def theme_interpreter(self) -> Agent:
        return Agent(
            config=self.agents_config['theme_interpreter'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def concept_designer(self) -> Agent:
        return Agent(
            config=self.agents_config['concept_designer'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def plot_architect(self) -> Agent:
        return Agent(
            config=self.agents_config['plot_architect'],
            llm=get_outline_llm(),  # Use dedicated LLM for outline generation
            verbose=True
        )

    @agent
    def continuity_keeper(self) -> Agent:
        return Agent(
            config=self.agents_config['continuity_keeper'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def chapter_planner(self) -> Agent:
        return Agent(
            config=self.agents_config['chapter_planner'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def chapter_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['chapter_writer'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def line_editor(self) -> Agent:
        return Agent(
            config=self.agents_config['line_editor'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def critic_judge(self) -> Agent:
        return Agent(
            config=self.agents_config['critic_judge'],
            llm=get_llm(),
            verbose=True
        )

    # ==================== TASKS ====================
    @task
    def build_story_spec(self) -> Task:
        return Task(
            config=self.tasks_config['build_story_spec'],
            output_pydantic=StorySpecWithResult
        )

    @task
    def build_concept(self) -> Task:
        return Task(
            config=self.tasks_config['build_concept'],
            output_pydantic=Concept
        )

    @task
    def build_outline(self) -> Task:
        return Task(
            config=self.tasks_config['build_outline'],
            output_pydantic=BookOutline
        )

    @task
    def init_bible(self) -> Task:
        return Task(
            config=self.tasks_config['init_bible'],
            output_pydantic=StoryBible
        )

    @task
    def plan_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['plan_chapter'],
            output_pydantic=SceneList
        )

    @task
    def write_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['write_chapter']
            # Removed output_pydantic=ChapterDraft - plain text output is sufficient
            # and avoids JSON validation overhead for 3000-word chapter text
        )

    @task
    def update_bible(self) -> Task:
        return Task(
            config=self.tasks_config['update_bible'],
            output_pydantic=StoryBible
        )

    @task
    def edit_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['edit_chapter']
            # Removed output_pydantic=ChapterRevision - plain text output is sufficient
            # and avoids JSON validation overhead for 3000-word chapter text
        )

    @task
    def judge_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['judge_chapter'],
            output_pydantic=JudgeReport
        )

    @task
    def judge_whole_book(self) -> Task:
        return Task(
            config=self.tasks_config['judge_whole_book'],
            output_pydantic=JudgeReport
        )

    @task
    def generate_novel_metadata(self) -> Task:
        return Task(
            config=self.tasks_config['generate_novel_metadata'],
            output_pydantic=NovelMetadata
        )

    @task
    def assemble_book(self) -> Task:
        return Task(
            config=self.tasks_config['assemble_book']
            # Output plain text (Markdown format) - no Pydantic validation needed
            # for final book assembly
        )

    # ==================== LEGACY SUPPORT ====================
    @crew
    def crew(self) -> Crew:
        """
        Legacy crew method for backward compatibility.
        Creates a sequential crew with all agents and tasks.
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    # ==================== UTILITY METHODS ====================
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get raw agent configuration by name."""
        return self.agents_config[agent_name]

    def get_task_config(self, task_name: str) -> Dict[str, Any]:
        """Get raw task configuration by name."""
        return self.tasks_config[task_name]
