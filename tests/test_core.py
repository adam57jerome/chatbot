from sqlalchemy import select

from src.models import Question, Questionnaire, Section, Session, Trainee
from src.services import (
    color_for_score,
    ensure_seed_data,
    get_or_create_attempt,
    group_synthesis,
    parse_question_block,
    save_answer,
    score_answer,
    section_stats_for_attempt,
)


def test_seed(db_session):
    ensure_seed_data(db_session)
    questionnaire = db_session.scalar(select(Questionnaire))
    assert questionnaire is not None
    assert len(db_session.scalars(select(Section)).all()) == 6
    assert len(db_session.scalars(select(Question)).all()) > 0


def test_add_question_block_parse():
    parsed = parse_question_block("1=A\n2=c\n3=d")
    assert parsed == [(1, "a"), (2, "c"), (3, "d")]


def test_scoring():
    assert score_answer(" A ", "a") == 1
    assert score_answer("b", "a") == 0


def _prepare_attempt(db_session):
    ensure_seed_data(db_session)
    sess = db_session.scalar(select(Session).where(Session.code == "AC1024"))
    q = db_session.scalar(select(Questionnaire))
    trainee = Trainee(session_id=sess.id, nom="Doe", prenom="Jane", actif=True)
    db_session.add(trainee)
    db_session.commit()
    attempt = get_or_create_attempt(db_session, sess.id, q.id, trainee.id)
    first_section = db_session.scalar(select(Section).where(Section.questionnaire_id == q.id).order_by(Section.ordre))
    questions = db_session.scalars(select(Question).where(Question.section_id == first_section.id)).all()
    return attempt, first_section, questions, q, sess


def test_section_stats(db_session):
    attempt, section, questions, _, _ = _prepare_attempt(db_session)
    save_answer(db_session, attempt.id, questions[0].id, questions[0].bonne_reponse, questions[0].bonne_reponse)
    stats = section_stats_for_attempt(db_session, attempt.id, section.id)
    assert stats.total_points == 1
    assert stats.nb_questions == len(questions)


def test_group_synthesis(db_session):
    attempt, section, questions, q, sess = _prepare_attempt(db_session)
    for question in questions:
        save_answer(db_session, attempt.id, question.id, question.bonne_reponse, question.bonne_reponse)
    synth = group_synthesis(db_session, sess.id, q.id)
    assert "section_stats" in synth
    assert len(synth["trainees_stats"]) == 1


def test_reference_threshold():
    assert color_for_score(16, 15) == "#2e7d32"
    assert color_for_score(14.2, 15) == "#f9a825"
    assert color_for_score(10, 15) == "#c62828"
