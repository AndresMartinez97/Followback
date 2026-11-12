"""Streamlit dashboard for importing and exploring Instagram follow exports."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.analysis import AGE_GROUPS, compare_accounts
from modules.data_cleaner import clean_records
from modules.parser import HTMLDataError, parse_instagram_html_content
from modules.visualizations import age_chart, monthly_records_chart, relationship_chart


PROJECT_DIR = Path(__file__).resolve().parent
CSS_PATH = PROJECT_DIR / "assets" / "styles.css"
PAGE_OPTIONS = [
    "Resumen",
    "No me siguen de regreso",
    "Seguidores y mutuos",
    "Datos y privacidad",
]

st.set_page_config(
    page_title="FollowBack Explorer",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_data(
    followers_content: bytes,
    following_content: bytes,
    followers_name: str,
    following_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    parsed = {
        "followers": parse_instagram_html_content(
            followers_content, "followers", followers_name
        ),
        "following": parse_instagram_html_content(
            following_content, "following", following_name
        ),
    }
    empty_files = [
        name
        for name, result in parsed.items()
        if result.report["registros_extraidos"] == 0
    ]
    if empty_files:
        labels = {
            "followers": followers_name,
            "following": following_name,
        }
        raise HTMLDataError(
            "No se encontraron cuentas reconocibles en: "
            + ", ".join(f"`{labels[name]}`" for name in empty_files)
            + ". Verifica que sean exportaciones HTML de Instagram del tipo esperado."
        )

    cleaned = {
        name: clean_records(parsed_data.data)
        for name, parsed_data in parsed.items()
    }
    reports = {}
    for name, result in cleaned.items():
        reports[name] = {
            **result.report,
            **parsed[name].report,
            "filas_originales": parsed[name].report["registros_html"],
            "duplicados_eliminados": result.report["duplicados_eliminados"],
            "usuarios_vacios": (
                result.report["usuarios_vacios"]
                + parsed[name].report["usuarios_vacios"]
            ),
        }
    return (
        cleaned["followers"].data,
        cleaned["following"].data,
        reports,
    )


def _upload_signature(followers_file, following_file) -> str | None:
    if followers_file is None or following_file is None:
        return None
    digest = hashlib.sha256()
    for uploaded_file in (followers_file, following_file):
        digest.update(uploaded_file.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(uploaded_file.getvalue())
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_upload_name(uploaded_file, label: str) -> str | None:
    if uploaded_file is None:
        return None
    if Path(uploaded_file.name).suffix.casefold() not in {".html", ".htm"}:
        return f"{label}: selecciona un archivo con extensión .html o .htm."
    return None


def _format_datetime(value: object) -> str:
    if pd.isna(value):
        return "Sin fecha válida"
    return pd.Timestamp(value).strftime("%d/%m/%Y %H:%M")


def _format_elapsed(days: object) -> str:
    if pd.isna(days) or days < 0:
        return "No disponible"
    return f"{int(days)} días"


def _show_account_table(
    frame: pd.DataFrame,
    *,
    date_column: str = "fecha",
    include_age: bool = False,
) -> None:
    if frame.empty:
        st.info("No hay cuentas que coincidan con los filtros seleccionados.")
        return

    table = pd.DataFrame(
        {
            "Usuario": frame["usuario"],
            "Perfil": frame["perfil"],
            "Fecha y hora": frame[date_column].map(_format_datetime),
        }
    )
    if include_age:
        table["Tiempo transcurrido"] = frame["dias_transcurridos"].map(_format_elapsed)
        table["Antigüedad"] = frame["antiguedad"].astype(str)

    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "Perfil": st.column_config.LinkColumn(
                "Perfil",
                display_text="Abrir perfil",
                help="Abre el enlace de perfil de Instagram validado del HTML.",
            )
        },
    )


def _filtered_non_mutual(frame: pd.DataFrame) -> pd.DataFrame:
    query = st.text_input("Buscar por nombre de usuario", key="not_following_search")
    selected_ages = st.multiselect(
        "Antigüedad",
        AGE_GROUPS,
        default=AGE_GROUPS,
        key="not_following_ages",
    )
    dates = frame["fecha"].dropna()
    if not dates.empty:
        minimum = dates.min().date()
        maximum = dates.max().date()
        date_range = st.date_input(
            "Rango de fechas en que seguiste la cuenta",
            value=(minimum, maximum),
            min_value=minimum,
            max_value=maximum,
            key="not_following_dates",
        )
    else:
        date_range = ()

    sort_by = st.selectbox(
        "Ordenar por",
        ["Nombre de usuario (A-Z)", "Más antiguos primero", "Más recientes primero"],
        key="not_following_sort",
    )

    filtered = frame.loc[
        frame["antiguedad"].astype(str).isin(selected_ages)
    ].copy()
    if query:
        filtered = filtered.loc[
            filtered["usuario"].str.contains(query.strip(), case=False, regex=False)
        ]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered.loc[
            filtered["fecha"].notna()
            & filtered["fecha"].dt.date.ge(start)
            & filtered["fecha"].dt.date.le(end)
        ]

    if sort_by == "Nombre de usuario (A-Z)":
        filtered = filtered.sort_values("usuario_normalizado", kind="stable")
    elif sort_by == "Más antiguos primero":
        filtered = filtered.sort_values("fecha", ascending=True, na_position="last")
    else:
        filtered = filtered.sort_values("fecha", ascending=False, na_position="last")
    return filtered


def _show_metrics(summary: dict[str, int]) -> None:
    columns = st.columns(5)
    metrics = [
        ("Seguidores", summary["seguidores"]),
        ("Seguidos", summary["seguidos"]),
        ("Mutuos", summary["mutuos"]),
        ("No te siguen", summary["no_me_siguen"]),
        ("No sigues de regreso", summary["no_sigo_de_regreso"]),
    ]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, f"{value:,}")

    if summary["seguidos"]:
        pct = summary["no_me_siguen"] / summary["seguidos"] * 100
        st.caption(
            f"El {pct:.1f}% de las cuentas que sigues no aparece en tu lista de seguidores."
        )


def main() -> None:
    if CSS_PATH.is_file():
        st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>
            #MainMenu {
                visibility: hidden;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("## 📸 FollowBack Explorer")
        st.caption("Tus exportaciones se procesan en memoria.")
        page = st.radio("Explorar", PAGE_OPTIONS, label_visibility="collapsed")
        st.markdown(
            '<div class="sidebar-footer"><a href="https://www.instagram.com/fermtzra/" '
            'target="_blank" rel="noopener noreferrer">Creado por @fermtzra</a></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="hero"><span class="eyebrow">TU CÍRCULO, MÁS CLARO</span>'
        "<h1>FollowBack Explorer</h1>"
        "<p>Importa tus exportaciones.. de Instagram y explora tus relaciones de seguimiento.</p></div>",
        unsafe_allow_html=True,
    )

    st.subheader("Importa tus archivos de Instagram")
    follower_column, following_column = st.columns(2)
    with follower_column:
        with st.container(border=True, key="followers-upload-card"):
            st.markdown("### 👥 Importar seguidores")
            st.caption("Importa aquí tu archivo de seguidores")
            followers_file = st.file_uploader(
                "Archivo de seguidores",
                type=["html", "htm"],
                key="followers_upload",
                label_visibility="collapsed",
            )
    with following_column:
        with st.container(border=True, key="following-upload-card"):
            st.markdown("### 💜 Importar seguidos")
            st.caption("Importa aquí tu archivo de seguidos")
            following_file = st.file_uploader(
                "Archivo de seguidos",
                type=["html", "htm"],
                key="following_upload",
                label_visibility="collapsed",
            )

    signature = _upload_signature(followers_file, following_file)
    if followers_file is not None:
        st.caption(f"Seguidores seleccionado: `{followers_file.name}`")
    if following_file is not None:
        st.caption(f"Seguidos seleccionado: `{following_file.name}`")

    if signature is None:
        st.info("Selecciona ambos archivos HTML para habilitar el análisis.")
    else:
        st.success("Ambos archivos están listos para analizar.")

    extension_errors = [
        error
        for error in (
            _validate_upload_name(followers_file, "Seguidores"),
            _validate_upload_name(following_file, "Seguidos"),
        )
        if error
    ]
    for error in extension_errors:
        st.error(error)

    can_analyze = signature is not None and not extension_errors
    if st.button(
        "✨ Analizar mis relaciones",
        type="primary",
        width="stretch",
        disabled=not can_analyze,
    ):
        st.session_state.pop("followback_analysis", None)
        st.session_state.pop("followback_analysis_signature", None)
        st.session_state.pop("followback_analysis_error", None)
        try:
            with st.spinner("Leyendo y analizando tus archivos en memoria..."):
                followers, following, reports = _load_data(
                    followers_file.getvalue(),
                    following_file.getvalue(),
                    followers_file.name,
                    following_file.name,
                )
                comparison = compare_accounts(followers, following)
            st.session_state["followback_analysis"] = (
                comparison,
                reports,
                followers_file.name,
                following_file.name,
            )
            st.session_state["followback_analysis_signature"] = signature
        except (HTMLDataError, ValueError) as exc:
            st.session_state["followback_analysis_error"] = (signature, str(exc))

    stored_error = st.session_state.get("followback_analysis_error")
    if stored_error and stored_error[0] == signature:
        st.error(stored_error[1])

    stored_analysis = st.session_state.get("followback_analysis")
    is_current_analysis = (
        stored_analysis is not None
        and signature is not None
        and st.session_state.get("followback_analysis_signature") == signature
    )
    if stored_analysis is not None and signature is not None and not is_current_analysis:
        st.warning(
            "Cambiaste uno o ambos archivos. Ejecuta nuevamente el análisis para "
            "actualizar los resultados."
        )

    if is_current_analysis:
        comparison, reports, followers_name, following_name = stored_analysis
        if any(report["registros_malformados"] for report in reports.values()):
            st.warning(
                "Se omitieron bloques malformados de una o ambas exportaciones. "
                "Consulta la sección «Datos y privacidad» para ver los conteos."
            )
        st.caption(
            f"Analizados: `{followers_name}` y `{following_name}`. "
            "El contenido HTML no se guarda en almacenamiento permanente."
        )
        st.divider()

        if page == "Resumen":
            _show_metrics(comparison.summary)
            left, right = st.columns(2)
            with left:
                st.subheader("Relaciones entre cuentas")
                st.plotly_chart(
                    relationship_chart(comparison.summary),
                    width="stretch",
                    config={"displaylogo": False},
                )
            with right:
                st.subheader("Antigüedad de quienes no te siguen")
                st.plotly_chart(
                    age_chart(comparison.not_following_back),
                    width="stretch",
                    config={"displaylogo": False},
                )
            st.subheader("Registros por mes")
            st.caption(
                "Cuenta registros fechados en cada lista; no representa el total histórico "
                "de seguidores que tenías en cada mes."
            )
            st.plotly_chart(
                monthly_records_chart(comparison.followers, comparison.following),
                width="stretch",
                config={"displaylogo": False},
            )

        elif page == "No me siguen de regreso":
            st.subheader("Cuentas que sigues y no aparecen entre tus seguidores")
            st.caption(
                "La antigüedad usa la fecha de la exportación de seguidos. Fechas "
                "inválidas o futuras no se interpretan como antigüedad."
            )
            filtered = _filtered_non_mutual(comparison.not_following_back)
            st.caption(f"{len(filtered):,} cuentas")
            _show_account_table(filtered, include_age=True)

        elif page == "Seguidores y mutuos":
            section = st.radio(
                "Tipo de relación",
                ["Me siguen y no sigo", "Seguimiento mutuo"],
                horizontal=True,
            )
            if section == "Me siguen y no sigo":
                st.caption("La fecha corresponde al registro de seguidores.")
                _show_account_table(comparison.not_followed_back)
            else:
                mutual = comparison.mutual.copy()
                mutual["Fecha en que tú seguiste"] = mutual["fecha_lo_segui"].map(
                    _format_datetime
                )
                mutual["Fecha en que te siguió"] = mutual["fecha_te_siguio"].map(
                    _format_datetime
                )
                st.dataframe(
                    mutual[
                        [
                            "usuario_seguido",
                            "perfil_seguido",
                            "Fecha en que tú seguiste",
                            "Fecha en que te siguió",
                        ]
                    ].rename(
                        columns={
                            "usuario_seguido": "Usuario",
                            "perfil_seguido": "Perfil",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Perfil": st.column_config.LinkColumn(
                            "Perfil", display_text="Abrir perfil"
                        )
                    },
                )

        else:
            st.subheader("Datos y privacidad")
            st.write(
                "Los archivos se procesan en memoria para esta sesión. No se conecta "
                "a Instagram ni se guardan permanentemente las exportaciones. En "
                "Community Cloud, los HTML se procesan en la instancia del servidor "
                "durante la sesión, no en el equipo del usuario."
            )
            st.write(
                "Las fechas corresponden a eventos distintos en cada exportación. "
                "El gráfico mensual no reconstruye el total histórico de seguidores."
            )
            st.markdown("**Calidad de las exportaciones**")
            for title, report in (
                ("Seguidores", reports["followers"]),
                ("Seguidos", reports["following"]),
            ):
                st.markdown(
                    f"**{title}:** {report['registros_extraidos']:,} registros "
                    f"extraídos de {report['registros_html']:,} bloques HTML"
                )
                st.caption(
                    f"Usuarios vacíos excluidos: {report['usuarios_vacios']} · "
                    f"Duplicados eliminados: {report['duplicados_eliminados']} · "
                    f"Fechas inválidas: {report['fechas_invalidas']} · "
                    f"Perfiles inválidos u omitidos: {report['perfiles_invalidos']} · "
                    f"Registros malformados: {report['registros_malformados']}"
                )

if __name__ == "__main__":
    main()
