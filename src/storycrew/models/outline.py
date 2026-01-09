"""Outline models for story structure."""
from typing import List, Optional
from pydantic import BaseModel, Field


class SceneInfo(BaseModel):
    """Brief scene information for outline level."""
    scene_purpose: str
    conflict: str = ""
    information_gain: str = ""
    emotional_shift: str = ""


class PlantPayoffEntry(BaseModel):
    """Foreshadowing plant and payoff entry."""
    plot_element: str
    planted_chapter: int
    payoff_chapter: int
    payoff_type: str  # reveal, resolution, twist, etc.
    status: str = "planted"  # planted, payoff_complete


class ChapterOutline(BaseModel):
    """Single chapter outline."""
    chapter_number: int
    title: str = ""
    summary: str = ""
    goals: List[str] = Field(default_factory=list)
    conflict: str = ""
    information_increment: str = ""
    emotional_increment: str = ""
    chapter_hook: str = ""  # Ending hook

    # Foreshadowing
    plants_this_chapter: List[str] = Field(default_factory=list)
    payoffs_this_chapter: List[str] = Field(default_factory=list)

    # Scene breakdown (brief)
    scenes: List[SceneInfo] = Field(default_factory=list)

    # Page/word count target
    target_words: int = 3000

    class Config:
        json_encoders = {}
