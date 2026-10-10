import os

from ehf.interface.factory import create_app
from ehf.settings import load_env

load_env()
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("EHF_PORT", "5151"))
    app.run(host="0.0.0.0", port=port, debug=True)
