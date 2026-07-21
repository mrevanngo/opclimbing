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


# --- Climbs ----------------------------------------------------------------

class ClimbResponse(BaseModel):
    id: UUID
    status: str
    video_ref: str | None
    created_at: dt.datetime


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
