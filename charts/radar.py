from __future__ import annotations

from collections.abc import Mapping

import plotly.graph_objects as go


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def build_radar_figure(
    scores: Mapping[str, float | int | None],
    title: str,
    max_score: float = 20,
    tick_step: int = 2,
) -> go.Figure:
    """Build a radar/spider chart (Excel-like) from score values.

    - Keeps category order from mapping insertion order.
    - Drops None values.
    - Clamps values to [0, max_score].
    - Closes the polygon by repeating first category/value.
    """
    categories: list[str] = []
    values: list[float] = []

    for category, raw_value in scores.items():
        if raw_value is None:
            continue
        categories.append(str(category))
        values.append(_clamp(float(raw_value), 0.0, float(max_score)))

    if not categories:
        fig = go.Figure()
        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            annotations=[
                {
                    "text": "Aucune donnée disponible",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                }
            ],
        )
        return fig

    # close loop
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    tickvals = list(range(0, int(max_score) + 1, max(1, int(tick_step))))

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values_closed,
                theta=categories_closed,
                fill="toself",
                line={"width": 2, "color": "#1d4ed8"},
                fillcolor="rgba(29, 78, 216, 0.25)",
                name="Score",
            )
        ]
    )
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center"},
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, max_score],
                "tickvals": tickvals,
                "gridcolor": "#d1d5db",
            },
            "angularaxis": {"gridcolor": "#e5e7eb"},
        },
        showlegend=False,
        margin={"l": 40, "r": 40, "t": 70, "b": 40},
    )
    return fig
