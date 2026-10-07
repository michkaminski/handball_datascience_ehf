"""Wording of the match summary print in Polish (default) and English."""

from __future__ import annotations

from datetime import datetime

from ehf.domain.match_summary import Headline
from ehf.interface.plurals import polish_count

LANGUAGES = ("pl", "en")
DEFAULT_LANGUAGE = "pl"

TEXTS: dict[str, dict[str, str]] = {
    "pl": {
        "title": "Podsumowanie meczu",
        "print": "Drukuj / zapisz jako PDF",
        "print_note": "Jedna strona A4 · wyłącz nagłówki i stopki przeglądarki · włącz grafikę tła.",
        "ht": "do przerwy",
        "ht_short": "przerwa",
        "after_shootout": "po rzutach karnych",
        "after_extra_shootout": "po dogrywce i rzutach karnych",
        "after_extra": "po dogrywce",
        "group": "Grupa",
        "flow": "Przebieg meczu",
        "ahead": "prowadzi {team}",
        "win_probability": "szanse na wygraną",
        "win_probability_of": "Szanse na wygraną: {team}",
        "run": "seria",
        "timeout": "czas",
        "suspension": "kara 2 min",
        "red": "CZ",
        "moments": "Kluczowe momenty",
        "moments_note": "(największe zmiany szans na wygraną)",
        "comparison": "Porównanie drużyn",
        "average": "Ø średnia: {label}",
        "phases": "Fazy meczu",
        "per_ten": "Bramki w 10-minutowych odcinkach",
        "et": "Dogr.",
        "more_players": "W przewadze",
        "fewer_players": "W osłabieniu",
        "timeouts": "Czasy",
        "timeouts_note": "Czasy – wynik, potem bramki 3 min przed → po",
        "shooting": "rzuty według stref · bramkarze",
        "goalkeeper": "Bramkarz",
        "saves": "Obrony",
        "no_keeper": "brak bramkarza w zapisie meczu",
        "goalkeepers": "bramkarze",
        "total": "Razem",
        "variant_full": "Pełna",
        "variant_short": "Skrócona",
        "biggest_lead_key": "najwyższe prowadzenie",
        "lead_note": "Najwyższa różnica bramek w każdej minucie – słupek w górę: prowadzą gospodarze, w dół: goście",
        "scorers": "strzelcy",
        "no": "Nr",
        "player": "Zawodnik",
        "goals_shots": "B/R",
        "seven_m": "7 m",
        "assists": "As",
        "turnovers_short": "Str",
        "goals_when": "Kiedy padały bramki",
        "no_goal": "Bez bramki",
        "assists_only": "Tylko asysty",
        "ties": "Remisy",
        "lead_changes": "Zmiany prowadzenia",
        # comparison rows
        "row_shooting": "Skuteczność rzutów",
        "row_attack": "Skuteczność ataku",
        "row_saving": "Obrony bramkarzy",
        "row_seven": "Bramki z 7 m",
        "row_fast_breaks": "Bramki z kontry",
        "row_assisted": "Bramki po asyście",
        "row_turnovers": "Straty",
        "row_steals": "Przechwyty",
        "row_blocks": "Bloki",
        "row_suspensions": "Kary 2 min",
        # zone groups
        "zone_wings": "Skrzydła",
        "zone_six": "6 m",
        "zone_nine": "9 m",
        "zone_seven": "7 m",
        "zone_fast_break": "Kontra",
        # facts
        "fact_front": "Czas prowadzenia",
        "fact_biggest_lead": "Najwyższe prowadzenie",
        "fact_best_run": "Najlepsza seria",
        "fact_drought": "Najdłużej bez bramki",
        "fact_last_ten": "Ostatnie 10 minut",
    },
    "en": {
        "title": "Match summary",
        "print": "Print / save as PDF",
        "print_note": "One A4 page · turn off the browser's headers and footers · background graphics on.",
        "ht": "HT",
        "ht_short": "HT",
        "after_shootout": "after 7 m shootout",
        "after_extra_shootout": "after extra time and 7 m shootout",
        "after_extra": "after extra time",
        "group": "Group",
        "flow": "How the match went",
        "ahead": "{team} ahead",
        "win_probability": "win probability",
        "win_probability_of": "{team} win probability",
        "run": "run",
        "timeout": "timeout",
        "suspension": "suspension",
        "red": "R",
        "moments": "Key moments",
        "moments_note": "(biggest swings in win probability)",
        "comparison": "Team comparison",
        "average": "Ø average, {label}",
        "phases": "Phases of the match",
        "per_ten": "Goals per 10 minutes",
        "et": "ET",
        "more_players": "More players",
        "fewer_players": "Fewer players",
        "timeouts": "Timeouts",
        "timeouts_note": "Timeouts – score, then goals 3 minutes before → after",
        "shooting": "shots by zone · goalkeepers",
        "goalkeeper": "Goalkeeper",
        "saves": "Saves",
        "no_keeper": "no goalkeeper in the feed",
        "goalkeepers": "goalkeepers",
        "total": "Total",
        "variant_full": "Full",
        "variant_short": "Short",
        "biggest_lead_key": "biggest lead",
        "lead_note": "Biggest goal difference in every minute – bar up: home team ahead, down: away team ahead",
        "scorers": "scorers",
        "no": "No",
        "player": "Player",
        "goals_shots": "G/Sh",
        "seven_m": "7 m",
        "assists": "As",
        "turnovers_short": "TO",
        "goals_when": "When the goals came",
        "no_goal": "No goal",
        "assists_only": "Assists only",
        "ties": "Ties",
        "lead_changes": "Lead changes",
        "row_shooting": "Shooting",
        "row_attack": "Attack efficiency",
        "row_saving": "Goalkeeper saves",
        "row_seven": "7 m goals",
        "row_fast_breaks": "Fast-break goals",
        "row_assisted": "Assisted goals",
        "row_turnovers": "Turnovers",
        "row_steals": "Steals",
        "row_blocks": "Blocks",
        "row_suspensions": "2-min suspensions",
        "zone_wings": "Wings",
        "zone_six": "6 m",
        "zone_nine": "9 m",
        "zone_seven": "7 m",
        "zone_fast_break": "Fast break",
        "fact_front": "In front",
        "fact_biggest_lead": "Biggest lead",
        "fact_best_run": "Best run",
        "fact_drought": "Longest without a goal",
        "fact_last_ten": "Last 10 minutes",
    },
}

