from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


DISCLAIMER_TEXT = (
    "This information is based on model bye-laws and is for informational "
    "purposes only. Actual applicability depends on the registered bye-laws "
    "of the specific society."
)


class ConditionItem(BaseModel):
    requirement: str
    plain_explanation: str


class RelatedRuleItem(BaseModel):
    section: str
    subsection: Optional[str] = None
    title: str


class AnalyzeRequest(BaseModel):
    description: str = Field(
        ...,
        min_length=10,
        max_length=3000,
        description="Plain-language description of the housing society issue.",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Description cannot be empty.")
        return cleaned


class AnalyzeResponse(BaseModel):
    law: str
    section: Optional[str]
    subsection: Optional[str]
    title: Optional[str]
    explanation: str
    citation: str
    example: str
    conditions_required: list[ConditionItem]
    possible_challenges: list[str]
    related_statutes: list[str]
    related_rules: list[RelatedRuleItem]
    confidence: float = Field(..., ge=0.0, le=1.0)
    disclaimer: str = DISCLAIMER_TEXT


class FollowupRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1500)
    context: dict[str, Any]

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned


class FollowupResponse(BaseModel):
    section: Optional[str]
    subsection: Optional[str]
    title: Optional[str]
    answer: str
    citation: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    disclaimer: str = DISCLAIMER_TEXT
