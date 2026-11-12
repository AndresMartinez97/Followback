import pandas as pd
import pytest

from modules.parser import HTMLDataError, parse_instagram_html


def _write_html(path, title, records):
    path.write_text(
        f"<html><head><title>{title}</title></head><body>"
        f"<main>{records}</main></body></html>",
        encoding="utf-8",
    )


def test_parses_followers_profile_and_exported_date(tmp_path):
    path = tmp_path / "followers.html"
    _write_html(
        path,
        "Followers",
        '<div class="_a6-g"><div><a href="https://www.instagram.com/Ana">'
        "Ana</a></div><div>Oct 21, 2026 7:47 pm</div></div>",
    )

    parsed = parse_instagram_html(path, "followers")

    assert parsed.data.loc[0, "usuario"] == "Ana"
    assert parsed.data.loc[0, "perfil"] == "https://www.instagram.com/Ana"
    assert parsed.data.loc[0, "fecha"] == pd.Timestamp("2026-10-21 19:47")
    assert parsed.report["registros_extraidos"] == 1
    assert parsed.report["fechas_invalidas"] == 0


def test_parses_following_heading_and_normalizes_internal_profile_path(tmp_path):
    path = tmp_path / "following.html"
    _write_html(
        path,
        "Following",
        '<div class="_a6-g"><h2>Some.User</h2><div><a '
        'href="https://www.instagram.com/_u/Some.User">'
        "https://www.instagram.com/_u/Some.User</a></div>"
        "<div>Jan 02, 2025 12:30 am</div></div>",
    )

    parsed = parse_instagram_html(path, "following")

    assert parsed.data.loc[0, "usuario"] == "Some.User"
    assert parsed.data.loc[0, "perfil"] == "https://www.instagram.com/Some.User"
    assert (
        parsed.data.loc[0, "perfil_exportado"]
        == "https://www.instagram.com/_u/Some.User"
    )
    assert parsed.data.loc[0, "fecha"] == pd.Timestamp("2025-01-02 00:30")
    assert parsed.report["enlaces_exportados_formato_interno"] == 1


def test_invalid_date_is_reported_without_inventing_a_date(tmp_path):
    path = tmp_path / "followers.html"
    _write_html(
        path,
        "Followers",
        '<div class="_a6-g"><a href="https://www.instagram.com/ana">ana</a>'
        "<div>unknown date</div></div>",
    )

    parsed = parse_instagram_html(path, "followers")

    assert pd.isna(parsed.data.loc[0, "fecha"])
    assert parsed.report["fechas_invalidas"] == 1


def test_wrong_export_type_and_missing_file_are_reported(tmp_path):
    path = tmp_path / "following.html"
    _write_html(path, "Following", "")

    with pytest.raises(HTMLDataError, match="no parece ser una exportación"):
        parse_instagram_html(path, "followers")
    with pytest.raises(HTMLDataError, match="No se encontró"):
        parse_instagram_html(tmp_path / "missing.html", "followers")