PL_WEEKDAYS = ("pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz.")


def language(value: str | None) -> str:
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def headline_text(item: Headline, names: dict[str, str], lang: str) -> str:
    v = item.values
    winner = names[item.winner] if item.winner else ""
    loser = names["away" if item.winner == "home" else "home"] if item.winner else ""
    if lang == "pl":
        ties = polish_count(int(v.get("ties", 0)), "raz", "razy", "razy")
        changes = polish_count(int(v.get("changes", 0)), "raz", "razy", "razy")
        story = f"wynik wyrównywano {ties}, a prowadzenie zmieniało się {changes}"
        if item.kind == "shootout":
            extra = " po dogrywce" if v["extra_time"] else ""
            return f"{winner} wygrywa w rzutach karnych po remisie {v['regular']}{extra} – {story}."
        if item.kind == "draw":
            return f"{names['home']} i {names['away']} remisują {v['score']} – {story}."
        if item.kind == "comeback":
            return (
                f"{winner} przegrywa {v['behind']} w {v['minute']}. minucie, "
                f"ale wygrywa {v['score']} po końcówce {v['finish']}."
            )
        if item.kind == "control":
            lead = f"; najwyższe prowadzenie +{v['lead']} w {v['lead_minute']}. minucie" if v["lead"] else ""
            return f"{winner} prowadzi przez {v['front']} z {v['total']} minut i wygrywa {v['score']}{lead}."
        if item.kind == "go_ahead":
            return f"{winner} wygrywa {v['score']} – decydujące prowadzenie daje {v['scorer']} w {v['minute']}. minucie ({v['at']})."
        return f"{winner} wygrywa z {loser} {v['score']}."

    ties = _english_count(int(v.get("ties", 0)), "tie", "ties")
    changes = _english_count(int(v.get("changes", 0)), "lead change", "lead changes")
    if item.kind == "shootout":
        extra = " in extra time" if v["extra_time"] else ""
        return f"{winner} won the 7 m shootout after {v['regular']}{extra} – {ties} and {changes} on the way."
    if item.kind == "draw":
        return f"{names['home']} and {names['away']} drew {v['score']} after {ties} and {changes}."
    if item.kind == "comeback":
        return f"{winner} trailed {v['behind']} at {v['clock']} and won {v['score']} with a {v['finish']} finish."
    if item.kind == "control":
        lead = f", biggest lead +{v['lead']} at {v['lead_clock']}" if v["lead"] else ""
        return f"{winner} were in front for {v['front']} of {v['total']} minutes and won {v['score']}{lead}."
    if item.kind == "go_ahead":
        return f"{winner} won {v['score']}: {v['scorer']} put them ahead for good at {v['clock']} ({v['at']})."
    return f"{winner} beat {loser} {v['score']}."


def kickoff_text(value: datetime | None, lang: str) -> str:
    if value is None:
        return ""
    if lang == "pl":
        return f"{PL_WEEKDAYS[value.weekday()]} {value:%d.%m.%Y, %H:%M}"
    return value.strftime("%a %d %b %Y, %H:%M")


def spectators_text(value: int | None, lang: str) -> str:
    if not value:
        return ""
    number = f"{value:,}".replace(",", " ")
    if lang == "pl":
        return polish_count(value, "widz", "widzów", "widzów").replace(str(value), number, 1)
    return f"{number} spectators"


def decimal_text(value: str, lang: str) -> str:
    return value.replace(".", ",") if lang == "pl" else value


def _english_count(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"
