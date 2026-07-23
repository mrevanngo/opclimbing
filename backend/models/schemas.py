"""Pydantic request/response models. Input is validated at the boundary
(CLAUDE.md - Python Conventions); the landmarks contract mirrors PIPELINE.md.

Responses are wrapped in the ``{ "data": ... }`` envelope by the routers; these
models describe the payloads that go inside it.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

LANDMARKS_PER_FRAME = 33


# --- Auth ------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    created_at: dt.datetime


# --- Climbs / logbook ------------------------------------------------------

# A climb is one logbook entry; video analysis is optional extra data on it.
Angle = Literal["slab", "vertical", "overhang", "roof"]
Outcome = Literal["flash", "send", "attempt"]
HoldType = Literal["crimp", "jug", "sloper", "pinch", "pocket"]


class ClimbLogInput(BaseModel):
    """Logbook fields. All optional so this works for both creating a logged
    climb and patching one (including a video draft logged after the fact)."""

    grade: int | None = Field(default=None, ge=0, le=17)  # V-scale
    angle: Angle | None = None
    outcome: Outcome | None = None
    attempts: int | None = Field(default=None, ge=1)
    beta_notes: str | None = Field(default=None, max_length=2000)
    climbed_at: dt.datetime | None = None  # backfill past sessions
    hold_types: list[HoldType] | None = None


class ClimbResponse(BaseModel):
    id: UUID
    status: str
    video_ref: str | None
    created_at: dt.datetime
    grade: int | None = None
    angle: str | None = None
    outcome: str | None = None
    attempts: int = 1
    beta_notes: str | None = None
    climbed_at: dt.datetime | None = None
    hold_types: list[str] = Field(default_factory=list)


# --- Stats (logbook analytics) ---------------------------------------------

class ProgressionPoint(BaseModel):
    month: str  # YYYY-MM
    sends: int
    max_grade: int
    median_grade: float
    running_best: int  # best grade sent up to and including this month


class HoldTypeStat(BaseModel):
    hold_type: str
    total: int
    sends: int
    send_rate: float  # percent


class AngleStat(BaseModel):
    angle: str
    logged: int
    sends: int
    send_rate: float  # percent
    best_grade: int | None
    grade_per_month: float | None  # trend slope from regr_slope
    trend: Literal["improving", "plateau", "declining", "insufficient_data"]


# --- Holds -----------------------------------------------------------------

class HoldInput(BaseModel):
    sequence_index: int = Field(ge=0)
    frame_x: float = Field(ge=0.0, le=1.0)
    frame_y: float = Field(ge=0.0, le=1.0)


class HoldsRequest(BaseModel):
    holds: list[HoldInput]


class HoldResponse(BaseModel):
    id: UUID
    sequence_index: int
    frame_x: float
    frame_y: float


# --- Analyze (landmarks payload -> scoring) --------------------------------

class Landmark(BaseModel):
    x: float
    y: float
    z: float
    visibility: float


class AnalyzeRequest(BaseModel):
    frame_rate: float = Field(gt=0.0, le=240.0)
    landmarks: list[list[Landmark]] = Field(min_length=1)

    @field_validator("landmarks")
    @classmethod
    def each_frame_has_33_landmarks(cls, frames: list[list[Landmark]]) -> list[list[Landmark]]:
        for i, frame in enumerate(frames):
            if len(frame) != LANDMARKS_PER_FRAME:
                raise ValueError(
                    f"frame {i} has {len(frame)} landmarks, expected {LANDMARKS_PER_FRAME}"
                )
        return frames


class MoveResponse(BaseModel):
    move_index: int
    target_hold_id: UUID | None
    cog_distance: float | None
    move_type: Literal["static", "dynamic"]
    confidence: float
    note: str | None


class AnalysisResponse(BaseModel):
    id: UUID
    climb_id: UUID
    overall_summary: str | None
    created_at: dt.datetime
