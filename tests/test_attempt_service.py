from datetime import datetime

from sqlalchemy import select

from src.attempt_service import compare_attempts_section_delta, create_attempt, save_answer_for_attempt
from src.models import Answer, Question, Questionnaire, Section, Session, Trainee


def _setup_base(db_session):
    sess = Session(code="ACP1", label="Session ACP1", active=True)
    q = Questionnaire(name="Q Attempts", active=True, reference_score_20=15.0)
    db_session.add_all([sess, q])
    db_session.flush()
    sec = Section(questionnaire_id=q.id, name="S1", ordre=1)
    db_session.add(sec)
    db_session.flush()
    q1 = Question(questionnaire_id=q.id, section_id=sec.id, numero=1, bonne_reponse="a")
    q2 = Question(questionnaire_id=q.id, section_id=sec.id, numero=2, bonne_reponse="b")
    t1 = Trainee(session_id=sess.id, nom="Doe", prenom="A", actif=True)
    db_session.add_all([q1, q2, t1])
    db_session.commit()
    return sess, q, sec, q1, q2, t1


def test_create_attempt(db_session):
    sess, q, *_ = _setup_base(db_session)
    a = create_attempt(db_session, sess.id, q.id, label="Entrée", created_at=datetime.utcnow())
    assert a.id is not None
    assert a.label == "Entrée"


def test_answers_unique_per_attempt_trainee_question(db_session):
    sess, q, sec, q1, _, t1 = _setup_base(db_session)
    a = create_attempt(db_session, sess.id, q.id, label="Entrée")
    save_answer_for_attempt(db_session, a.id, t1.id, q1.id, "a", "a")
    save_answer_for_attempt(db_session, a.id, t1.id, q1.id, "b", "a")
    rows = db_session.scalars(select(Answer).where(Answer.attempt_id == a.id, Answer.trainee_id == t1.id, Answer.question_id == q1.id)).all()
    assert len(rows) == 1


def test_compare_attempts_section_delta(db_session):
    sess, q, sec, q1, q2, t1 = _setup_base(db_session)
    a = create_attempt(db_session, sess.id, q.id, label="A")
    b = create_attempt(db_session, sess.id, q.id, label="B")
    save_answer_for_attempt(db_session, a.id, t1.id, q1.id, "a", "a")
    save_answer_for_attempt(db_session, a.id, t1.id, q2.id, "x", "b")
    save_answer_for_attempt(db_session, b.id, t1.id, q1.id, "a", "a")
    save_answer_for_attempt(db_session, b.id, t1.id, q2.id, "b", "b")
    delta = compare_attempts_section_delta(db_session, a.id, b.id, q.id)
    assert delta["S1"] == 10.0


def test_copy_previous_attempt_answers(db_session):
    sess, q, sec, q1, q2, t1 = _setup_base(db_session)
    a = create_attempt(db_session, sess.id, q.id, label="A")
    save_answer_for_attempt(db_session, a.id, t1.id, q1.id, "a", "a")
    save_answer_for_attempt(db_session, a.id, t1.id, q2.id, "b", "b")
    b = create_attempt(db_session, sess.id, q.id, label="B", duplicate_from_attempt_id=a.id)
    rows = db_session.scalars(select(Answer).where(Answer.attempt_id == b.id)).all()
    assert len(rows) == 2
    assert sum(r.score for r in rows) == 2
