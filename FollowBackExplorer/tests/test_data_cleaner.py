import pandas as pd

from modules.data_cleaner import clean_records, normalize_username


def test_normalizes_usernames_for_case_insensitive_comparison():
    assert normalize_username("  @MiCuenta  ") == "micuenta"
    assert normalize_username(None) == ""


def test_removes_duplicates_and_empty_users_and_reports_invalid_values():
    frame = pd.DataFrame(
        {
            "numero_lista": [1, 2, 3, 4],
            "usuario": [" @Ana ", "ana", None, "bea"],
            "perfil": [
                "https://www.instagram.com/ana",
                "https://www.instagram.com/ana",
                None,
                "http://example.com/bea",
            ],
            "fecha": ["2025-01-01", "2025-01-02", "invalid", "not a date"],
        }
    )

    result = clean_records(frame)

    assert result.data["usuario_normalizado"].tolist() == ["ana", "bea"]
    assert result.report == {
        "filas_originales": 4,
        "usuarios_vacios": 1,
        "duplicados_eliminados": 1,
        "fechas_invalidas": 1,
        "perfiles_invalidos": 1,
    }
    assert pd.isna(result.data.loc[1, "fecha"])
    assert pd.isna(result.data.loc[1, "perfil"])


def test_rejects_non_instagram_and_non_https_profile_links():
    frame = pd.DataFrame(
        {
            "numero_lista": [1, 2, 3],
            "usuario": ["a", "b", "c"],
            "perfil": [
                "https://instagram.com/a",
                "http://www.instagram.com/b",
                "https://www.instagram.com.evil.example/c",
            ],
            "fecha": [pd.Timestamp("2025-01-01")] * 3,
        }
    )

    result = clean_records(frame)

    assert result.data.loc[0, "perfil"] == "https://instagram.com/a"
    assert result.data.loc[1:, "perfil"].isna().all()
    assert result.report["perfiles_invalidos"] == 2
