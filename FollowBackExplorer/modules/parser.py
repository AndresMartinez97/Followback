"""Parse the Instagram account export HTML files into canonical data frames."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_DATE_PATTERN = re.compile(
    r"\b([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})\s+"
    r"(\d{1,2}):(\d{2})\s*(am|pm)\b",
    re.IGNORECASE,
)


class HTMLDataError(ValueError):
    """Raised when an Instagram export HTML file is absent or unreadable."""


@dataclass(frozen=True)
class ParsedHTML:
    data: pd.DataFrame
    report: dict[str, int]


@dataclass
class _Record:
    depth: int = 1
    anchors: list[dict[str, str]] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    text: list[str] = field(default_factory=list)
    in_heading: bool = False


class _InstagramExportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.current_title = False
        self.current_record: _Record | None = None
        self.finished_records: list[_Record] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "title":
            self.current_title = True
        if tag == "div" and "_a6-g" in classes:
            if self.current_record is not None:
                self.current_record.depth += 1
            else:
                self.current_record = _Record()
        elif tag == "div" and self.current_record is not None:
            self.current_record.depth += 1

        record = self.current_record
        if record is None:
            return
        if tag == "h2":
            record.in_heading = True
        elif tag == "a":
            anchor = {
                "href": attributes.get("href") or "",
            }
            record.anchors.append(anchor)

    def handle_data(self, data: str) -> None:
        if self.current_title:
            self.title += data
        record = self.current_record
        if record is not None:
            record.text.append(data)
            if record.in_heading:
                record.headings.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.current_title = False
        record = self.current_record
        if record is None:
            return
        if tag == "h2":
            record.in_heading = False
        elif tag == "div":
            record.depth -= 1
            if record.depth == 0:
                self.finished_records.append(record)
                self.current_record = None


def _username_from_profile(value: str, role: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"instagram.com", "www.instagram.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if role == "following" and len(parts) == 2 and parts[0] == "_u":
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    return ""


def _parse_export_date(value: str) -> datetime | None:
    match = _DATE_PATTERN.search(value)
    if not match:
        return None
    month, day, year, hour, minute, meridiem = match.groups()
    month_number = _MONTHS.get(month.casefold())
    if month_number is None:
        return None
    hour_number = int(hour) % 12
    if meridiem.casefold() == "pm":
        hour_number += 12
    try:
        return datetime(
            int(year),
            month_number,
            int(day),
            hour_number,
            int(minute),
        )
    except ValueError:
        return None


def _extract_record(record: _Record, role: str) -> tuple[dict[str, object] | None, str | None]:
    if len(record.anchors) != 1:
        return None, "cantidad de enlaces distinta de uno"

    anchor = record.anchors[0]
    linked_username = _username_from_profile(anchor["href"], role)
    heading_username = "".join(record.headings).strip()
    username = heading_username if role == "following" else linked_username
    if not username or not linked_username:
        return None, "usuario o enlace de perfil ausente/malformado"
    if username.casefold() != linked_username.casefold():
        return None, "usuario del registro no coincide con el enlace"

    date_value = _parse_export_date(" ".join(record.text))
    if date_value is None:
        return {
            "usuario": username,
            "perfil": f"https://www.instagram.com/{username}",
            "perfil_exportado": anchor["href"].strip(),
            "fecha": pd.NaT,
        }, "fecha ausente o malformada"

    return {
        "usuario": username,
        "perfil": f"https://www.instagram.com/{username}",
        "perfil_exportado": anchor["href"].strip(),
        "fecha": date_value,
    }, None


def parse_instagram_html(path: str | Path, role: str) -> ParsedHTML:
    """Parse one ``followers`` or ``following`` export from a local path."""
    html_path = Path(path)
    if not html_path.is_file():
        raise HTMLDataError(f"No se encontró el archivo HTML: {html_path}")
    try:
        content = html_path.read_bytes()
    except (OSError, UnicodeError) as exc:
        raise HTMLDataError(f"No se pudo leer «{html_path.name}»: {exc}") from exc
    return parse_instagram_html_content(content, role, html_path.name)


def parse_instagram_html_content(
    content: bytes | str,
    role: str,
    source_name: str = "archivo HTML",
) -> ParsedHTML:
    """Parse an uploaded Instagram export directly from memory."""
    if role not in {"followers", "following"}:
        raise ValueError("role debe ser 'followers' o 'following'.")
    try:
        decoded_content = (
            content.decode("utf-8-sig")
            if isinstance(content, bytes)
            else content.lstrip("\ufeff")
        )
    except UnicodeDecodeError as exc:
        raise HTMLDataError(
            f"«{source_name}» no tiene una codificación HTML UTF-8 válida."
        ) from exc
    if not decoded_content.strip():
        raise HTMLDataError(f"«{source_name}» está vacío.")

    parser = _InstagramExportParser()
    try:
        parser.feed(decoded_content)
        parser.close()
    except (ValueError, AssertionError) as exc:
        raise HTMLDataError(
            f"«{source_name}» no contiene HTML válido: {exc}"
        ) from exc

    expected_title = "followers" if role == "followers" else "following"
    if parser.title.strip().casefold() != expected_title:
        raise HTMLDataError(
            f"«{source_name}» no parece ser una exportación de "
            f"{expected_title}; título detectado: {parser.title.strip() or 'vacío'}."
        )
    if parser.current_record is not None:
        parser.finished_records.append(parser.current_record)

    records: list[dict[str, object]] = []
    malformed_rows = 0
    invalid_dates = 0
    for index, record in enumerate(parser.finished_records, start=1):
        parsed, issue = _extract_record(record, role)
        if parsed is None:
            malformed_rows += 1
            continue
        parsed["numero_lista"] = index
        records.append(parsed)
        if issue == "fecha ausente o malformada":
            invalid_dates += 1

    frame = pd.DataFrame(
        records,
        columns=[
            "numero_lista",
            "usuario",
            "perfil",
            "perfil_exportado",
            "fecha",
        ],
    )
    frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce")
    missing_users = int(
        frame["usuario"].fillna("").astype(str).str.strip().eq("").sum()
    )
    duplicate_users = int(
        frame["usuario"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lstrip("@")
        .str.casefold()
        .duplicated(keep="first")
        .sum()
    )
    return ParsedHTML(
        frame,
        {
            "registros_html": len(parser.finished_records),
            "registros_extraidos": len(frame),
            "registros_malformados": malformed_rows,
            "usuarios_vacios": missing_users,
            "duplicados_normalizados": duplicate_users,
            "fechas_invalidas": invalid_dates,
            "enlaces_exportados_formato_interno": int(
                frame["perfil_exportado"].astype(str).str.contains("/_u/").sum()
            ),
        },
    )


def default_html_paths() -> dict[str, Path]:
    """Return local export paths next to the FollowBackExplorer project directory."""
    data_directory = Path(__file__).resolve().parents[2]
    return {
        "followers": data_directory / "followers.html",
        "following": data_directory / "following.html",
    }


def read_html_data(
    followers_path: str | Path | None = None,
    following_path: str | Path | None = None,
) -> dict[str, ParsedHTML]:
    """Read both expected exports and return parsed data plus quality reports."""
    defaults = default_html_paths()
    return {
        "followers": parse_instagram_html(
            followers_path or defaults["followers"], "followers"
        ),
        "following": parse_instagram_html(
            following_path or defaults["following"], "following"
        ),
    }
