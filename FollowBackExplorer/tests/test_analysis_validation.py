import pandas as pd

from modules.analysis import compare_data_sources


def test_compares_source_counts_missing_additional_and_profile_formats():
    html = pd.DataFrame(
        {
            "usuario": ["@Ana", "html-only"],
            "perfil": [
                "https://www.instagram.com/ana",
                "https://www.instagram.com/html-only",
            ],
            "perfil_exportado": [
                "https://www.instagram.com/_u/ana",
                "https://www.instagram.com/html-only",
            ],
            "fecha": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-02")],
        }
    )
    excel = pd.DataFrame(
        {
            "usuario": ["ana", "excel-only"],
            "perfil": [
                "https://www.instagram.com/ana",
                "https://www.instagram.com/excel-only",
            ],
            "fecha": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-03")],
        }
    )

    result = compare_data_sources(html, excel)

    assert result["coincidencias"] == 1
    assert result["faltantes_en_html"] == ["excel-only"]
    assert result["adicionales_en_html"] == ["html-only"]
    assert result["diferencias_de_escritura"] == [
        {"usuario_html": "@Ana", "usuario_excel": "ana"}
    ]
    assert len(result["diferencias_de_formato_de_perfil"]) == 1
    assert not result["diferencias_de_identidad_de_perfil"]
    assert not result["diferencias_de_fecha"]
