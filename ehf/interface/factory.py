from __future__ import annotations

from pathlib import Path

from flask import Flask

from ehf.infrastructure.competition_list_reader import PsycopgCompetitionListReader
from ehf.infrastructure.connection import open_connection
from ehf.infrastructure.match_detail_reader import PsycopgMatchDetailReader
from ehf.infrastructure.match_list_reader import PsycopgMatchListReader
from ehf.infrastructure.news_reader import PsycopgNewsReader
from ehf.infrastructure.player_detail_reader import PsycopgPlayerDetailReader
from ehf.infrastructure.player_list_reader import PsycopgPlayerListReader
from ehf.infrastructure.referee_detail_reader import PsycopgRefereeDetailReader
from ehf.infrastructure.referee_list_reader import PsycopgRefereeListReader
from ehf.infrastructure.scorer_list_reader import PsycopgScorerListReader
from ehf.infrastructure.season_list_reader import PsycopgSeasonListReader
from ehf.infrastructure.match_sheet_reader import PsycopgMatchSheetReader
from ehf.infrastructure.team_detail_reader import PsycopgTeamDetailReader
from ehf.infrastructure.team_list_reader import PsycopgTeamListReader
from ehf.infrastructure.venue_detail_reader import PsycopgVenueDetailReader
from ehf.infrastructure.venue_list_reader import PsycopgVenueListReader
from ehf.interface.competition_views import CompetitionListView
from ehf.interface.expand import expand_href
from ehf.interface.match_views import MatchDetailView, MatchListView
from ehf.interface.navigation import zarejestruj_kontekst_nawigacji
from ehf.interface.player_views import PlayerDetailView, PlayerListView
from ehf.interface.plurals import polish_count
from ehf.interface.positions import code_for_player, code_for_position, hue_for_player
from ehf.interface.referee_views import RefereeDetailView, RefereeListView
from ehf.interface.scorer_views import ScorerListView
from ehf.interface.season_views import SeasonListView
from ehf.interface.start_views import StartView
from ehf.interface.match_sheet_views import MatchSheetFormView, MatchSheetPrintView
from ehf.interface.team_views import TeamDetailView, TeamListView
from ehf.interface.venue_views import VenueDetailView, VenueListView
from ehf.interface.views import utworz_blueprint
from ehf.services.competition_list import CompetitionListService
from ehf.services.match_detail import MatchDetailService
from ehf.services.match_list import MatchListService
from ehf.services.news import NewsService
from ehf.services.player_detail import PlayerDetailService
from ehf.services.player_list import PlayerListService
from ehf.services.referee_detail import RefereeDetailService
from ehf.services.referee_list import RefereeListService
from ehf.services.scorer_list import ScorerListService
from ehf.services.season_list import SeasonListService
from ehf.services.match_sheet import MatchSheetService
from ehf.services.team_detail import TeamDetailService
from ehf.services.team_list import TeamListService
from ehf.services.venue_detail import VenueDetailService
from ehf.services.venue_list import VenueListService
from ehf.settings import Settings

INTERFACE_DIR = Path(__file__).resolve().parent


def create_app() -> Flask:
    settings = Settings.from_env()
    app = Flask(
        "handball_ehf",
        template_folder=str(INTERFACE_DIR / "templates"),
        static_folder=str(INTERFACE_DIR / "static"),
        static_url_path="/statyczne",
    )
    app.config["SECRET_KEY"] = settings.secret_key
    app.add_template_filter(hue_for_player, "position_hue")
    app.add_template_filter(code_for_player, "position_code")
    app.add_template_filter(code_for_position, "position_abbr")
    app.add_template_filter(polish_count, "polish_count")
    app.add_template_global(expand_href, "expand_href")
    zarejestruj_kontekst_nawigacji(app)
    blueprint = utworz_blueprint()
    def connect():
        return open_connection(settings)

    list_service = MatchListService(PsycopgMatchListReader(connect))
    detail_service = MatchDetailService(PsycopgMatchDetailReader(connect))
    player_list_service = PlayerListService(PsycopgPlayerListReader(connect))
    player_detail_service = PlayerDetailService(PsycopgPlayerDetailReader(connect))
    venue_list_service = VenueListService(PsycopgVenueListReader(connect))
    venue_detail_service = VenueDetailService(PsycopgVenueDetailReader(connect))
    referee_list_service = RefereeListService(PsycopgRefereeListReader(connect))
    referee_detail_service = RefereeDetailService(PsycopgRefereeDetailReader(connect))
    season_list_service = SeasonListService(PsycopgSeasonListReader(connect))
    competition_list_service = CompetitionListService(PsycopgCompetitionListReader(connect))
    team_list_service = TeamListService(PsycopgTeamListReader(connect))
    team_detail_service = TeamDetailService(PsycopgTeamDetailReader(connect))
    match_sheet_service = MatchSheetService(PsycopgMatchSheetReader(connect))
    scorer_list_service = ScorerListService(PsycopgScorerListReader(connect))
    news_service = NewsService(PsycopgNewsReader(connect))
    blueprint.add_url_rule(
        "/",
        view_func=StartView.as_view("start", service=news_service),
    )
    blueprint.add_url_rule(
        "/mecze",
        view_func=MatchListView.as_view("match_list", service=list_service),
    )
    blueprint.add_url_rule(
        "/mecze/<int:match_id>",
        view_func=MatchDetailView.as_view("match_detail", service=detail_service),
    )
    blueprint.add_url_rule(
        "/zawodnicy",
        view_func=PlayerListView.as_view("lista_zawodnikow", service=player_list_service),
    )
    blueprint.add_url_rule(
        "/zawodnicy/<int:player_id>",
        view_func=PlayerDetailView.as_view("player_detail", service=player_detail_service),
    )
    blueprint.add_url_rule(
        "/hale",
        view_func=VenueListView.as_view("lista_hal", service=venue_list_service),
    )
    blueprint.add_url_rule(
        "/hale/<int:venue_id>",
        view_func=VenueDetailView.as_view("venue_detail", service=venue_detail_service),
    )
    blueprint.add_url_rule(
        "/sedziowie",
        view_func=RefereeListView.as_view("lista_sedziow", service=referee_list_service),
    )
    blueprint.add_url_rule(
        "/sedziowie/<int:referee_id>",
        view_func=RefereeDetailView.as_view("referee_detail", service=referee_detail_service),
    )
    blueprint.add_url_rule(
        "/sezony",
        view_func=SeasonListView.as_view("lista_sezonow", service=season_list_service),
    )
    blueprint.add_url_rule(
        "/rozgrywki",
        view_func=CompetitionListView.as_view("lista_rozgrywek", service=competition_list_service),
    )
    blueprint.add_url_rule(
        "/druzyny",
        view_func=TeamListView.as_view("lista_druzyn", service=team_list_service),
    )
    blueprint.add_url_rule(
        "/druzyny/<int:club_id>",
        view_func=TeamDetailView.as_view("team_detail", service=team_detail_service),
    )
    blueprint.add_url_rule(
        "/protokol",
        view_func=MatchSheetFormView.as_view("match_sheet", service=match_sheet_service),
    )
    blueprint.add_url_rule(
        "/protokol/druk",
        view_func=MatchSheetPrintView.as_view("match_sheet_print", service=match_sheet_service),
    )
    blueprint.add_url_rule(
        "/strzelcy",
        view_func=ScorerListView.as_view("lista_strzelcow", service=scorer_list_service),
    )
    app.register_blueprint(blueprint)
    return app
