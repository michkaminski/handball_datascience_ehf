from __future__ import annotations

from dataclasses import dataclass

# TE/TBP/TYC/TRC/FRP repeat another event; GKS/SUBST/TPT are goalkeeper swaps and substitutions
SKIPPED_CODES = frozenset({"CLOCK", "TBP", "TYC", "TRC", "TE", "FRP", "GKS", "SUBST", "TPT"})

SHOT_TITLES = {
    "GOAL": "Goal",
    "SAVE": "Save",
    "MISS": "Miss",
    "POST": "Post",
    "BLC": "Block",
}

ACTION_TITLES = {
    "TO": "Turnover",
    "TMS": "2 min",
    "YC": "Yellow",
    "RC": "Red",
    "TOUT": "Timeout",
    "ST": "Steal",
    "RFP": "7m",
}

SHOT_FILTERS = {
    "GOAL": "goal",
    "SAVE": "save",
    "MISS": "shot",
    "POST": "shot",
    "BLC": "shot",
}

ACTION_FILTERS = {
    "TO": "turnover",
    "TMS": "card",
    "YC": "card",
    "RC": "card",
    "TOUT": "timeout",
    "RFP": "penalty",
    "ST": "other",
}

ZONE_LABELS = {
    "LW": "left wing",
    "RW": "right wing",
    "PTY": "7 m",
    "LSD": "6 m · left",
    "CSD": "6 m · centre",
    "RSD": "6 m · right",
    "LLD": "9 m · left",
    "CLD": "9 m · centre",
    "RLD": "9 m · right",
}

SHOT_TONES = {
    "GOAL": "goal",
    "SAVE": "save",
    "MISS": "shot",
    "POST": "shot",
    "BLC": "shot",
}

ACTION_TONES = {
    "TO": "turnover",
    "TMS": "card",
    "YC": "card",
    "RC": "red",
    "TOUT": "timeout",
    "ST": "steal",
    "RFP": "penalty",
}


@dataclass(frozen=True)
class PlayParticipant:
    side: str
    role_code: str | None
    shirt_number: str | None
    first_name: str | None
    last_name: str | None
    person_id: int | None

    @property
    def label(self) -> str:
        name = " ".join(part for part in (self.first_name, self.last_name) if part).strip()
        if self.shirt_number and name:
            return f"{self.shirt_number} {name}"
        return name or self.shirt_number or ""


@dataclass(frozen=True)
class PlayAction:
    seq: int
    action_code: str
    period_code: str | None
    clock_raw: str | None
    result_code: str | None
    shot_zone: str | None
    action_add: str | None
    score_home: int
    score_away: int
    participants: tuple[PlayParticipant, ...]
    seconds: int | None = None


@dataclass(frozen=True)
class PlayPerson:
    person_id: int | None
    label: str


@dataclass(frozen=True)
class PlayRow:
    kind: str
    side: str | None = None
    clock: str = ""
    score: str = ""
    lead_text: str = ""
    lead_side: str = "tie"
    title: str = ""
    zone: str = ""
    player: PlayPerson | None = None
    assist: PlayPerson | None = None
    keeper: PlayPerson | None = None
    shot_by: PlayPerson | None = None
    tone: str = ""
    filter_key: str = ""
    detail: str = ""
    layout: str = ""
    person_ids: tuple[int, ...] = ()
    minute: int | None = None
    scored: str | None = None
    fast_break: bool = False
    seven: bool = False

    @property
    def people_key(self) -> str:
        return ",".join(str(person_id) for person_id in self.person_ids)


def is_visible(action: PlayAction) -> bool:
    if action.action_code in SKIPPED_CODES:
        return False
    if action.action_code == "TOUT" and action.action_add == "END":
        return False
    return True


def clock_label(clock_raw: str | None) -> str:
    seconds = period_seconds(clock_raw)
    if seconds is None:
        return (clock_raw or "").strip()
    sign = "-" if seconds < 0 else ""
    minutes, secs = divmod(abs(seconds), 60)
    return f"{sign}{minutes:02d}:{secs:02d}"


