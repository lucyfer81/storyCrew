"""Judge report models for quality gates."""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class Issue(BaseModel):
    """Issue identified by critic."""
    type: Literal[
        "continuity", "structure", "motivation", "pacing",
        "clue_fairness", "prose", "hook", "safety", "word_count"
    ]
    severity: Literal["low", "medium", "high", "critical"]
    note: str = ""
    location: Optional[str] = None  # chapter/scene reference


class ScoreBreakdown(BaseModel):
    """Score breakdown for different dimensions."""
    continuity: int = Field(default=0, ge=0, le=10)
    pacing: int = Field(default=0, ge=0, le=10)
    character_motivation: int = Field(default=0, ge=0, le=10)
    genre_fulfillment: int = Field(default=0, ge=0, le=10)
    prose: int = Field(default=0, ge=0, le=10)
    hook: int = Field(default=0, ge=0, le=10)

    # Mystery-specific
    clue_fairness: int = Field(default=0, ge=0, le=10)


class JudgeReport(BaseModel):
    """Quality gate report for a chapter or whole book."""
    chapter: Optional[int] = None  # None for whole-book review
    word_count: Optional[int] = None
    is_whole_book: bool = False

    # Scores
    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)

    # Hard requirements
    hard_fail: Dict[str, Any] = Field(default_factory=lambda: {
        "safety_pass": True,
        "continuity_conflicts": [],
        "word_count_in_range": True
    })

    # Overall pass/fail
    passed: bool = False

    # Detailed feedback
    issues: List[Issue] = Field(default_factory=list)
    revision_instructions: List[str] = Field(default_factory=list)

    # Strengths (for positive feedback)
    strengths: List[str] = Field(default_factory=list)

    # Additional metrics for whole-book review
    plant_payoff_coverage: Optional[float] = None  # For whole book
    theme_delivery: Optional[int] = Field(default=None, ge=0, le=10)
    ending_satisfaction: Optional[int] = Field(default=None, ge=0, le=10)

    class Config:
        json_encoders = {}
