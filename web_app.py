from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select

from src.database import SessionLocal, initialize_database
from src.excel_importer import parse_excel_preview
from src.import_service import import_excel_to_db
from src.models import Answer, Question, Questionnaire, Section, Session as CohortSession, Trainee
from src.services import ensure_seed_data, export_chatgpt_payload, get_or_create_attempt, group_synthesis, score_answer


st.set_page_config(page_title="Questionnaire AC Web", page_icon="📊", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem;}
.kpi-card {background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:12px 16px;margin-bottom:10px;}
.title {font-size:1.8rem;font-weight:700;color:#0f172a;}
.subtitle {color:#334155;margin-bottom:8px;}
</style>
""",
    unsafe_allow_html=True,
)

initialize_database()
with SessionLocal() as seed_db:
    ensure_seed_data(seed_db)

st.markdown('<div class="title">Questionnaire AC — Version Web</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Interface orientée web avec tableau de bord et CSS.</div>', unsafe_allow_html=True)


def get_session():
    if "db" not in st.session_state:
        st.session_state.db = SessionLocal()
    return st.session_state.db


db = get_session()

sessions = db.scalars(select(CohortSession).order_by(CohortSession.code)).all()
questionnaires = db.scalars(select(Questionnaire).order_by(Questionnaire.name)).all()

if not sessions or not questionnaires:
    st.warning("Aucune session ou questionnaire en base.")
    st.stop()

sid = st.sidebar.selectbox("Session", sessions, format_func=lambda s: f"{s.code} - {s.label}")
qid = st.sidebar.selectbox("Questionnaire", questionnaires, format_func=lambda q: q.name)
ref = qid.reference_score_20
st.sidebar.markdown(f"**Référence /20 : {ref:.1f}**")

sections = db.scalars(select(Section).where(Section.questionnaire_id == qid.id).order_by(Section.ordre)).all()
section = st.sidebar.selectbox("Section", sections, format_func=lambda s: s.name)
trainees = db.scalars(select(Trainee).where(Trainee.session_id == sid.id).order_by(Trainee.nom)).all()
trainee = st.sidebar.selectbox("Stagiaire", trainees, format_func=lambda t: f"{t.nom} {t.prenom}") if trainees else None


tab_input, tab_synth, tab_trainee, tab_import = st.tabs(["Saisie", "Synthèse groupe", "Stagiaire", "Import Excel"])

with tab_input:
    st.subheader("Saisie manuelle")
    if trainee is None:
        st.info("Ajoutez des stagiaires dans la session pour saisir des réponses.")
    else:
        attempt = get_or_create_attempt(db, sid.id, qid.id, trainee.id)
        questions = db.scalars(select(Question).where(Question.section_id == section.id).order_by(Question.numero)).all()
        answer_map = {a.question_id: a for a in db.scalars(select(Answer).where(Answer.attempt_id == attempt.id)).all()}

        rows = []
        for q in questions:
            existing = answer_map.get(q.id)
            rows.append(
                {
                    "question_id": q.id,
                    "Numero": q.numero,
                    "Bonne réponse": q.bonne_reponse or "",
                    "Réponse": existing.reponse_texte if existing else "",
                    "Score": existing.score if existing else 0,
                }
            )

        df = pd.DataFrame(rows)
        edited = st.data_editor(df[["Numero", "Bonne réponse", "Réponse", "Score"]], use_container_width=True)

        if st.button("Enregistrer les réponses"):
            for idx, q in enumerate(questions):
                response = str(edited.iloc[idx]["Réponse"] or "")
                expected = q.bonne_reponse or ""
                score = score_answer(response, expected)
                ans = answer_map.get(q.id)
                if ans is None:
                    db.add(Answer(attempt_id=attempt.id, question_id=q.id, reponse_texte=response, score=score))
                else:
                    ans.reponse_texte = response
                    ans.score = score
            db.commit()
            st.success("Réponses enregistrées.")

        sec_answers = db.scalars(select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id.in_([q.id for q in questions]))).all()
        total = sum(a.score for a in sec_answers)
        note = (20 / len(questions)) * total if questions else 0
        color = "#16a34a" if note >= ref else ("#f59e0b" if note >= ref - 1 else "#dc2626")
        st.markdown(f'<div class="kpi-card"><b>Total</b>: {total} / {len(questions)}<br/><b>Note /20</b>: <span style="color:{color}">{note:.2f}</span></div>', unsafe_allow_html=True)
        st.code(export_chatgpt_payload(db, sid.id, qid.id), language="json")

with tab_synth:
    st.subheader("Synthèse groupe")
    synth = group_synthesis(db, sid.id, qid.id)
    trainees_stats = synth["trainees_stats"]
    if trainees_stats:
        data = []
        for row in trainees_stats:
            pct = 100 if row["global_note"] >= ref else 0
            data.append({"Stagiaire": row["trainee"], "Moyenne générale": row["global_note"], "% >= ref": pct})
        dfg = pd.DataFrame(data)
        st.dataframe(dfg, use_container_width=True)
        st.bar_chart(dfg.set_index("Stagiaire")["Moyenne générale"])

        sec_means = {k: v["mean"] for k, v in synth["section_stats"].items()}
        st.write("Moyennes par section")
        st.bar_chart(pd.DataFrame({"section": list(sec_means.keys()), "mean": list(sec_means.values())}).set_index("section"))

with tab_trainee:
    st.subheader("Vue stagiaire")
    if trainee is None:
        st.info("Aucun stagiaire.")
    else:
        attempt = get_or_create_attempt(db, sid.id, qid.id, trainee.id)
        sec_rows = []
        for sec in sections:
            qs = db.scalars(select(Question).where(Question.section_id == sec.id)).all()
            qids = [q.id for q in qs]
            answers = db.scalars(select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id.in_(qids))).all() if qids else []
            total = sum(a.score for a in answers)
            note = (20 / len(qs)) * total if qs else 0
            sec_rows.append({"Section": sec.name, "Note /20": round(note, 2)})
        dft = pd.DataFrame(sec_rows)
        st.dataframe(dft, use_container_width=True)
        st.bar_chart(dft.set_index("Section")["Note /20"])
        st.metric("Moyenne générale", f"{dft['Note /20'].mean():.2f}/20")

with tab_import:
    st.subheader("Importer Excel")
    file = st.file_uploader("Fichier .xlsx", type=["xlsx"])
    if file is not None:
        tmp_path = Path("data") / file.name
        tmp_path.parent.mkdir(exist_ok=True)
        tmp_path.write_bytes(file.getvalue())
        preview = parse_excel_preview(str(tmp_path))

        st.write("### Récapitulatif")
        q_name = st.text_input("Nom questionnaire", value=preview.questionnaire_name)
        import_answers = st.checkbox("Importer les réponses existantes", value=True)
        import_new = st.checkbox("Importer les nouveaux stagiaires", value=True)

        section_choices = {}
        st.write("#### Sections détectées")
        existing_q = db.scalar(select(Questionnaire).where(Questionnaire.name == q_name).limit(1))
        existing_sec_names = set()
        if existing_q:
            existing_sec_names = {s.name for s in db.scalars(select(Section).where(Section.questionnaire_id == existing_q.id)).all()}
            st.warning(f"Le questionnaire '{q_name}' existe déjà.")
        strategy = st.radio("Conflit questionnaire", ["copy", "cancel"], format_func=lambda v: "Importer en copie" if v=="copy" else "Annuler")

        for sec in preview.sections_data:
            exists = sec.name in existing_sec_names
            section_choices[sec.name] = st.checkbox(f"{sec.name} ({len(sec.questions)} questions) - {'EXISTE' if exists else 'NOUVELLE'}", value=not exists)

        session_code = st.selectbox("Session cible", ["__auto__"] + [s.code for s in sessions], format_func=lambda v: "Créer session depuis nom fichier" if v=="__auto__" else v)
        if session_code == "__auto__":
            session_code = Path(preview.source_path).stem.upper().replace(" ", "_")[:30]

        selected_trainees = []
        selected_new = []
        existing_session = db.scalar(select(CohortSession).where(CohortSession.code == session_code).limit(1))
        existing_t = set()
        if existing_session:
            existing_t = {f"{t.nom} {t.prenom}".strip() for t in db.scalars(select(Trainee).where(Trainee.session_id == existing_session.id)).all()}

        st.write("#### Stagiaires détectés")
        for t in preview.trainees:
            use = st.checkbox(f"Utiliser réponses: {t} ({'EXISTE' if t in existing_t else 'NOUVEAU'})", value=True, key=f"use_{t}")
            if use:
                selected_trainees.append(t)
            if t not in existing_t:
                create_t = st.checkbox(f"Créer nouveau stagiaire: {t}", value=True, key=f"new_{t}")
                if create_t:
                    selected_new.append(t)

        est_answers = sum(len(s.questions) for s in preview.sections_data if section_choices.get(s.name)) * len(selected_trainees)
        st.info(f"Vous allez importer: {sum(section_choices.values())} sections, {len(selected_trainees)} stagiaires, {est_answers} réponses.")

        if st.button("Lancer import"):
            if strategy == "cancel" and existing_q:
                st.error("Import annulé: questionnaire existant.")
            else:
                questionnaire, session, warnings, diagnostics = import_excel_to_db(
                    db,
                    preview,
                    questionnaire_name=q_name,
                    session_code=session_code,
                    import_answers=import_answers,
                    questionnaire_strategy=strategy,
                    selected_sections={k for k, v in section_choices.items() if v},
                    selected_trainees_for_answers=set(selected_trainees),
                    import_new_trainees=import_new,
                    selected_new_trainees=set(selected_new),
                )
                st.success(f"Import terminé: {questionnaire.name} / session {session.code}")
                if warnings:
                    st.warning("Warnings:\n- " + "\n- ".join(warnings[:30]))
                st.text_area("Journal / Diagnostics", value="\n".join(diagnostics), height=200)
