"""Read and validate the Instagram export without modifying the source workbook."""

from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Final

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException


EXPECTED_SHEETS: Final = {"seguidores": "followers", "seguidos": "following"}
_REQUIRED_HEADERS: Final = {
    "numero_lista": {"#", "numero de lista"},
    "usuario": {"usuario"},
    "perfil": {"perfil"},
}
_DATE_HEADERS: Final = {
    "followers": "te siguio el",
    "following": "lo seguiste el",
}


class ExcelDataError(ValueError):
    """Raised when the workbook does not match the supported export format."""


def _normalized_label(value: object) -> str:
    if str(value).strip() == "#":
        return "#"
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9]+", " ", text.casefold())).strip()


def default_workbook_path() -> Path:
    """Return data_follow.xlsx from the folder containing the project directory."""
    return Path(__file__).resolve().parents[2] / "data_follow.xlsx"


def _find_sheet(sheet_names: list[str], expected_name: str) -> str:
    matches = [
        name for name in sheet_names if _normalized_label(name) == expected_name
    ]
    if not matches:
        raise ExcelDataError(
            f"No se encontró la hoja «{expected_name}». "
            f"Hojas disponibles: {', '.join(sheet_names)}."
        )
    return matches[0]


def _canonicalize_sheet(frame: pd.DataFrame, sheet_name: str, role: str) -> pd.DataFrame:
    header_lookup: dict[str, object] = {}
    for column in frame.columns:
        normalized = _normalized_label(column)
        if normalized in header_lookup:
            raise ExcelDataError(
                f"La hoja «{sheet_name}» tiene encabezados duplicados "
                f"equivalentes a «{column}»."
            )
        header_lookup[normalized] = column

    required = dict(_REQUIRED_HEADERS)
    required["fecha"] = {_DATE_HEADERS[role]}
    selected: dict[str, object] = {}
    missing: list[str] = []
    for canonical, aliases in required.items():
        source = next((header_lookup[a] for a in aliases if a in header_lookup), None)
        if source is None:
            missing.append(canonical)
        else:
            selected[canonical] = source

    if missing:
        expected_date = (
            "Te siguió el" if role == "followers" else "Lo seguiste el"
        )
        raise ExcelDataError(
            f"La hoja «{sheet_name}» no contiene las columnas requeridas "
            f"(número de lista/#, Usuario, Perfil y {expected_date}). "
            f"Faltan: {', '.join(missing)}."
        )

    return frame[[selected[name] for name in required]].rename(
        columns={source: canonical for canonical, source in selected.items()}
    )


def read_follow_data(
    path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Read both expected sheets and return canonical ``followers``/``following`` data."""
    workbook_path = Path(path) if path is not None else default_workbook_path()
    if not workbook_path.is_file():
        raise ExcelDataError(
            f"No se encontró el archivo Excel: {workbook_path}. "
            "Coloca data_follow.xlsx junto a la carpeta FollowBackExplorer."
        )

    try:
        workbook = pd.ExcelFile(workbook_path, engine="openpyxl")
    except (
        OSError,
        ValueError,
        ImportError,
        zipfile.BadZipFile,
        InvalidFileException,
    ) as exc:
        raise ExcelDataError(
            f"No se pudo abrir «{workbook_path.name}» como un archivo Excel válido: {exc}"
        ) from exc

    loaded: dict[str, pd.DataFrame] = {}
    try:
        for expected_name, role in EXPECTED_SHEETS.items():
            actual_name = _find_sheet(workbook.sheet_names, expected_name)
            try:
                frame = pd.read_excel(
                    workbook, sheet_name=actual_name, engine="openpyxl"
                )
            except (
                OSError,
                ValueError,
                ImportError,
                zipfile.BadZipFile,
                InvalidFileException,
            ) as exc:
                raise ExcelDataError(
                    f"No se pudieron leer los datos de la hoja «{actual_name}»: {exc}"
                ) from exc
            loaded[role] = _canonicalize_sheet(frame, actual_name, role)
    finally:
        workbook.close()

    return loaded
