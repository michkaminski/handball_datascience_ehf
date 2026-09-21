# Baza EHF

Flask czyta schemat `ehf` z `../imports/sql/001_ehf_schema.sql`. Importer zapisuje, panel tylko odczytuje. To nie jest baza ZPRP.

Schemat: `CREATE SCHEMA ehf`.

## Wynik meczu

`ehf.match.result_type` (może być puste):

| Wartość | Znaczenie |
|---|---|
| `normal` | zwykły wynik |
| `walkover` | walkower (`is_walkover`) |
| `extra_time` | dogrywka (`went_to_extra_time`) |
| `penalties` | karne (`went_to_seven_meters`) |

`status`: `played` | `awarded` | `scheduled_or_no_result`.

## Strony → tabele

| Strona | Szkic | Tabele |
|---|---|---|
| Sezony | [strony/sezony.md](strony/sezony.md) | `ehf.season` |
| Rozgrywki | [strony/rozgrywki.md](strony/rozgrywki.md) | `ehf.competition`, `ehf.competition_edition` |
| Drużyny | [strony/druzyny.md](strony/druzyny.md) | `ehf.club`, `ehf.club_edition` |
| Zawodnicy | [strony/zawodnicy.md](strony/zawodnicy.md) | `ehf.person`, `ehf.player_edition` |
| Składy | [strony/sklady.md](strony/sklady.md) | `ehf.match_lineup`, `ehf.player_edition` |
| Mecze | [strony/mecze.md](strony/mecze.md) | `ehf.match`, `ehf.match_period`, `ehf.match_team` |
| Tabele | [strony/tabele.md](strony/tabele.md) | wyliczane z `ehf.match` (brak osobnej tabeli) |
| Strzelcy | [strony/strzelcy.md](strony/strzelcy.md) | `ehf.match_player_stat`, `ehf.match_lineup`, `ehf.person` |
| Hale | [strony/hale.md](strony/hale.md) | `ehf.venue` |
| Sędziowie | [strony/sedziowie.md](strony/sedziowie.md) | `ehf.match_official` (`role = 'referee'`) |

Karty: mecz → `ehf.match` + składy/sędziowie; zawodnik → `ehf.person`; hala → `ehf.venue`.

SQL zostaje w `imports/sql/`. Warstwa `infrastructure` będzie jedynym miejscem zapytań.
