from __future__ import annotations

from pathlib import Path

from flask import Flask

from ehf.infrastructure.connection import open_connection
from ehf.infrastructure.match_detail_reader import PsycopgMatchDetailReader
from ehf.infrastructure.match_list_reader import PsycopgMatchListReader
from ehf.infrastructure.player_detail_reader import PsycopgPlayerDetailReader
from ehf.infrastructure.player_list_reader import PsycopgPlayerListReader
from ehf.interface.match_views import MatchDetailView, MatchListView
from ehf.interface.navigation import zarejestruj_kontekst_nawigacji
from ehf.interface.player_views import PlayerDetailView, PlayerListView
from ehf.interface.positions import code_for_player, code_for_position, hue_for_player
from ehf.interface.views import utworz_blueprint
from ehf.services.match_detail import MatchDetailService
from ehf.services.match_list import MatchListService
from ehf.services.player_detail import PlayerDetailService
from ehf.services.player_list import PlayerListService
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
    zarejestruj_kontekst_nawigacji(app)
    blueprint = utworz_blueprint()
    def connect():
        return open_connection(settings)

    list_service = MatchListService(PsycopgMatchListReader(connect))
    detail_service = MatchDetailService(PsycopgMatchDetailReader(connect))
    player_list_service = PlayerListService(PsycopgPlayerListReader(connect))
    player_detail_service = PlayerDetailService(PsycopgPlayerDetailReader(connect))
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
    app.register_blueprint(blueprint)
    return app
