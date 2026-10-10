from __future__ import annotations

from collections.abc import Sequence

from ehf.domain.attendance_analytics import AttendanceReport
from ehf.domain.attendance_calendar import WEEKDAY_LABELS, CalendarBucket

CLUB_CHART_LIMIT = 15
OPPONENT_CHART_LIMIT = 15


def _trend(report: AttendanceReport) -> dict[str, object]:
    selected = report.filters.season_id
    return {
        "points": [
            {
                "season": point.season.season_code,
                "mean": point.season.summary.mean,
                "median": point.season.summary.median,
                "q1": point.season.summary.q1,
                "q3": point.season.summary.q3,
                "movingAverage": point.moving_average,
                "known": point.season.summary.known,
                "played": point.season.summary.played,
                "selected": point.season.season_id == selected,
            }
            for point in report.trend.points
        ]
    }


def _heatmap(report: AttendanceReport) -> dict[str, object]:
    cells = report.calendar.heatmap if report.calendar else ()
    return {
        "weekdays": list(WEEKDAY_LABELS),
        "cells": [
            {
                "weekday": cell.weekday,
                "hour": cell.hour,
                "mean": cell.mean,
                "known": cell.known,
                "played": cell.played,
            }
            for cell in cells
        ],
    }


def _histogram(report: AttendanceReport) -> list[dict[str, object]]:
    science = report.science
    if science is None or science.distribution is None:
        return []
    return [
        {"label": item.label, "count": item.count, "share": item.share}
        for item in science.distribution.histogram
    ]


def _clubs(report: AttendanceReport) -> list[dict[str, object]]:
    return [
        {
            "name": row.club.club_name,
            "mean": row.club.summary.mean,
            "known": row.club.summary.known,
        }
        for row in report.ranking[:CLUB_CHART_LIMIT]
    ]


def _cities(report: AttendanceReport) -> list[dict[str, object]]:
    if report.cities is None:
        return []
    return [
        {
            "name": item.city,
            "total": item.total,
            "mean": item.mean,
            "median": item.median,
            "mode": item.mode,
            "known": item.known,
        }
        for item in report.cities.chart_cities
    ]


def _city_details(report: AttendanceReport) -> list[dict[str, object]]:
    cities = report.cities
    if cities is None:
        return []
    return [
        {
            "name": item.city,
            "seasons": [
                {
                    "season": row.season_code,
                    "total": row.total,
                    "mean": row.mean,
                    "median": row.median,
                    "known": row.known,
                    "played": row.played,
                }
                for row in cities.seasons_of(item.city)
            ],
            "competitions": [
                {"name": row.competition, "total": row.total, "mean": row.mean, "known": row.known}
                for row in cities.competitions_of(item.city)
            ],
            "venues": [
                {"name": row.venue_name, "total": row.total, "mean": row.mean, "known": row.known}
                for row in cities.venues_of(item.city)
            ],
        }
        for item in cities.chart_cities
    ]


def _buckets(buckets: Sequence[CalendarBucket]) -> list[dict[str, object]]:
    return [
        {"label": item.label, "mean": item.mean, "known": item.known, "played": item.played}
        for item in buckets
    ]


def _calendar_buckets(report: AttendanceReport, name: str) -> list[dict[str, object]]:
    if report.calendar is None:
        return []
    return _buckets(getattr(report.calendar, name))


def _opponents(report: AttendanceReport) -> list[dict[str, object]]:
    section = report.opponents
    if section is None or section.requires_club:
        return []
    return [
        {
            "name": row.opponent.opponent_name,
            "mean": row.opponent.mean,
            "difference": row.difference,
        }
        for row in section.rows[:OPPONENT_CHART_LIMIT]
    ]


def _coverage(report: AttendanceReport) -> list[dict[str, object]]:
    return [
        {
            "season": point.season.season_code,
            "known": point.season.summary.known,
            "played": point.season.summary.played,
            "coverage": (
                None
                if point.season.summary.coverage is None
                else round(point.season.summary.coverage * 100, 1)
            ),
        }
        for point in report.trend.points
    ]


def _weekday_effect(report: AttendanceReport) -> list[dict[str, object]]:
    if report.science is None:
        return []
    return [
        {"label": item.label, "mean": item.mean, "n": item.n}
        for item in report.science.weekdays
    ]


def attendance_charts_payload(report: AttendanceReport) -> dict[str, object]:
    return {
        "trend": _trend(report),
        "heatmap": _heatmap(report),
        "histogram": _histogram(report),
        "clubs": _clubs(report),
        "cities": _cities(report),
        "cityDetails": _city_details(report),
        "months": _calendar_buckets(report, "months"),
        "weekdays": _calendar_buckets(report, "weekdays"),
        "hours": _calendar_buckets(report, "hours"),
        "opponents": _opponents(report),
        "coverage": _coverage(report),
        "weekdayEffect": _weekday_effect(report),
    }
