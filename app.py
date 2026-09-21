from pathlib import Path

from flask import Flask, render_template

ROOT = Path(__file__).resolve().parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )

    @app.get("/")
    def home():
        return render_template("home.html", aktywna="przeglad")

    @app.get("/mecze")
    def mecze():
        return render_template("mecze.html", aktywna="mecze")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
