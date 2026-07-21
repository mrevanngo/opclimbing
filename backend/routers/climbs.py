"""Climb routes: create draft, list, fetch (with holds + analysis), delete.

Ownership rule (CLAUDE.md): every /climbs/* route requires the climb to belong
to the authed user; otherwise 404 - never reveal another user's climb exists.
"""

from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from core.db import get_conn
from core.envelope import ok
from core.security import CurrentUser, get_current_user
from models.schemas import ClimbResponse, HoldResponse

router = APIRouter(prefix="/climbs", tags=["climbs"])


def _owned_climb_or_404(
    conn: psycopg.Connection[dict[str, Any]], climb_id: UUID, user_id: UUID
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, video_ref, status, created_at FROM climbs WHERE id = %s",
            (climb_id,),
        )
        row = cur.fetchone()
    # 404 (not 403) for another user's climb, so existence is not revealed.
    if row is None or row["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Climb not found")
    return row


@router.post("", status_code=status.HTTP_201_CREATED)
def create_climb(
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO climbs (user_id) VALUES (%s) RETURNING id, status, video_ref, created_at",
            (user.id,),
        )
        row = cur.fetchone()
    assert row is not None
    return ok({"climb": ClimbResponse(**row).model_dump(mode="json")})


@router.get("")
def list_climbs(
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, video_ref, created_at
            FROM climbs WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user.id,),
        )
        rows = cur.fetchall()
    climbs = [ClimbResponse(**r).model_dump(mode="json") for r in rows]
    return ok({"climbs": climbs})


@router.get("/{climb_id}")
def get_climb(
    climb_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    climb = _owned_climb_or_404(conn, climb_id, user.id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, sequence_index, frame_x, frame_y
            FROM holds WHERE climb_id = %s
            ORDER BY sequence_index
            """,
            (climb_id,),
        )
        holds = [HoldResponse(**r).model_dump(mode="json") for r in cur.fetchall()]
        cur.execute(
            "SELECT id, climb_id, overall_summary, created_at FROM analyses WHERE climb_id = %s",
            (climb_id,),
        )
        analysis_row = cur.fetchone()

    payload: dict[str, Any] = {
        "climb": ClimbResponse(
            id=climb["id"],
            status=climb["status"],
            video_ref=climb["video_ref"],
            created_at=climb["created_at"],
        ).model_dump(mode="json"),
        "holds": holds,
        "analysis": None,
    }
    if analysis_row is not None:
        payload["analysis"] = {
            "id": str(analysis_row["id"]),
            "climb_id": str(analysis_row["climb_id"]),
            "overall_summary": analysis_row["overall_summary"],
            "created_at": analysis_row["created_at"].isoformat(),
        }
    return ok(payload)


@router.delete("/{climb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_climb(
    climb_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> Response:
    _owned_climb_or_404(conn, climb_id, user.id)
    with conn.cursor() as cur:
        # ON DELETE CASCADE removes holds, analysis, and moves.
        cur.execute("DELETE FROM climbs WHERE id = %s", (climb_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
