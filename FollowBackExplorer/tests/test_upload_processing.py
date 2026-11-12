from io import BytesIO

import pytest

from app import _load_data, _upload_signature, _validate_upload_name
from modules.analysis import compare_accounts
from modules.parser import HTMLDataError, parse_instagram_html_content


def _export_html(title, records):
    return (
        f"<html><head><title>{title}</title></head><body>"
        f"<main>{records}</main></body></html>"
    ).encode("utf-8")


def test_upload_processing_accepts_arbitrary_names_and_matches_expected_analysis():
    followers = _export_html(
        "Followers",
        '<div class="_a6-g"><div><a href="https://www.instagram.com/mutual">'
        "mutual</a></div><div>Oct 21, 2026 7:47 pm</div></div>"
        '<div class="_a6-g"><div><a href="https://www.instagram.com/follower">'
        "follower</a></div><div>Oct 20, 2026 7:47 pm</div></div>",
    )
    following = _export_html(
        "Following",
        '<div class="_a6-g"><h2>mutual</h2><div><a '
        'href="https://www.instagram.com/_u/mutual">'
        "https://www.instagram.com/_u/mutual</a></div>"
        "<div>Oct 21, 2026 7:47 pm</div></div>"
        '<div class="_a6-g"><h2>notback</h2><div><a '
        'href="https://www.instagram.com/_u/notback">'
        "https://www.instagram.com/_u/notback</a></div>"
        "<div>Oct 20, 2026 7:47 pm</div></div>",
    )

    follower_data, following_data, reports = _load_data(
        followers,
        following,
        "followers_1.html",
        "personas_que_sigo.html",
    )
    result = compare_accounts(follower_data, following_data)

    assert result.summary == {
        "seguidores": 2,
        "seguidos": 2,
        "mutuos": 1,
        "no_me_siguen": 1,
        "no_sigo_de_regreso": 1,
    }
    assert reports["followers"]["registros_extraidos"] == 2
    assert reports["following"]["registros_extraidos"] == 2


def test_parser_accepts_html_bytes_regardless_of_filename():
    content = _export_html(
        "Followers",
        '<div class="_a6-g"><a href="https://www.instagram.com/ana">ana</a>'
        "<div>Oct 21, 2026 7:47 pm</div></div>",
    )

    parsed = parse_instagram_html_content(
        content,
        "followers",
        "seguidores_instagram.html",
    )

    assert parsed.data["usuario"].tolist() == ["ana"]


def test_uploaded_file_signature_changes_with_selected_files():
    followers_a = BytesIO(b"followers export A")
    followers_a.name = "followers.html"
    followers_b = BytesIO(b"followers export B")
    followers_b.name = "followers.html"
    following = BytesIO(b"following export")
    following.name = "following.html"

    signature_a = _upload_signature(followers_a, following)
    signature_b = _upload_signature(followers_b, following)

    assert signature_a != signature_b
    assert _upload_signature(followers_a, None) is None


def test_upload_name_validation_and_wrong_export_are_reported():
    unsupported = BytesIO(b"not html")
    unsupported.name = "followers.xlsx"
    assert _validate_upload_name(unsupported, "Seguidores")

    with pytest.raises(HTMLDataError, match="no parece ser una exportación"):
        parse_instagram_html_content(
            _export_html("Following", ""),
            "followers",
            "otro_nombre.html",
        )


def test_uploaded_html_without_accounts_is_reported():
    with pytest.raises(HTMLDataError, match="[Nn]o se encontraron cuentas reconocibles"):
        _load_data(
            _export_html("Followers", ""),
            _export_html("Following", ""),
            "followers_1.html",
            "following_1.html",
        )
