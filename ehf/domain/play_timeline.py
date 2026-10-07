from __future__ import annotations

from dataclasses import dataclass, replace

from ehf.domain.play_by_play import PlayAction, PlayRow, event_row, is_visible
from ehf.domain.play_charts import PlayCharts, build_play_charts

PERIOD_TITLES = {
    "H1": "1st half",
    "H2": "2nd half",
    "OT1": "Extra time 1",
    "OT2": "Extra time 2",
    "ET1": "Extra time 1",
    "ET2": "Extra time 2",
    "PSO": "7m shootout",
    "SO": "7m shootout",
    "P7": "7m shootout",
}
PERIOD_ORDER = {"H1": 0, "H2": 1, "OT1": 2, "ET1": 2, "OT2": 3, "ET2": 3, "PSO": 4, "SO": 4, "P7": 4}
SHOOTOUT = frozenset({"PSO", "SO", "P7"})
FAST_BREAK_ZONES = frozenset({"FB", "FBL", "FBR", "FBC"})
# a divider with the score every ten minutes of play (half-time and full time have their own rows)
MARKS = (10 * 60, 20 * 60, 40 * 60, 50 * 60)


@dataclass(frozen=True)
class PlayTimeline:
    rows: tuple[PlayRow, ...]
    charts: PlayCharts
    home_name: str
    away_name: str

    @property
    def has_events(self) -> bool:
        return any(row.kind == "event" for row in self.rows)


def present_timeline(
    actions: tuple[PlayAction, ...],
    home_name: str,
    away_name: str,
    half_time: str = "",
) -> PlayTimeline:
    return PlayTimeline(
        rows=tuple(_rows(_cleaned(actions))),
        charts=build_play_charts(actions, half_time),
        home_name=home_name,
        away_name=away_name,
    )


def _cleaned(actions: tuple[PlayAction, ...]) -> list[PlayAction]:
    """Visible actions without the feed's repeats (2021-22 sends a fast-break shot once per FB zone code)."""
    kept: list[PlayAction] = []
    moment: tuple | None = None
    seen: set[tuple] = set()
    for action in actions:
        if not is_visible(action):
            continue
        here = (action.seconds, action.score_home, action.score_away)
        if here != moment:
            moment, seen = here, set()
        zone = "FB" if action.shot_zone in FAST_BREAK_ZONES else action.shot_zone
        key = (action.action_code, action.result_code, zone, action.action_add, action.participants)
        if key in seen:
            continue
        seen.add(key)
        kept.append(action)
    return kept


def _rows(actions: list[PlayAction]) -> list[PlayRow]:
    rows: list[PlayRow] = []
    period: str | None = None
    marks = list(MARKS)
    previous = (0, 0)
    last_play = _last_play(actions)
    for action in actions:
        seconds = action.seconds
        # periods only move forward: the feed tags a few late events with an earlier period
        if action.action_code != "ENDP" and _order(action.period_code) > _order(period):
            period = action.period_code
            rows.append(PlayRow(kind="period", title=PERIOD_TITLES.get(period, period)))
        if action.action_code == "STARTP":
            previous = (action.score_home, action.score_away)
            continue
        while marks and seconds is not None and seconds > marks[0] and period not in SHOOTOUT:
            mark = marks.pop(0)
            rows.append(PlayRow(kind="tick", clock=f"{mark // 60}'", score=f"{previous[0]}:{previous[1]}"))
        score = (action.score_home, action.score_away)
        if action.action_code == "ENDP":
            title = _end_title(action, last_play)
            if title:
                rows.append(PlayRow(kind="close", title=title, score=f"{score[0]}:{score[1]}"))
            previous = score
            continue
        if action.action_code == "TO" and action.action_add == "FB":
            _mark_fast_break(rows, action)
            continue
        row = event_row(action)
        scored = None
        if score[0] > previous[0]:
            scored = "home"
        elif score[1] > previous[1]:
            scored = "away"
        rows.append(
            replace(
                row,
                clock="7m" if period in SHOOTOUT else _clock(seconds) if seconds is not None else row.clock,
                minute=seconds // 60 + 1 if seconds is not None and period not in SHOOTOUT else None,
                scored=scored,
                fast_break=action.shot_zone in FAST_BREAK_ZONES,
                seven=action.shot_zone == "PTY",
            )
        )
        previous = score
    return rows


def _order(period: str | None) -> int:
    return PERIOD_ORDER.get(period or "", -1)


def _last_play(actions: list[PlayAction]) -> int:
    return max(
        (a.seconds or 0 for a in actions if a.action_code != "ENDP" and a.period_code not in SHOOTOUT),
        default=0,
    )


def _end_title(action: PlayAction, last_play: int) -> str:
    if action.period_code == "H1":
        return "Half-time"
    if action.action_add == "END":
        return "Full time"
    if action.period_code == "H2" and last_play > 60 * 60:
        return "End of regular time"
    if action.period_code in ("OT1", "ET1"):
        return "End of extra time 1"
    return ""


def _mark_fast_break(rows: list[PlayRow], action: PlayAction) -> None:
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if row.kind != "event":
            continue
        if row.filter_key in ("goal", "save", "shot") and row.clock == _clock(action.seconds or 0):
            rows[index] = replace(row, fast_break=True)
        return


def _clock(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
