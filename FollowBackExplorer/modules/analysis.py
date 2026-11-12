"""Source-independent relationship analysis and HTML/Excel validation."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import pandas as pd

from modules.data_cleaner import normalize_username


AGE_GROUPS = [
    "Menos de 30 días",
    "30 a 179 días",
    "180 a 365 días",
    "Más de 365 días",
    "Fecha inválida o futura",
]


@dataclass(frozen=True)
class ComparisonResult:
    followers: pd.DataFrame
    following: pd.DataFrame
    mutual: pd.DataFrame
    not_following_back: pd.DataFrame
    not_followed_back: pd.DataFrame
    summary: dict[str, int]


def add_follow_age(
    frame: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Add elapsed days and non-overlapping age groups based on the follow date."""
    result = frame.copy()
    reference = pd.Timestamp(as_of or pd.Timestamp.now()).normalize()
    dates = pd.to_datetime(result["fecha"], errors="coerce")
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    result["dias_transcurridos"] = (reference - dates).dt.days

    age = pd.Series("Fecha inválida o futura", index=result.index, dtype="object")
    valid = result["dias_transcurridos"].notna() & result["dias_transcurridos"].ge(0)
    days = result["dias_transcurridos"]
    age.loc[valid & days.lt(30)] = AGE_GROUPS[0]
    age.loc[valid & days.ge(30) & days.lt(180)] = AGE_GROUPS[1]
    age.loc[valid & days.ge(180) & days.le(365)] = AGE_GROUPS[2]
    age.loc[valid & days.gt(365)] = AGE_GROUPS[3]
    result["antiguedad"] = pd.Categorical(age, categories=AGE_GROUPS, ordered=True)
    return result


def compare_accounts(
    followers: pd.DataFrame,
    following: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
) -> ComparisonResult:
    """Compare account frames by normalized username, ignoring duplicates."""
    follower_data = followers.drop_duplicates("usuario_normalizado").copy()
    following_data = following.drop_duplicates("usuario_normalizado").copy()

    follower_keys = set(follower_data["usuario_normalizado"])
    following_keys = set(following_data["usuario_normalizado"])

    not_following_back = following_data.loc[
        ~following_data["usuario_normalizado"].isin(follower_keys)
    ].copy()
    not_followed_back = follower_data.loc[
        ~follower_data["usuario_normalizado"].isin(following_keys)
    ].copy()
    mutual = following_data.loc[
        following_data["usuario_normalizado"].isin(follower_keys)
    ].merge(
        follower_data[
            [
                "usuario_normalizado",
                "usuario",
                "perfil",
                "fecha",
            ]
        ].rename(
            columns={
                "usuario": "usuario_seguidor",
                "perfil": "perfil_seguidor",
                "fecha": "fecha_te_siguio",
            }
        ),
        on="usuario_normalizado",
        how="left",
        validate="one_to_one",
    )
    mutual = mutual.rename(
        columns={
            "usuario": "usuario_seguido",
            "perfil": "perfil_seguido",
            "fecha": "fecha_lo_segui",
        }
    )
    mutual["perfil_seguido"] = mutual["perfil_seguido"].combine_first(
        mutual["perfil_seguidor"]
    )

    not_following_back = add_follow_age(not_following_back, as_of)
    summary = {
        "seguidores": len(follower_data),
        "seguidos": len(following_data),
        "mutuos": len(mutual),
        "no_me_siguen": len(not_following_back),
        "no_sigo_de_regreso": len(not_followed_back),
    }
    return ComparisonResult(
        followers=follower_data,
        following=following_data,
        mutual=mutual,
        not_following_back=not_following_back,
        not_followed_back=not_followed_back,
        summary=summary,
    )


