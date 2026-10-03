from typing import Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class PetCharacteristics(BaseModel):
    species: str = ""
    breed: str = ""
    colors: list[str] = Field(default_factory=list)
    size: str = ""
    markings: list[str] = Field(default_factory=list)
    distinctive_features: list[str] = Field(default_factory=list)


class DiscoveredReport(BaseModel):
    id: str
    pet_name: str = ""
    report_type: Literal["lost", "found", "unknown"]
    description: str
    location: str = ""
    report_date: Optional[str] = None
    characteristics: PetCharacteristics = Field(default_factory=PetCharacteristics)
    source_type: Literal["public"] = "public"
    platform: str
    profile_name: Optional[str] = None
    post_title: str
    post_url: AnyHttpUrl
    caption: str
    image_url: Optional[AnyHttpUrl] = None
    contact_info: Optional[str] = None
    date_is_estimated: bool = False


class CandidateAssessment(BaseModel):
    report_id: str
    similarity_score: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=500)


class CandidateAssessmentResponse(BaseModel):
    assessments: list[CandidateAssessment]


class MatchResult(BaseModel):
    id: str
    pet_name: str
    report_type: str
    description: str
    location: str
    report_date: Optional[str] = None
    score: float
    description_score: float
    visual_score: float
    location_score: float
    date_score: float
    ai_score: float
    ai_explanation: str
    reasons: list[str]
    source_type: Literal["local", "public"] = "local"
    platform: Optional[str] = None
    profile_name: Optional[str] = None
    post_url: Optional[AnyHttpUrl] = None
    caption: Optional[str] = None
    image_url: Optional[AnyHttpUrl] = None
    contact_info: Optional[str] = None
    date_is_estimated: bool = False
    post_title: Optional[str] = None


class MatchResponse(BaseModel):
    matches: list[MatchResult]
    notice: str
