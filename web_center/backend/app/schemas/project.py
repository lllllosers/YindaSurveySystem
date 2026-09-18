from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProjectStatus = Literal["active", "archived"]
SurveyBatchStatus = Literal["planned", "active", "closed"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    short_name: str | None = Field(default=None, max_length=100)
    status: ProjectStatus = "active"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    short_name: str | None = Field(default=None, max_length=100)
    status: ProjectStatus | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_uid: str
    name: str
    short_name: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class SurveyBatchBase(BaseModel):
    batch_name: str = Field(min_length=1, max_length=200)
    batch_code: str = Field(min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    status: SurveyBatchStatus = "planned"

    @model_validator(mode="after")
    def validate_dates(self) -> "SurveyBatchBase":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class SurveyBatchCreate(SurveyBatchBase):
    pass


class SurveyBatchUpdate(BaseModel):
    batch_name: str | None = Field(default=None, min_length=1, max_length=200)
    batch_code: str | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    status: SurveyBatchStatus | None = None


class SurveyBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    survey_batch_uid: str
    batch_name: str
    batch_code: str
    start_date: date | None
    end_date: date | None
    status: SurveyBatchStatus
    created_at: datetime
    updated_at: datetime
