from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[1]


def get_role_ui_preset(role: str) -> dict[str, object]:
    presets: dict[str, dict[str, object]] = {
        "Admin": {
            "ui_density": "Confort",
            "ui_compact_tables": False,
            "ui_show_trainee_actions": True,
            "ui_show_section_actions": True,
            "ui_show_formation_actions": True,
            "ui_show_qcm_editor": True,
        },
        "Formateur": {
            "ui_density": "Compact",
            "ui_compact_tables": True,
            "ui_show_trainee_actions": False,
            "ui_show_section_actions": False,
            "ui_show_formation_actions": False,
            "ui_show_qcm_editor": True,
        },
    }
    return presets.get(role, presets["Admin"]).copy()


def inject_app_css() -> None:
    css_path = BASE_DIR / "static" / "app.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

    density = st.session_state.get("ui_density", "Confort")
    compact_tables = st.session_state.get("ui_compact_tables", False)
    spacing = "0.5rem" if density == "Compact" else "1rem"
    font_scale = "0.96" if density == "Compact" else "1"
    row_height = "0.8rem" if compact_tables else "1rem"
    st.markdown(
        f"""
        <style>
            .block-container {{ padding-top: {spacing}; }}
            html, body, [class*="css"] {{ font-size: calc(16px * {font_scale}); }}
            [data-testid="stDataFrame"] div[role="gridcell"] {{ padding-top: {row_height}; padding-bottom: {row_height}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def toast(kind: str, message: str) -> None:
    if hasattr(st, "toast"):
        icon = {"success": "✅", "error": "❌", "info": "ℹ️", "warning": "⚠️"}.get(kind, "ℹ️")
        st.toast(message, icon=icon)
        return
    getattr(st, kind if kind in {"success", "error", "warning", "info"} else "info")(message)


def render_header(title: str, breadcrumb: str, actions: list[tuple[str, Callable[[], None]]] | None = None) -> None:
    container = st.container()
    with container:
        st.markdown('<div class="app-header">', unsafe_allow_html=True)
        left, right = st.columns([5, 2])
        with left:
            st.markdown(f"<h1>{title}</h1>", unsafe_allow_html=True)
            st.markdown(f'<div class="app-breadcrumb">{breadcrumb}</div>', unsafe_allow_html=True)
        with right:
            if actions:
                for label, callback in actions:
                    if st.button(label, use_container_width=True):
                        callback()
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_page_assistant(steps: list[str]) -> None:
    with st.expander("🧭 Assistant de page — quoi faire maintenant ?", expanded=False):
        for step in steps[:3]:
            st.markdown(f"- {step}")


def render_onboarding(page_key: str, tips: list[str]) -> None:
    seen_key = f"onboarding_seen_{page_key}"
    if st.session_state.get(seen_key):
        return
    with st.expander("👋 Découverte rapide", expanded=True):
        for tip in tips[:3]:
            st.markdown(f"• {tip}")
        if st.button("Compris", key=f"onboarding_done_{page_key}"):
            st.session_state[seen_key] = True
            st.rerun()


def render_context_actions(actions: list[tuple[str, str, str]]) -> str | None:
    """Render a sticky action bar and return key of clicked action."""
    if not actions:
        return None
    st.markdown('<div class="sticky-actions">', unsafe_allow_html=True)
    cols = st.columns(len(actions))
    clicked: str | None = None
    for col, (action_key, label, kind) in zip(cols, actions):
        button_type = "primary" if kind == "primary" else "secondary"
        if col.button(label, key=f"ctx_{action_key}", use_container_width=True, type=button_type):
            clicked = action_key
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked
