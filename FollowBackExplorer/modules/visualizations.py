"""Interactive Plotly charts for account relationships and recorded dates."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from modules.followers_analyzer import AGE_GROUPS


PALETTE = ["#9b4dca", "#ed3b83", "#ff8a3d", "#6f42c1", "#f2a0c4"]


def relationship_chart(summary: dict[str, int]) -> go.Figure:
    labels = ["Seguimiento mutuo", "No me siguen", "No sigo de regreso"]
    values = [
        summary["mutuos"],
        summary["no_me_siguen"],
        summary["no_sigo_de_regreso"],
    ]
    figure = px.pie(
        names=labels,
        values=values,
        hole=0.58,
        color_discrete_sequence=PALETTE,
    )
    figure.update_traces(
        textposition="inside",
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} cuentas<extra></extra>",
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f5f2f7",
        margin=dict(t=10, b=10, l=10, r=10),
        legend_title_text="Relación",
    )
    return figure


def age_chart(frame: pd.DataFrame) -> go.Figure:
    counts = frame["antiguedad"].value_counts().reindex(AGE_GROUPS, fill_value=0)
    figure = px.bar(
        x=counts.index,
        y=counts.values,
        labels={"x": "Antigüedad al seguir la cuenta", "y": "Cuentas"},
        color=counts.index,
        color_discrete_sequence=PALETTE,
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f5f2f7",
        showlegend=False,
        margin=dict(t=20, b=20, l=10, r=10),
        xaxis_title=None,
    )
    return figure


def monthly_records_chart(
    followers: pd.DataFrame, following: pd.DataFrame
) -> go.Figure:
    records: list[pd.DataFrame] = []
    for frame, label in (
        (followers, "Fecha en que te siguieron"),
        (following, "Fecha en que tú seguiste"),
    ):
        dated = frame.loc[frame["fecha"].notna(), ["fecha"]].copy()
        if dated.empty:
            continue
        dated["mes"] = dated["fecha"].dt.to_period("M").dt.to_timestamp()
        dated["tipo"] = label
        records.append(dated[["mes", "tipo"]])

    figure = go.Figure()
    if records:
        monthly = (
            pd.concat(records, ignore_index=True)
            .groupby(["mes", "tipo"])
            .size()
            .rename("registros")
            .reset_index()
        )
        for index, (label, group) in enumerate(monthly.groupby("tipo", sort=False)):
            figure.add_bar(
                x=group["mes"],
                y=group["registros"],
                name=label,
                marker_color=PALETTE[index],
                hovertemplate="%{x|%B %Y}: %{y} registros<extra>%{fullData.name}</extra>",
            )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f5f2f7",
        barmode="group",
        xaxis_title="Mes registrado",
        yaxis_title="Registros con fecha",
        margin=dict(t=20, b=20, l=10, r=10),
        legend_title_text="Tipo de fecha",
    )
    return figure
