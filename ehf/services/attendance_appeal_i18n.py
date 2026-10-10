from __future__ import annotations

import re
from collections.abc import Callable

FEATURE_LABELS = {
    "weekend": "Weekend match (Saturday–Sunday)",
    "hour": "Kickoff hour (standardised)",
    "host_form": "Home form — mean points from the last 5 matches",
    "opponent_form": "Visitor form — mean points from the last 5 matches",
    "host_position": "Home standing before the match (0 = leader, 1 = last)",
    "opponent_position": "Visitor standing before the match (0 = leader, 1 = last)",
    "playoff": "Knockout / play-off phase",
    "final": "Final or medal match",
}
GROUP_LABELS = {
    "host": "Home club (H)",
    "opponent": "Visitor (R)",
    "season": "Season (S)",
    "competition": "Competition (L)",
    "host_season": "Home club × season (HS)",
    "opponent_season": "Visitor × season (RS)",
}
ISSUE_LABELS = {
    "duplikat": "Duplicate match (same id, or same day and pair of teams)",
    "brak_frekwencji": "Attendance unknown (NULL) — excluded, never counted as 0",
    "zero_widzow": "Zero spectators (behind closed doors) — excluded from the appeal model",
    "teren_neutralny": "Neutral venue (tournament) — excluded",
    "brak_pojemnosci": "Venue capacity unknown — spectator-count analysis only",
    "przekroczona_pojemnosc": "More spectators than seats — inconsistent capacity",
    "podejrzana_wartosc": "At least 1.5× more spectators than seats — suspicious value",
    "odstajaca": "Outlier relative to the home club's typical attendance (robust z-score)",
}
STATISTIC_LABELS = {
    "Średnia liczba widzów": "Mean spectators",
    "Odchylenie standardowe": "Standard deviation",
    "Mediana": "Median",
    "Percentyl 90": "90th percentile",
    "Odsetek meczów < 100 widzów": "Share of matches with < 100 spectators",
    "Średnie wypełnienie": "Mean fill rate",
    "Odchylenie standardowe wypełnienia": "Fill rate standard deviation",
    "Odsetek meczów z wypełnieniem ≥ 95%": "Share of matches with fill rate ≥ 95%",
    "Odsetek meczów z wypełnieniem ≤ 10%": "Share of matches with fill rate ≤ 10%",
    "Mediana wypełnienia": "Median fill rate",
}
UNIT_LABELS = {"p.p. wypełnienia": "pp of fill rate", "% widzów": "% spectators"}
SCALE_LABELS = {"wypełnienie hali": "fill rate", "log10(liczba widzów)": "log10(spectators)"}
NOTE_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str]], ...] = (
    (re.compile(r"tylko (\d+) mecze/meczów jako rywal"), lambda m: f"only {m.group(1)} matches as visitor"),
    (re.compile(r"szeroki przedział 95% \((\d+) pkt\)"), lambda m: f"wide 95% interval ({m.group(1)} points)"),
    (re.compile(r"ostrzeżenie zbieżności MCMC"), lambda m: "MCMC convergence warning"),
    (
        re.compile(r"(\w+): poziom spoza danych — losowany z rozkładu populacji"),
        lambda m: f"{m.group(1)}: level not in the data — drawn from the population distribution",
    ),
    (
        re.compile(r"model liczby widzów nie zna limitu miejsc — prawdopodobieństwa kompletu są przybliżeniem"),
        lambda m: "the spectator-count model does not know the seat limit — full-house probabilities are approximate",
    ),
    (re.compile(r"średnia frekwencja gospodarza w danych treningowych"), lambda m: "home club mean attendance in the training data"),
    (re.compile(r"za mało sezonów do walidacji chronologicznej"), lambda m: "too few seasons for chronological validation"),
    (re.compile(r"pominięto na żądanie"), lambda m: "skipped on request"),
)


def translate_text(text: str) -> str:
    for pattern, replacement in NOTE_PATTERNS:
        if pattern.fullmatch(text):
            return pattern.sub(replacement, text)
    return text


def translate_panel(payload: dict[str, object]) -> dict[str, object]:
    for item in _list(payload.get("coefficients")):
        item["label"] = FEATURE_LABELS.get(str(item.get("name")), item.get("label"))
        item["effect_unit"] = UNIT_LABELS.get(str(item.get("effect_unit")), item.get("effect_unit"))
    model = payload.get("model")
    if isinstance(model, dict):
        translate_model(model)
    for club in _list(payload.get("clubs")):
        translate_club(club)
    quality = payload.get("quality")
    if isinstance(quality, dict):
        quality["issue_labels"] = ISSUE_LABELS
    ppc = payload.get("ppc")
    if isinstance(ppc, dict):
        ppc["scale"] = SCALE_LABELS.get(str(ppc.get("scale")), ppc.get("scale"))
        for check in _list(ppc.get("checks")):
            check["statistic"] = STATISTIC_LABELS.get(str(check["statistic"]), check["statistic"])
    backtest = payload.get("backtest")
    if isinstance(backtest, dict):
        for field in ("baseline_label", "reason"):
            if isinstance(backtest.get(field), str):
                backtest[field] = translate_text(str(backtest[field]))
    return payload


def translate_model(model: dict[str, object]) -> None:
    for group in _list(model.get("groups")):
        group["label"] = GROUP_LABELS.get(str(group.get("name")), group.get("label"))
    features = model.get("features")
    if isinstance(features, dict) and isinstance(features.get("names"), list):
        features["labels"] = [FEATURE_LABELS.get(str(name), str(name)) for name in features["names"]]


def translate_club(club: dict[str, object]) -> None:
    away = club.get("away")
    if isinstance(away, dict) and isinstance(away.get("notes"), list):
        away["notes"] = [translate_text(str(note)) for note in away["notes"]]


def translate_forecast(result: dict[str, object]) -> dict[str, object]:
    if isinstance(result.get("notes"), list):
        result["notes"] = [translate_text(str(note)) for note in result["notes"]]  # type: ignore[union-attr]
    return result


def _list(value: object) -> list[dict[str, object]]:
    return value if isinstance(value, list) else []
