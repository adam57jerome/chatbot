from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.database import get_recent_runs, get_sections_with_counts, init_db, save_assessment_run
from src.excel_parser import parse_workbook
from src.exporters import export_manual_workbook, export_recalculated_workbook, export_synthesis_csv
from src.manual_input import build_subjects_from_manual_tables
from src.scoring import score_all_subjects
from src.synthesis import build_synthesis

DEFAULT_SUBJECTS = [
    "Lecture de plan",
    "Acteur de l'acte de construire",
    "Corps d'état dans le batiment",
    "Utilisation de l'informatique e",
    "Utilisation du français",
    "Utilisation de Mathématique",
]


def _subject_detail_view(subject):
    display_columns = ["question", "correct_answer"]
    rename_map = {"question": "N° question", "correct_answer": "Bonne réponse"}
    for learner in subject.learners:
        response_col = f"{learner.name}__response"
        score_col = f"{learner.name}__score"
        display_columns.extend([response_col, score_col])
        rename_map[response_col] = f"{learner.name} - Réponse"
        rename_map[score_col] = f"{learner.name} - Score"

    st.dataframe(subject.questions_df[display_columns].rename(columns=rename_map), use_container_width=True)

    totals_df = pd.DataFrame(
        {
            "Stagiaire": [learner.name for learner in subject.learners],
            "Total points": [subject.totals.get(learner.name, 0) for learner in subject.learners],
            "Note /20": [subject.notes.get(learner.name, 0.0) for learner in subject.learners],
            "Réponses vides": [subject.empty_counts.get(learner.name, 0) for learner in subject.learners],
        }
    )
    st.subheader("Totaux et notes")
    st.dataframe(totals_df, use_container_width=True)


def _build_pie_data_for_learner(subjects, learner_name: str):
    correct = 0
    incorrect = 0
    for subject in subjects.values():
        total_q = len(subject.questions_df)
        points = subject.totals.get(learner_name)
        if points is None:
            continue
        correct += points
        incorrect += max(total_q - points, 0)
    return pd.DataFrame({"Type": ["Bonnes réponses", "Mauvaises réponses"], "Valeur": [correct, incorrect]})


def _build_group_theme_pie(subjects):
    rows = []
    for subject_name, subject in subjects.items():
        total_q = len(subject.questions_df)
        if total_q == 0:
            continue
        mean_note = pd.Series(list(subject.notes.values()), dtype="float64").mean(skipna=True)
        mean_correct = (mean_note / 20) * total_q if pd.notna(mean_note) else 0
        rows.append({"Thématique": subject_name, "Bonnes réponses moyennes": round(mean_correct, 2)})
    return pd.DataFrame(rows)


def _synthesis_view(subjects, synthesis_df):
    st.subheader("Tableau de synthèse")
    st.dataframe(synthesis_df, use_container_width=True)

    detail_df = synthesis_df[synthesis_df["Matière"] != "Moyenne générale apprenant"].copy()
    learner_names = [col for col in detail_df.columns if col not in {"Matière", "Moyenne matière"}]

    st.subheader("Analyses graphiques")
    col1, col2 = st.columns(2)

    with col1:
        selected_learner = st.selectbox("Camembert par stagiaire", learner_names)
        learner_pie = _build_pie_data_for_learner(subjects, selected_learner)
        st.plotly_chart(
            px.pie(learner_pie, values="Valeur", names="Type", title=f"Répartition des réponses - {selected_learner}", hole=0.35),
            use_container_width=True,
        )

    with col2:
        theme_df = _build_group_theme_pie(subjects)
        if not theme_df.empty:
            selected_theme = st.selectbox("Camembert par thématique", theme_df["Thématique"].tolist())
            val = float(theme_df.loc[theme_df["Thématique"] == selected_theme, "Bonnes réponses moyennes"].iloc[0])
            question_count = len(subjects[selected_theme].questions_df)
            theme_pie = pd.DataFrame(
                {
                    "Type": ["Bonnes réponses moyennes", "Mauvaises réponses moyennes"],
                    "Valeur": [val, max(question_count - val, 0)],
                }
            )
            st.plotly_chart(
                px.pie(theme_pie, values="Valeur", names="Type", title=f"Répartition moyenne groupe - {selected_theme}", hole=0.35),
                use_container_width=True,
            )

    st.subheader("Analyse graphique du groupe")
    learner_means = (
        detail_df[learner_names]
        .mean(numeric_only=True)
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"index": "Stagiaire", 0: "Moyenne générale"})
    )
    st.plotly_chart(
        px.bar(learner_means, x="Stagiaire", y="Moyenne générale", title="Moyenne générale par stagiaire (groupe)"),
        use_container_width=True,
    )


def _save_current_results(section_name: str, subjects, source: str):
    learners = []
    for subject in subjects.values():
        for learner in subject.learners:
            if learner.name not in learners:
                learners.append(learner.name)

    run_id = save_assessment_run(section_name=section_name, learner_names=learners, subjects=subjects, source=source)
    st.success(f"Résultats enregistrés en base (run #{run_id}).")


