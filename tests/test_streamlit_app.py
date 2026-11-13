from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_streamlit_app_starts_with_authentication_tabs() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()

    assert not app.exception
    assert len(app.tabs) == 2
