"""Climb routes: a climb is one logbook entry (video analysis is optional extra
data on it). Create, list, fetch (with holds + analysis), update log fields, delete.

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
from models.schemas import ClimbLogInput, ClimbResponse, HoldResponse

router = APIRouter(prefix="/climbs", tags=["climbs"])

_CLIMB_COLUMNS = (
    "id, status, video_ref, created_at, grade, angle, outcome, attempts, beta_notes, climbed_at"
)


def _owned_climb_or_404(
    conn: psycopg.Connection[dict[str, Any]], climb_id: UUID, user_id: UUID
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT user_id, {_CLIMB_COLUMNS} FROM climbs WHERE id = %s",
            (climb_id,),
        )
        row = cur.fetchone()
    # 404 (not 403) for another user's climb, so existence is not revealed.
    if row is None or row["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Climb not found")
    return row


def _hold_types(conn: psycopg.Connection[dict[str, Any]], climb_id: UUID) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT hold_type FROM climb_hold_types WHERE climb_id = %s ORDER BY hold_type",
            (climb_id,),
        )
        return [r["hold_type"] for r in cur.fetchall()]


def _replace_hold_types(
    conn: psycopg.Connection[dict[str, Any]], climb_id: UUID, hold_types: list[str]
) -> None:
    """Replace the tag set atomically (dedup preserved by the PK)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM climb_hold_types WHERE climb_id = %s", (climb_id,))
        for ht in dict.fromkeys(hold_types):  # de-duplicate, keep order
            cur.execute(
                "INSERT INTO climb_hold_types (climb_id, hold_type) VALUES (%s, %s)",
                (climb_id, ht),
            )


def _climb_payload(row: dict[str, Any], hold_types: list[str]) -> dict[str, Any]:
    data = {k: row[k] for k in ClimbResponse.model_fields if k in row}
    data["hold_types"] = hold_types
    return ClimbResponse(**data).model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_climb(
    body: ClimbLogInput | None = None,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """Create a climb. With no body this is a bare draft for the video flow;
    with log fields it is a logbook entry (no video required)."""
    log = body or ClimbLogInput()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO climbs (user_id, grade, angle, outcome, attempts, beta_notes, climbed_at)
            VALUES (%s, %s, %s, %s, COALESCE(%s, 1), %s, COALESCE(%s, NOW()))
            RETURNING {_CLIMB_COLUMNS}
            """,
            (
                user.id,
                log.grade,
                log.angle,
                log.outcome,
                log.attempts,
                log.beta_notes,
                log.climbed_at,
            ),
        )
        row = cur.fetchone()
    assert row is not None
    if log.hold_types:
        _replace_hold_types(conn, row["id"], list(log.hold_types))
    return ok({"climb": _climb_payload(row, list(log.hold_types or []))})


@router.patch("/{climb_id}")
def update_climb(
    climb_id: UUID,
    body: ClimbLogInput,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """Update logbook fields on an existing climb. Only fields present in the
    request are changed (a partial update)."""
    _owned_climb_or_404(conn, climb_id, user.id)

    sent = body.model_dump(exclude_unset=True)
    scalar = {k: v for k, v in sent.items() if k != "hold_types"}
    with conn.cursor() as cur:
        if scalar:
            assignments = ", ".join(f"{col} = %s" for col in scalar)
            cur.execute(
                f"UPDATE climbs SET {assignments} WHERE id = %s",  # column names are from a fixed model, values parameterized
                (*scalar.values(), climb_id),
            )
        if "hold_types" in sent:
            _replace_hold_types(conn, climb_id, list(sent["hold_types"] or []))
        cur.execute(f"SELECT {_CLIMB_COLUMNS} FROM climbs WHERE id = %s", (climb_id,))
        row = cur.fetchone()
    assert row is not None
    return ok({"climb": _climb_payload(row, _hold_types(conn, climb_id))})


@router.get("")
def list_climbs(
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """This user's climbs, most recently climbed first."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CLIMB_COLUMNS},
                   COALESCE(
                     (SELECT array_agg(h.hold_type ORDER BY h.hold_type)
                      FROM climb_hold_types h WHERE h.climb_id = climbs.id),
                     '{{}}'
                   ) AS hold_types
            FROM climbs WHERE user_id = %s
            ORDER BY climbed_at DESC, created_at DESC
            """,
            (user.id,),
        )
        rows = cur.fetchall()
    climbs = [_climb_payload(r, list(r["hold_types"])) for r in rows]
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
        "climb": _climb_payload(climb, _hold_types(conn, climb_id)),
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
        # ON DELETE CASCADE removes holds, hold types, analysis, and moves.
        cur.execute("DELETE FROM climbs WHERE id = %s", (climb_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
