from __future__ import annotations

from dataclasses import dataclass

from flask import Flask

from ehf.interface.branding import NAZWA_PROJEKTU, ODZNAKA_PROJEKTU, PODTYTUL_PROJEKTU
from ehf.interface.pages import KLUCZE_DANYCH


@dataclass(frozen=True)
class PozycjaMenu:
    klucz: str
    etykieta: str
    punkt_koncowy: str
    ikona: str | None = None


GORNY_PASEK: tuple[PozycjaMenu, ...] = (
    PozycjaMenu("start", "Start", "panel.start"),
    PozycjaMenu("mecze", "Data", "panel.match_list"),
    PozycjaMenu("import", "Import", "panel.import_danych"),
    PozycjaMenu("kontrola", "Kontrola danych", "panel.kontrola_danych"),
    PozycjaMenu("logi", "Logi", "panel.logi_aplikacji"),
)

SIDEBAR: tuple[tuple[str, tuple[PozycjaMenu, ...]], ...] = (
    (
        "Data",
        (
            PozycjaMenu("sezony", "Seasons", "panel.lista_sezonow", "◫"),
            PozycjaMenu("rozgrywki", "Competitions", "panel.lista_rozgrywek", "⌘"),
            PozycjaMenu("druzyny", "Teams", "panel.lista_druzyn", "▣"),
            PozycjaMenu("zawodnicy", "Players", "panel.lista_zawodnikow", "◎"),
            PozycjaMenu("sklady", "Squads", "panel.lista_skladow", "☰"),
            PozycjaMenu("mecze", "Matches", "panel.match_list", "◈"),
            PozycjaMenu("protokol", "Match sheet", "panel.match_sheet", "✎"),
            PozycjaMenu("tabele", "Standings", "panel.lista_tabel", "▤"),
            PozycjaMenu("strzelcy", "Scorers", "panel.lista_strzelcow", "★"),
            PozycjaMenu("hale", "Venues", "panel.lista_hal", "⌂"),
            PozycjaMenu("sedziowie", "Referees", "panel.lista_sedziow", "⚑"),
        ),
    ),
    (
        "Import / eksport",
        (
            PozycjaMenu("import", "Import danych", "panel.import_danych", "⇪"),
            PozycjaMenu("historia_importow", "Historia importów", "panel.historia_importow", "⇄"),
            PozycjaMenu("eksport_danych", "Eksport danych", "panel.eksport_danych", "⇩"),
        ),
    ),
    (
        "Narzędzia",
        (
            PozycjaMenu("anomalie", "Anomalie danych", "panel.anomalie", "!"),
            PozycjaMenu("walidacja", "Walidacja danych", "panel.walidacja", "✓"),
            PozycjaMenu("logi_aplikacji", "Logi aplikacji", "panel.logi_aplikacji", "≡"),
        ),
    ),
)


def zarejestruj_kontekst_nawigacji(aplikacja: Flask) -> None:
    @aplikacja.context_processor
    def wstrzyknij_menu() -> dict[str, object]:
        return {
            "gorny_pasek": GORNY_PASEK,
            "sidebar": SIDEBAR,
            "klucze_danych": KLUCZE_DANYCH,
            "nazwa_projektu": NAZWA_PROJEKTU,
            "podtytul_projektu": PODTYTUL_PROJEKTU,
            "odznaka_projektu": ODZNAKA_PROJEKTU,
        }
