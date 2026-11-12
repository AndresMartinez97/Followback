import pandas as pd
import pytest

from modules.excel_reader import ExcelDataError, read_follow_data


def _write_workbook(path, followers=None, following=None):
    if followers is None:
        followers = pd.DataFrame(
            {
                "#": [1],
                "Usuario": ["ana"],
                "Perfil": ["https://www.instagram.com/ana"],
                "Te siguió el": [pd.Timestamp("2025-01-02 12:30")],
            }
        )
    if following is None:
        following = pd.DataFrame(
            {
                "#": [1],
                "Usuario": ["bea"],
                "Perfil": ["https://www.instagram.com/bea"],
                "Lo seguiste el": [pd.Timestamp("2025-01-03 12:30")],
            }
        )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        followers.to_excel(writer, sheet_name="Seguidores", index=False)
        following.to_excel(writer, sheet_name="Seguidos", index=False)


def test_reads_actual_spanish_sheets_and_date_fields(tmp_path):
    path = tmp_path / "data_follow.xlsx"
    _write_workbook(path)

    result = read_follow_data(path)

    assert set(result) == {"followers", "following"}
    assert list(result["followers"].columns) == [
        "numero_lista",
        "usuario",
        "perfil",
        "fecha",
    ]
    assert result["followers"].loc[0, "fecha"] == pd.Timestamp("2025-01-02 12:30")
    assert result["following"].loc[0, "fecha"] == pd.Timestamp("2025-01-03 12:30")


def test_missing_workbook_has_explanatory_error(tmp_path):
    with pytest.raises(ExcelDataError, match="No se encontró el archivo"):
        read_follow_data(tmp_path / "missing.xlsx")


def test_corrupt_workbook_has_explanatory_error(tmp_path):
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"not an xlsx file")

    with pytest.raises(ExcelDataError, match="archivo Excel válido"):
        read_follow_data(path)


def test_missing_sheet_is_reported(tmp_path):
    path = tmp_path / "incomplete.xlsx"
    pd.DataFrame({"Usuario": ["ana"]}).to_excel(path, sheet_name="Amigos", index=False)

    with pytest.raises(ExcelDataError, match="No se encontró la hoja"):
        read_follow_data(path)


def test_missing_required_column_is_reported(tmp_path):
    path = tmp_path / "bad_headers.xlsx"
    following = pd.DataFrame(
        {
            "#": [1],
            "Usuario": ["bea"],
            "Perfil": ["https://www.instagram.com/bea"],
            "Lo seguiste el": [pd.Timestamp("2025-01-03")],
        }
    )
    _write_workbook(path, followers=pd.DataFrame({"Usuario": ["ana"]}), following=following)

    with pytest.raises(ExcelDataError, match="columnas requeridas"):
        read_follow_data(path)
