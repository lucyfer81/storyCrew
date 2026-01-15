"""Story specification models."""
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class StorySpecWithResult(BaseModel):
    """Wrapper for build_story_spec task output."""
    novel_name: str
    story_spec: StorySpec


class NarrationConfig(BaseModel):
    """Narration configuration."""
    pov: Literal["first_person", "third_person", "third_limited", "third_omniscient"] = "third_person"
    tense: Literal["past", "present", "past_or_present_consistent"] = "past_or_present_consistent"


class StyleGuide(BaseModel):
    """Writing style guide."""
    language: str = "zh"
    tone: List[str] = Field(default_factory=lambda: ["现实", "细腻", "有张力"])
    pacing: Literal["slow", "balanced", "fast", "variable"] = "balanced"
    imagery_density: Literal["sparse", "light", "moderate", "rich", "dense"] = "moderate"
    dialogue_ratio: float = Field(default=0.3, ge=0.0, le=1.0)
    forbidden_words: List[str] = Field(default_factory=list)
    style_notes: List[str] = Field(default_factory=list)


class StorySpec(BaseModel):
    """Complete story specification."""
    # Basic metadata
    language: str = "zh"
    genre: Literal["romance", "mystery"] = "romance"
    subgenre: Literal["urban_workplace", "traditional", "social", "police_procedural", "cozy"] = "urban_workplace"

    # Structure
    total_chapters: int = 9
    target_words_per_chapter: int = 3000
    chapter_word_tolerance: float = 0.1  # ±10%

    # Narration
    narration: NarrationConfig = Field(default_factory=NarrationConfig)

    # Style
    style: StyleGuide = Field(default_factory=StyleGuide)

    # Content constraints
    taboos: List[str] = Field(default_factory=lambda: [
        "未成年人性内容",
        "过度血腥细节",
        "仇恨/歧视性表达"
    ])
    must_have: List[str] = Field(default_factory=lambda: [
        "章末钩子",
        "每章信息增量",
        "每章情绪转折"
    ])

    # Genre-specific fields
    # Romance-specific
    relationship_arc: Optional[str] = None
    emotional_turns_per_chapter: int = 1

    # Mystery-specific
    mystery_question: Optional[str] = None
    truth_solution: Optional[str] = None  # For internal use only
    suspect_pool_size: int = 5
    clue_budget_rule: str = "每章至少1条可见线索入库"
    fair_play_rule: str = "终局解答所用关键线索必须在前文出现"

    # Theme
    theme_statement: str = ""  # Core theme to be delivered
    ending_contract: str = "结局必须兑现主题句的价值判断或反讽"

    class Config:
        json_encoders = {
            # Add any custom encoders if needed
        }