def period_seconds(clock_raw: str | None) -> int | None:
    text = (clock_raw or "").strip()
    if ":" not in text:
        return None
    minutes_text, seconds_text = text.split(":", 1)
    try:
        minutes = int(minutes_text)
        seconds = int(seconds_text)
    except ValueError:
        return None
    if seconds < 0 or seconds >= 60:
        return None
    if abs(minutes) > 35:
        return None
    return minutes * 60 + seconds


def lead_of(home: int, away: int) -> tuple[str, str]:
    difference = home - away
    if difference > 0:
        return f"+{difference}", "home"
    if difference < 0:
        return f"+{-difference}", "away"
    return "0", "tie"


def event_row(action: PlayAction) -> PlayRow:
    player, assist, keeper, shot_by, side = _actors(action)
    filter_key = _filter_key(action)
    lead_text, lead_side = lead_of(action.score_home, action.score_away)
    people = tuple(
        person.person_id
        for person in (player, assist, keeper, shot_by)
        if person is not None and person.person_id is not None
    )
    return PlayRow(
        kind="event",
        side=side,
        clock=clock_label(action.clock_raw),
        score=f"{action.score_home}:{action.score_away}",
        lead_text=lead_text,
        lead_side=lead_side,
        title=_title(action),
        zone=_zone(action),
        player=player,
        assist=assist,
        keeper=keeper,
        shot_by=shot_by,
        tone=_tone(action),
        filter_key=filter_key,
        layout=_layout(filter_key),
        person_ids=people,
    )


def _actors(
    action: PlayAction,
) -> tuple[PlayPerson | None, PlayPerson | None, PlayPerson | None, PlayPerson | None, str | None]:
    scorer = _first(action, "SCR")
    keeper = _first(action, "GK")
    assist = _first(action, "ASSIST")
    if action.action_code == "SHOT" and action.result_code == "SAVE" and keeper is not None:
        shot_by = None if _same(scorer, keeper) else _person(scorer)
        return _person(keeper), None, None, shot_by, keeper.side
    if action.action_code == "SHOT" and action.result_code == "GOAL":
        main = scorer or keeper
        conceded = None if scorer is None or _same(keeper, scorer) else _person(keeper)
        helper = None if _same(assist, main) else _person(assist)
        side = None if main is None else main.side
        return _person(main), helper, conceded, None, side
    if action.action_code == "SHOT":
        main = scorer or keeper
        side = None if main is None else main.side
        return _person(main), None, None, None, side
    named = _first(action, "TO") or _first(action, "ST") or _labelled(action)
    side = None if named is None else named.side
    return _person(named), None, None, None, side


def _filter_key(action: PlayAction) -> str:
    if action.action_code == "SHOT":
        return SHOT_FILTERS.get(action.result_code or "", "shot")
    return ACTION_FILTERS.get(action.action_code, "other")


def _layout(filter_key: str) -> str:
    if filter_key == "goal":
        return "goal"
    if filter_key == "save":
        return "save"
    return "line"


def _title(action: PlayAction) -> str:
    if action.action_code == "SHOT":
        return SHOT_TITLES.get(action.result_code or "", "Shot")
    return ACTION_TITLES.get(action.action_code, action.action_code)


def _tone(action: PlayAction) -> str:
    if action.action_code == "SHOT":
        return SHOT_TONES.get(action.result_code or "", "shot")
    return ACTION_TONES.get(action.action_code, "neutral")


def _zone(action: PlayAction) -> str:
    # FB/FBL/FBR/FBC only say "fast break", which the row shows on its own
    if action.action_code != "SHOT" or not action.shot_zone or action.shot_zone.startswith("FB"):
        return ""
    return ZONE_LABELS.get(action.shot_zone, action.shot_zone)


def _person(participant: PlayParticipant | None) -> PlayPerson | None:
    if participant is None or not participant.label:
        return None
    return PlayPerson(person_id=participant.person_id, label=participant.label)


def _same(left: PlayParticipant | None, right: PlayParticipant | None) -> bool:
    if left is None or right is None:
        return False
    if left.person_id is not None and left.person_id == right.person_id:
        return True
    return left.label == right.label and bool(left.label)


def _labelled(action: PlayAction) -> PlayParticipant | None:
    for person in action.participants:
        if person.label:
            return person
    if action.participants:
        return action.participants[0]
    return None


def _first(action: PlayAction, role: str) -> PlayParticipant | None:
    for person in action.participants:
        if person.role_code == role:
            return person
    return None
