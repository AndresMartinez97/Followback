import pandas as pd

import validate_exports
from modules.parser import ParsedHTML


def test_generates_report_with_all_source_rows_before_details(tmp_path, monkeypatch):
    frame = pd.DataFrame(
        {
            "numero_lista": [1],
            "usuario": ["ana"],
            "perfil": ["https://www.instagram.com/ana"],
            "perfil_exportado": ["https://www.instagram.com/ana"],
            "fecha": [pd.Timestamp("2025-01-01")],
        }
    )
    report = {
        "registros_html": 1,
        "registros_extraidos": 1,
        "registros_malformados": 0,
        "usuarios_vacios": 0,
        "duplicados_normalizados": 0,
        "fechas_invalidas": 0,
        "enlaces_exportados_formato_interno": 0,
    }
    parsed = ParsedHTML(frame.copy(), report)
    monkeypatch.setattr(
        validate_exports,
        "read_html_data",
        lambda *_args: {"followers": parsed, "following": parsed},
    )
    monkeypatch.setattr(
        validate_exports,
        "read_follow_data",
        lambda *_args: {"followers": frame.copy(), "following": frame.copy()},
    )
    target = tmp_path / "report.md"
    monkeypatch.setattr(validate_exports, "REPORT_PATH", target)

    generated = validate_exports.generate_report()

    text = generated.read_text(encoding="utf-8")
    assert generated == target
    assert text.index("| Seguidores |") < text.index("| Seguidos |")
    assert text.index("| Seguidos |") < text.index("## Seguidores")
    assert "Coincidencias |" in text
