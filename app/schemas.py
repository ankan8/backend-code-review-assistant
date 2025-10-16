from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class Issue(BaseModel):
    id: int
    rule_id: str
    severity: str
    message: str
    line: int | None = None
    file_id: int | None = None

    model_config = ConfigDict(from_attributes=True)

class ReviewFileOut(BaseModel):
    id: int
    filename: str
    language: str | None = None

    model_config = ConfigDict(from_attributes=True)

class ReviewOut(BaseModel):
    id: int
    created_at: datetime
    summary: str | None = None
    llm_used: bool
    files: list[ReviewFileOut] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
