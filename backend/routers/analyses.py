"""Analysis routes: run scoring + feedback, and read back the result.

Contract (CLAUDE.md):
  POST /climbs/{id}/analyze { landmarks, frame_rate } -> 201 { data: { analysis } }
  GET  /climbs/{id}/analysis                          -> 200 { data: { analysis, moves } }

The client sends raw landmarks; the server recomputes scoring authoritatively
(scoring/*, validated against the same fixture as the client pipeline), then the
feedback layer turns the numeric metrics into prose. Analyze is idempotent per
climb: re-analyzing replaces the prior analysis (analyses.climb_id is UNIQUE).

Note on landing_control: the moves table (CLAUDE.md schema) stores cog_distance
but not landing_control. Per PIPELINE.md a dynamic move is scored on landing
control; that metric is computed and passed to the feedback layer (which
describes the catch in the note), but is not a persisted column - so a dynamic
move persists cog_distance = NULL and carries its landing quality in the note.
"""

import logging
from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from core.config import get_settings
from core.db import get_conn
from core.envelope import ok
from core.security import CurrentUser, get_current_user
from feedback.base import FeedbackProvider
from feedback.generate import MoveMetrics, generate_feedback, resolve_provider
from models.schemas import AnalysisResponse, AnalyzeRequest, MoveResponse
from routers.climbs import _owned_climb_or_404
from scoring.cog import Landmark, compute_cog_trajectory
from scoring.moves import Hold, classify_moves
from scoring.smoothing import smooth_trajectory

logger = logging.getLogger("optimalclimbing")

router = APIRouter(prefix="/climbs", tags=["analyses"])


def get_feedback_provider() -> FeedbackProvider:
    """The configured feedback provider (template by default; ollama/anthropic
    optional). A dependency so tests can override it if needed."""
    return resolve_provider(get_settings())


def _load_holds(conn: psycopg.Connection[dict[str, Any]], climb_id: UUID) -> list[Hold]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, sequence_index, frame_x, frame_y FROM holds WHERE climb_id = %s ORDER BY sequence_index",
            (climb_id,),
        )
        return [
            Hold(
                id=str(r["id"]),
                sequence_index=r["sequence_index"],
                frame_x=r["frame_x"],
                frame_y=r["frame_y"],
            )
            for r in cur.fetchall()
        ]


@router.post("/{climb_id}/analyze", status_code=status.HTTP_201_CREATED)
def analyze(
    climb_id: UUID,
    body: AnalyzeRequest,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
    feedback_provider: FeedbackProvider = Depends(get_feedback_provider),
) -> dict[str, Any]:
    _owned_climb_or_404(conn, climb_id, user.id)
    holds = _load_holds(conn, climb_id)
    if not holds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Annotate at least one hold before analyzing",
        )

    # --- Scoring (server-authoritative; mirrors the client pipeline) ---
    frames = [
        [Landmark(x=lm.x, y=lm.y, z=lm.z, visibility=lm.visibility) for lm in frame]
        for frame in body.landmarks
    ]
    trajectory = compute_cog_trajectory(frames)
    smoothed = smooth_trajectory(trajectory, body.frame_rate)
    moves = classify_moves(frames, smoothed, holds)

    # --- Feedback (numeric metrics only, never landmarks/video) ---
    metrics = [
        MoveMetrics(
            move_index=m.move_index,
            target_hold_sequence_index=m.target_hold_sequence_index,
            move_type=m.move_type,
            cog_distance=m.cog_distance,
            landing_control=m.landing_control,
            confidence=m.confidence,
            low_confidence=m.low_confidence,
        )
        for m in moves
    ]
    feedback = generate_feedback(metrics, feedback_provider)
    notes = {n.move_index: n.note for n in feedback.notes}

    # --- Persist (idempotent: replace any prior analysis for this climb) ---
    with conn.cursor() as cur:
        cur.execute("DELETE FROM analyses WHERE climb_id = %s", (climb_id,))
        cur.execute(
            "INSERT INTO analyses (climb_id, overall_summary) VALUES (%s, %s) RETURNING id, climb_id, overall_summary, created_at",
            (climb_id, feedback.overall_summary),
        )
        analysis = cur.fetchone()
        assert analysis is not None
        for m in moves:
            cur.execute(
                """
                INSERT INTO moves
                  (analysis_id, move_index, target_hold_id, cog_distance, move_type, confidence, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    analysis["id"],
                    m.move_index,
                    m.target_hold_id,
                    m.cog_distance,  # NULL for dynamic moves
                    m.move_type,
                    m.confidence,
                    notes.get(m.move_index),
                ),
            )
        cur.execute("UPDATE climbs SET status = 'analyzed' WHERE id = %s", (climb_id,))

    return ok({"analysis": AnalysisResponse(**analysis).model_dump(mode="json")})


@router.get("/{climb_id}/analysis")
def get_analysis(
    climb_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    _owned_climb_or_404(conn, climb_id, user.id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, climb_id, overall_summary, created_at FROM analyses WHERE climb_id = %s",
            (climb_id,),
        )
        analysis = cur.fetchone()
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No analysis for this climb"
            )
        cur.execute(
            """
            SELECT move_index, target_hold_id, cog_distance, move_type, confidence, note
            FROM moves WHERE analysis_id = %s
            ORDER BY move_index
            """,
            (analysis["id"],),
        )
        moves = [MoveResponse(**r).model_dump(mode="json") for r in cur.fetchall()]

    return ok(
        {
            "analysis": AnalysisResponse(**analysis).model_dump(mode="json"),
            "moves": moves,
        }
    )
