"""Normalize exported account records and report data-quality issues."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import pandas as pd


REQUIRED_COLUMNS = {"numero_lista", "usuario", "perfil", "fecha"}


@dataclass(frozen=True)
class CleaningResult:
    data: pd.DataFrame
    report: dict[str, int]


def normalize_username(value: object) -> str:
    """Normalize an account identifier for case-insensitive comparison."""
    if pd.isna(value):
        return ""
    username = str(value).strip()
    if username.startswith("@"):
        username = username[1:]
    return username.casefold()


def _validated_profile(value: object) -> str | None:
    if pd.isna(value):
        return None
    candidate = str(value).strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"instagram.com", "www.instagram.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[A-Za-z0-9._]+/?", parsed.path)
    ):
        return None
    return candidate


def clean_records(frame: pd.DataFrame) -> CleaningResult:
    """Clean one canonical sheet and retain a count of discarded or invalid values."""
    missing_columns = REQUIRED_COLUMNS.difference(frame.columns)
    if missing_columns:
        raise ValueError(
            "Faltan columnas canónicas: " + ", ".join(sorted(missing_columns))
        )

    data = frame.loc[:, ["numero_lista", "usuario", "perfil", "fecha"]].copy()
    data["usuario"] = data["usuario"].fillna("").astype(str).str.strip()
    data["usuario"] = data["usuario"].str.replace(r"^@", "", n=1, regex=True)
    data["usuario_normalizado"] = data["usuario"].map(normalize_username)

    missing_users = int(data["usuario_normalizado"].eq("").sum())
    data = data.loc[data["usuario_normalizado"].ne("")].copy()

    duplicate_mask = data["usuario_normalizado"].duplicated(keep="first")
    duplicate_rows = int(duplicate_mask.sum())
    data = data.loc[~duplicate_mask].copy()

    dates = pd.to_datetime(data["fecha"], errors="coerce")
    invalid_dates = int(dates.isna().sum())
    data["fecha"] = dates

    validated_profiles = data["perfil"].map(_validated_profile)
    invalid_profiles = int(validated_profiles.isna().sum())
    data["perfil"] = validated_profiles

    report = {
        "filas_originales": len(frame),
        "usuarios_vacios": missing_users,
        "duplicados_eliminados": duplicate_rows,
        "fechas_invalidas": invalid_dates,
        "perfiles_invalidos": invalid_profiles,
    }
    return CleaningResult(
        data.reset_index(drop=True),
        report,
    )
