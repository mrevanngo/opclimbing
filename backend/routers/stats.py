"""Logbook analytics: the insights that fall out of logging climbs.

Three questions, answered in SQL rather than in Python, so the database does the
aggregation:
  GET /stats/progression  - grade progression over time (window function)
  GET /stats/hold-types   - send rate per hold type (FILTER aggregates)
  GET /stats/angles       - send rate + progression trend per wall angle, using
                            regr_slope to detect a plateau

Every query is scoped to the authed user.
"""

from typing import Any

import psycopg
from fastapi import APIRouter, Depends

from core.db import get_conn
from core.envelope import ok
from core.security import CurrentUser, get_current_user
from models.schemas import AngleStat, HoldTypeStat, ProgressionPoint

router = APIRouter(prefix="/stats", tags=["stats"])

# A send is a climb completed, flashed or not. Attempts are logged but not sends.
_SENT = "outcome IN ('flash','send')"

# Grades per month below/above which a trend counts as movement rather than a
# plateau. Heuristic, tunable as more real logging data accumulates.
_TREND_EPSILON = 0.05
_MIN_POINTS_FOR_TREND = 3


@router.get("/progression")
def progression(
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """Monthly send volume, hardest and median grade, plus the running best
    grade to date (window function over the monthly rollup)."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH monthly AS (
              SELECT date_trunc('month', climbed_at)                      AS month,
                     COUNT(*)                                             AS sends,
                     MAX(grade)                                           AS max_grade,
                     PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY grade)   AS median_grade
              FROM climbs
              WHERE user_id = %s AND grade IS NOT NULL AND {_SENT}
              GROUP BY 1
            )
            SELECT to_char(month, 'YYYY-MM')      AS month,
                   sends,
                   max_grade,
                   median_grade,
                   MAX(max_grade) OVER (ORDER BY month) AS running_best
            FROM monthly
            ORDER BY month
            """,
            (user.id,),
        )
        rows = cur.fetchall()

    points = [
        ProgressionPoint(
            month=r["month"],
            sends=int(r["sends"]),
            max_grade=int(r["max_grade"]),
            median_grade=float(r["median_grade"]),
            running_best=int(r["running_best"]),
        ).model_dump(mode="json")
        for r in rows
    ]
    return ok({"progression": points})


@router.get("/hold-types")
def hold_types(
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """Send rate per hold type, weakest first - which holds shut you down."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT h.hold_type,
                   COUNT(*)                                  AS total,
                   COUNT(*) FILTER (WHERE c.{_SENT})         AS sends,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE c.{_SENT}) / COUNT(*), 1) AS send_rate
            FROM climb_hold_types h
            JOIN climbs c ON c.id = h.climb_id
            WHERE c.user_id = %s AND c.outcome IS NOT NULL
            GROUP BY h.hold_type
            ORDER BY send_rate ASC, h.hold_type
            """,
            (user.id,),
        )
        rows = cur.fetchall()

    stats = [
        HoldTypeStat(
            hold_type=r["hold_type"],
            total=int(r["total"]),
            sends=int(r["sends"]),
            send_rate=float(r["send_rate"]),
        ).model_dump(mode="json")
        for r in rows
    ]
    return ok({"hold_types": stats})


def _classify(grade_per_month: float | None, send_points: int) -> str:
    if grade_per_month is None or send_points < _MIN_POINTS_FOR_TREND:
        return "insufficient_data"
    if grade_per_month > _TREND_EPSILON:
        return "improving"
    if grade_per_month < -_TREND_EPSILON:
        return "declining"
    return "plateau"


@router.get("/angles")
def angles(
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """Per wall angle: send rate, best grade, and whether grade is trending up
    or flat. The trend is a least-squares slope of grade against time
    (regr_slope), scaled to grades per 30 days, so a slope near zero is a plateau.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH logged AS (
              SELECT angle, grade, outcome,
                     EXTRACT(EPOCH FROM climbed_at) / 86400.0 AS day
              FROM climbs
              WHERE user_id = %s AND angle IS NOT NULL AND outcome IS NOT NULL
            ),
            trend AS (
              SELECT angle,
                     COUNT(*)                        AS send_points,
                     regr_slope(grade, day) * 30.0   AS grade_per_month
              FROM logged
              WHERE {_SENT} AND grade IS NOT NULL
              GROUP BY angle
            )
            SELECT l.angle,
                   COUNT(*)                                                      AS logged,
                   COUNT(*) FILTER (WHERE l.{_SENT})                             AS sends,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE l.{_SENT}) / COUNT(*), 1) AS send_rate,
                   MAX(l.grade) FILTER (WHERE l.{_SENT})                         AS best_grade,
                   t.grade_per_month,
                   COALESCE(t.send_points, 0)                                    AS send_points
            FROM logged l
            LEFT JOIN trend t ON t.angle = l.angle
            GROUP BY l.angle, t.grade_per_month, t.send_points
            ORDER BY l.angle
            """,
            (user.id,),
        )
        rows = cur.fetchall()

    stats = []
    for r in rows:
        slope = None if r["grade_per_month"] is None else float(r["grade_per_month"])
        stats.append(
            AngleStat(
                angle=r["angle"],
                logged=int(r["logged"]),
                sends=int(r["sends"]),
                send_rate=float(r["send_rate"]),
                best_grade=None if r["best_grade"] is None else int(r["best_grade"]),
                grade_per_month=None if slope is None else round(slope, 3),
                trend=_classify(slope, int(r["send_points"])),
            ).model_dump(mode="json")
        )
    return ok({"angles": stats})
