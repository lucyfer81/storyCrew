"""Base crew configuration for StoryCrew."""
import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List, Dict, Any

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

        _llm = LLM(
            model=llm_model,
            api_key=api_key,
            base_url=base_url
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
            base_url=base_url
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
            base_url=base_url
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
            config=self.tasks_config['build_story_spec']
        )

    @task
    def build_concept(self) -> Task:
        return Task(
            config=self.tasks_config['build_concept']
        )

    @task
    def build_outline(self) -> Task:
        return Task(
            config=self.tasks_config['build_outline']
        )

    @task
    def init_bible(self) -> Task:
        return Task(
            config=self.tasks_config['init_bible']
        )

    @task
    def plan_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['plan_chapter']
        )

    @task
    def write_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['write_chapter']
        )

    @task
    def update_bible(self) -> Task:
        return Task(
            config=self.tasks_config['update_bible']
        )

    @task
    def edit_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['edit_chapter']
        )

    @task
    def judge_chapter(self) -> Task:
        return Task(
            config=self.tasks_config['judge_chapter']
        )

    @task
    def judge_whole_book(self) -> Task:
        return Task(
            config=self.tasks_config['judge_whole_book']
        )

    @task
    def assemble_book(self) -> Task:
        return Task(
            config=self.tasks_config['assemble_book']
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
