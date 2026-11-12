from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _export_html(title, user):
    if title == "Followers":
        record = (
            f'<div class="_a6-g"><div><a href="https://www.instagram.com/{user}">'
            f"{user}</a></div><div>Oct 21, 2026 7:47 pm</div></div>"
        )
    else:
        record = (
            f'<div class="_a6-g"><h2>{user}</h2><div><a '
            f'href="https://www.instagram.com/_u/{user}">'
            f"https://www.instagram.com/_u/{user}</a></div>"
            "<div>Oct 21, 2026 7:47 pm</div></div>"
        )
    return (
        f"<html><head><title>{title}</title></head><body>{record}</body></html>"
    ).encode()


def test_uploads_analyzes_and_requires_rerun_after_file_change():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert app.button[0].disabled
    assert len(app.get("file_uploader")) == 2
    assert any("Selecciona ambos archivos" in message.value for message in app.info)

    app.get("file_uploader")[0].upload(
        "followers_1.html",
        _export_html("Followers", "mutual"),
        "text/html",
    ).run()
    assert app.button[0].disabled

    app.get("file_uploader")[1].upload(
        "personas_que_sigo.html",
        _export_html("Following", "mutual"),
        "text/html",
    ).run()
    assert not app.button[0].disabled
    assert any("Ambos archivos están listos" in message.value for message in app.success)

    app.button[0].click().run()
    assert not app.exception
    assert [(metric.label, metric.value) for metric in app.metric] == [
        ("Seguidores", "1"),
        ("Seguidos", "1"),
        ("Mutuos", "1"),
        ("No te siguen", "0"),
        ("No sigues de regreso", "0"),
    ]

    app.get("file_uploader")[0].set_value(
        (
            "seguidores_instagram.html",
            _export_html("Followers", "different"),
            "text/html",
        )
    ).run()
    assert not app.metric
    assert any("Cambiaste uno o ambos archivos" in item.value for item in app.warning)

    app.button[0].click().run()
    assert not app.exception
    assert [(metric.label, metric.value) for metric in app.metric] == [
        ("Seguidores", "1"),
        ("Seguidos", "1"),
        ("Mutuos", "0"),
        ("No te siguen", "1"),
        ("No sigues de regreso", "1"),
    ]

    for page in (
        "No me siguen de regreso",
        "Seguidores y mutuos",
        "Datos y privacidad",
    ):
        navigation = next(radio for radio in app.radio if page in radio.options)
        navigation.set_value(page).run()
        if page == "Seguidores y mutuos":
            next(
                radio
                for radio in app.radio
                if "Seguimiento mutuo" in radio.options
            ).set_value("Seguimiento mutuo").run()
        assert not app.exception


def test_uploading_wrong_export_type_shows_error_without_results():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.get("file_uploader")[0].upload(
        "followers.html",
        _export_html("Following", "ana"),
        "text/html",
    ).run()
    app.get("file_uploader")[1].upload(
        "following.html",
        _export_html("Following", "ana"),
        "text/html",
    ).run()

    app.button[0].click().run()

    assert not app.exception
    assert not app.metric
    assert any("no parece ser una exportación" in error.value for error in app.error)
