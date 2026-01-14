"""Story Bible models for maintaining continuity."""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class Character(BaseModel):
    """Character card."""
    name: str
    role: Literal["protagonist", "antagonist", "supporting", "minor"]
    age: Optional[int] = None
    occupation: Optional[str] = None
    personality: List[str] = Field(default_factory=list)
    motivation: str = ""
    secrets: List[str] = Field(default_factory=list)
    speech_pattern: str = ""  # Voice samples
    forbidden_phrases: List[str] = Field(default_factory=list)
    backstory: str = ""
    arc_description: str = ""


class Relationship(BaseModel):
    """Relationship between characters."""
    character_a: str
    character_b: str
    relationship_type: Literal["romantic", "professional", "family", "rival", "friend", "neutral"]
    status: str = "neutral"  # current state
    history: str = ""
    development_plan: str = ""


class Clue(BaseModel):
    """Clue for mystery genre."""
    clue_id: str
    description: str
    chapter_introduced: int
    is_red_herring: bool = False
    resolved: bool = False
    resolution_chapter: Optional[int] = None
    importance: str = "major"  # major, minor


class TimelineEvent(BaseModel):
    """Timeline event."""
    chapter: int
    scene: Optional[int] = None
    event: str
    characters_involved: List[str] = Field(default_factory=list)
    facts_established: List[str] = Field(default_factory=list)
    emotional_shift: Optional[str] = None


class StoryBible(BaseModel):
    """Story continuity database."""
    # Characters
    characters: List[Character] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)

    # Mystery-specific
    clues: Dict[str, List[Clue]] = Field(
        default_factory=lambda: {"planted": [], "resolved": [], "open": []}
    )
    truth_card: Optional[Dict[str, Any]] = None  # Only for mystery, restricted access

    # Timeline
    timeline: List[TimelineEvent] = Field(default_factory=list)

    # Chapter summaries
    chapter_summaries: List[str] = Field(default_factory=list)

    # Immutable facts (cannot be contradicted)
    immutable_facts: List[str] = Field(default_factory=list)

    # Track used imagery to avoid repetition
    used_imagery: List[str] = Field(default_factory=list)
    used_metaphors: List[str] = Field(default_factory=list)

    # Genre
    genre: str = "romance"  # romance or mystery

    class Config:
        json_encoders = {}