def _canonical_profile(value: object, username: str) -> str:
    if pd.isna(value):
        return ""
    parsed = urlsplit(str(value).strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"instagram.com", "www.instagram.com"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 1 and parts[0].casefold() == username:
        return username
    if len(parts) == 2 and parts[0] == "_u" and parts[1].casefold() == username:
        return username
    return ""


def compare_data_sources(
    html_frame: pd.DataFrame, excel_frame: pd.DataFrame
) -> dict[str, object]:
    """Summarize counts, normalized identities, and field-level differences."""
    def prepare(frame: pd.DataFrame, source: str) -> pd.DataFrame:
        result = frame.copy()
        result["usuario_normalizado"] = result["usuario"].map(normalize_username)
        result = result.loc[result["usuario_normalizado"].ne("")].copy()
        result = result.drop_duplicates("usuario_normalizado", keep="first")
        if "perfil_exportado" not in result:
            result["perfil_exportado"] = result["perfil"]
        result = result.rename(
            columns={
                "usuario": f"usuario_{source}",
                "perfil": f"perfil_{source}",
                "perfil_exportado": f"perfil_exportado_{source}",
                "fecha": f"fecha_{source}",
            }
        )
        return result

    html_duplicates = int(
        html_frame["usuario"].map(normalize_username).loc[lambda values: values.ne("")].duplicated().sum()
    )
    excel_duplicates = int(
        excel_frame["usuario"].map(normalize_username).loc[lambda values: values.ne("")].duplicated().sum()
    )
    html_empty = int(html_frame["usuario"].map(normalize_username).eq("").sum())
    excel_empty = int(excel_frame["usuario"].map(normalize_username).eq("").sum())
    html_data = prepare(html_frame, "html")
    excel_data = prepare(excel_frame, "excel")
    merged = html_data.merge(
        excel_data,
        on="usuario_normalizado",
        how="outer",
        indicator=True,
        validate="one_to_one",
    )

    html_only = merged.loc[merged["_merge"].eq("left_only")]
    excel_only = merged.loc[merged["_merge"].eq("right_only")]
    shared = merged.loc[merged["_merge"].eq("both")].copy()
    username_differences = shared.loc[
        shared["usuario_html"].ne(shared["usuario_excel"])
    ]

    html_dates = pd.to_datetime(shared["fecha_html"], errors="coerce")
    excel_dates = pd.to_datetime(shared["fecha_excel"], errors="coerce")
    date_differences = shared.loc[
        html_dates.ne(excel_dates) & ~(html_dates.isna() & excel_dates.isna())
    ]

    html_profile_keys = shared.apply(
        lambda row: _canonical_profile(
            row["perfil_html"], row["usuario_normalizado"]
        ),
        axis=1,
    )
    excel_profile_keys = shared.apply(
        lambda row: _canonical_profile(
            row["perfil_excel"], row["usuario_normalizado"]
        ),
        axis=1,
    )
    profile_identity_differences = shared.loc[
        html_profile_keys.ne(excel_profile_keys)
    ]
    html_source_urls = shared["perfil_exportado_html"].fillna("").astype(str)
    excel_urls = shared["perfil_exportado_excel"].fillna("").astype(str)
    profile_format_differences = shared.loc[
        html_source_urls.ne(excel_urls) & html_profile_keys.eq(excel_profile_keys)
    ]

    return {
        "html_rows": len(html_frame),
        "excel_rows": len(excel_frame),
        "html_unique_users": len(html_data),
        "excel_unique_users": len(excel_data),
        "coincidencias": len(shared),
        "faltantes_en_html": excel_only["usuario_excel"].tolist(),
        "adicionales_en_html": html_only["usuario_html"].tolist(),
        "duplicados_html": html_duplicates,
        "duplicados_excel": excel_duplicates,
        "usuarios_vacios_html": html_empty,
        "usuarios_vacios_excel": excel_empty,
        "diferencias_de_escritura": username_differences[
            ["usuario_html", "usuario_excel"]
        ].to_dict("records"),
        "diferencias_de_fecha": date_differences[
            ["usuario_normalizado", "fecha_html", "fecha_excel"]
        ].to_dict("records"),
        "diferencias_de_formato_de_perfil": profile_format_differences[
            ["usuario_normalizado", "perfil_exportado_html", "perfil_exportado_excel"]
        ].to_dict("records"),
        "diferencias_de_identidad_de_perfil": profile_identity_differences[
            ["usuario_normalizado", "perfil_html", "perfil_excel"]
        ].to_dict("records"),
    }
