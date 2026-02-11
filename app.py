from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.excel_parser import parse_workbook
from src.exporters import export_recalculated_workbook, export_synthesis_csv
from src.scoring import score_all_subjects
from src.synthesis import build_synthesis

st.set_page_config(page_title="Recalcul questionnaire", layout="wide")
st.title("Recalcul des résultats questionnaire")
st.caption("Importez un fichier Excel pour recalculer les scores, notes et la synthèse sans formules Excel.")

uploaded = st.file_uploader("Fichier Excel (.xlsx)", type=["xlsx"])

if uploaded is not None:
    file_bytes = uploaded.getvalue()
    parsed = parse_workbook(file_bytes)

    if parsed.ignored_sheets:
        for sheet_name, reason in parsed.ignored_sheets.items():
            st.warning(f"Feuille ignorée: {sheet_name} ({reason})")

    if not parsed.subjects:
        st.error("Aucune feuille matière exploitable détectée.")
        st.stop()

    subjects = score_all_subjects(parsed.subjects)
    synthesis_df = build_synthesis(subjects)

    tabs = st.tabs(["Vue Matière", "Synthèse"])

    with tabs[0]:
        selected_subject = st.selectbox("Choisir une matière", list(subjects.keys()))
        subject = subjects[selected_subject]

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
                "Apprenant": [learner.name for learner in subject.learners],
                "Total points": [subject.totals.get(learner.name, 0) for learner in subject.learners],
                "Note /20": [subject.notes.get(learner.name, 0.0) for learner in subject.learners],
                "Réponses vides": [subject.empty_counts.get(learner.name, 0) for learner in subject.learners],
            }
        )
        st.subheader("Totaux et notes")
        st.dataframe(totals_df, use_container_width=True)

        learners_with_empty = totals_df[totals_df["Réponses vides"] > 0]
        if not learners_with_empty.empty:
            st.warning(
                "Réponses vides détectées: "
                + ", ".join(
                    f"{row['Apprenant']} ({int(row['Réponses vides'])})"
                    for _, row in learners_with_empty.iterrows()
                )
            )

    with tabs[1]:
        st.subheader("Tableau de synthèse")
        st.dataframe(synthesis_df, use_container_width=True)

        detail_df = synthesis_df[synthesis_df["Matière"] != "Moyenne générale apprenant"].copy()

        learner_names = [
            col for col in detail_df.columns if col not in {"Matière", "Moyenne matière"}
        ]
        learner_means = (
            detail_df[learner_names]
            .mean(numeric_only=True)
            .sort_values(ascending=False)
            .reset_index()
            .rename(columns={"index": "Apprenant", 0: "Moyenne générale"})
        )

        fig_learner = px.bar(
            learner_means,
            x="Apprenant",
            y="Moyenne générale",
            title="Moyenne générale par apprenant",
        )
        st.plotly_chart(fig_learner, use_container_width=True)

        subject_means = detail_df[["Matière", "Moyenne matière"]].copy()
        fig_subject = px.bar(
            subject_means,
            x="Matière",
            y="Moyenne matière",
            title="Moyenne par matière (groupe)",
        )
        st.plotly_chart(fig_subject, use_container_width=True)

    recalculated_bytes = export_recalculated_workbook(file_bytes, subjects, synthesis_df)
    csv_bytes = export_synthesis_csv(synthesis_df)

    st.download_button(
        "Télécharger Excel recalculé",
        data=recalculated_bytes,
        file_name="resultats_recalcules.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button(
        "Télécharger synthèse CSV",
        data=csv_bytes,
        file_name="synthese.csv",
        mime="text/csv",
    )
else:
    st.info("Chargez un fichier .xlsx pour commencer.")
