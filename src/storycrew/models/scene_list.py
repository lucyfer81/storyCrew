"""Scene list models for detailed chapter planning."""
from typing import List, Optional
from pydantic import BaseModel, Field


class Scene(BaseModel):
    """Detailed scene information."""
    scene_number: int
    purpose: str
    setting: str = ""
    characters: List[str] = Field(default_factory=list)

    # Core elements
    conflict: str = ""
    action_beat: str = ""
    dialogue_focus: str = ""

    # Progression
    information_revealed: str = ""
    emotional_shift: str = ""
    plot_advancement: str = ""

    # Exit
    exit_hook: str = ""  # How scene ends (hook to next)

    # Target length
    target_words: int = 400

    # Notes
    notes: List[str] = Field(default_factory=list)


class SceneList(BaseModel):
    """Detailed scene list for a chapter."""
    chapter_number: int
    chapter_title: str = ""
    scenes: List[Scene] = Field(default_factory=list)
    total_target_words: int = 3000

    # Foreshadowing reminders
    clues_to_plant: List[str] = Field(default_factory=list)
    clues_to_reveal: List[str] = Field(default_factory=list)
    plot_points_to_advance: List[str] = Field(default_factory=list)

    # Chapter-level requirements
    chapter_goal: str = ""
    required_emotional_arc: str = ""

    class Config:
        json_encoders = {}