def _excel_mode():
    uploaded = st.file_uploader("Fichier Excel (.xlsx)", type=["xlsx"])
    if uploaded is None:
        st.info("Chargez un fichier .xlsx pour commencer.")
        return

    file_bytes = uploaded.getvalue()
    parsed = parse_workbook(file_bytes)
    if parsed.ignored_sheets:
        for sheet_name, reason in parsed.ignored_sheets.items():
            st.warning(f"Feuille ignorée: {sheet_name} ({reason})")

    if not parsed.subjects:
        st.error("Aucune feuille matière exploitable détectée.")
        return

    subjects = score_all_subjects(parsed.subjects)
    synthesis_df = build_synthesis(subjects)
    section_name = st.text_input("Section (pour sauvegarde en base)", value="Section importée", key="excel_section")

    tabs = st.tabs(["Vue Matière", "Synthèse"])
    with tabs[0]:
        selected_subject = st.selectbox("Choisir une matière", list(subjects.keys()))
        _subject_detail_view(subjects[selected_subject])
    with tabs[1]:
        _synthesis_view(subjects, synthesis_df)

    st.download_button(
        "Télécharger Excel recalculé",
        data=export_recalculated_workbook(file_bytes, subjects, synthesis_df),
        file_name="resultats_recalcules.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button(
        "Télécharger synthèse CSV",
        data=export_synthesis_csv(synthesis_df),
        file_name="synthese.csv",
        mime="text/csv",
    )
    if st.button("Enregistrer ce calcul en base", key="save_excel_db"):
        _save_current_results(section_name=section_name, subjects=subjects, source="excel")


def _manual_mode():
    st.markdown("### Paramétrage manuel")
    section_name = st.text_input("Section", value="Section A")
    learners_raw = st.text_input("Stagiaires (séparés par virgule)", value="Alice, Bob")
    learners = [name.strip() for name in learners_raw.split(",") if name.strip()]

    selected_subjects = st.multiselect("Thématiques", options=DEFAULT_SUBJECTS, default=DEFAULT_SUBJECTS)
    nb_questions = st.number_input("Nombre de questions par thématique", min_value=1, max_value=100, value=5)

    if not learners:
        st.warning("Veuillez saisir au moins un stagiaire.")
        return
    if not selected_subjects:
        st.warning("Veuillez sélectionner au moins une thématique.")
        return

    st.markdown("### Saisie des réponses")
    subject_tables = {}
    for subject_name in selected_subjects:
        st.markdown(f"**{subject_name}**")
        base = pd.DataFrame({"question": list(range(1, int(nb_questions) + 1)), "correct_answer": [""] * int(nb_questions)})
        for learner in learners:
            base[f"{learner}__response"] = [""] * int(nb_questions)
        subject_tables[subject_name] = st.data_editor(base, num_rows="fixed", key=f"editor_{subject_name}", use_container_width=True)

    if st.button("Calculer les résultats"):
        subjects = score_all_subjects(build_subjects_from_manual_tables(subject_tables, learners))
        synthesis_df = build_synthesis(subjects)
        st.session_state["manual_subjects"] = subjects
        st.session_state["manual_synthesis"] = synthesis_df
        st.session_state["manual_section"] = section_name

    subjects = st.session_state.get("manual_subjects")
    synthesis_df = st.session_state.get("manual_synthesis")
    section_saved = st.session_state.get("manual_section", section_name)

    if subjects and synthesis_df is not None:
        tabs = st.tabs(["Vue Matière", "Synthèse"])
        with tabs[0]:
            selected_subject = st.selectbox("Choisir une matière", list(subjects.keys()), key="manual_subject")
            st.caption(f"Section: {section_saved}")
            _subject_detail_view(subjects[selected_subject])
        with tabs[1]:
            st.caption(f"Section: {section_saved}")
            _synthesis_view(subjects, synthesis_df)

        st.download_button(
            "Télécharger Excel recalculé (manuel)",
            data=export_manual_workbook(section_saved, subjects, synthesis_df),
            file_name=f"resultats_{section_saved.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Télécharger synthèse CSV",
            data=export_synthesis_csv(synthesis_df),
            file_name=f"synthese_{section_saved.replace(' ', '_')}.csv",
            mime="text/csv",
        )
        if st.button("Enregistrer ce calcul en base", key="save_manual_db"):
            _save_current_results(section_name=section_saved, subjects=subjects, source="manual")


st.set_page_config(page_title="Recalcul questionnaire", layout="wide")
init_db()
st.title("Recalcul des résultats questionnaire")
st.caption("Mode Excel ou saisie manuelle des sections, stagiaires et réponses.")

with st.sidebar:
    st.header("Base de données")
    st.caption("Enregistrement des sections, stagiaires et calculs.")
    st.write("Sections enregistrées")
    st.dataframe(get_sections_with_counts(), use_container_width=True, hide_index=True)
    st.write("Derniers enregistrements")
    st.dataframe(get_recent_runs(), use_container_width=True, hide_index=True)

mode = st.radio("Mode d'utilisation", ["Import Excel", "Saisie manuelle"], horizontal=True)
if mode == "Import Excel":
    _excel_mode()
else:
    _manual_mode()
