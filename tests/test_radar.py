from __future__ import annotations

from charts.radar import build_radar_figure


def test_radar_closes_loop_and_preserves_order():
    scores = {"B": 10, "A": 12, "C": 8}
    fig = build_radar_figure(scores, "Test")
    theta = list(fig.data[0].theta)
    assert theta == ["B", "A", "C", "B"]


def test_radar_clamps_values_to_bounds():
    scores = {"X": -3, "Y": 42}
    fig = build_radar_figure(scores, "Clamp", max_score=20)
    r = list(fig.data[0].r)
    assert r[0] == 0.0
    assert r[1] == 20.0


def test_radar_handles_empty_scores():
    fig = build_radar_figure({}, "Empty")
    assert len(fig.data) == 0
