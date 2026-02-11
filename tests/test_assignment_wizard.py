from sqlalchemy import select

from src.assignment_service import (
    assign_questionnaire_to_session,
    can_start_saisie,
    wizard_prerequisites_logic,
)
from src.models import Assignment, Questionnaire, Session


def test_wizard_prerequisites_logic():
    r1 = wizard_prerequisites_logic(False, 0, 0, 0)
    assert r1["step1_ok"] is False
    assert r1["step2_ok"] is False
    assert r1["all_ok"] is False

    r2 = wizard_prerequisites_logic(True, 1, 1, 1)
    assert r2["step1_ok"] is True
    assert r2["step2_ok"] is True
    assert r2["all_ok"] is True


def test_assignment_creation(db_session):
    sess = Session(code="AC9999", label="Session AC9999", active=True)
    q = Questionnaire(name="Q test", active=True, reference_score_20=15.0)
    db_session.add_all([sess, q])
    db_session.commit()

    assignment = assign_questionnaire_to_session(db_session, sess.id, q.id, overwrite=True)
    assert assignment.id is not None
    row = db_session.scalar(select(Assignment).where(Assignment.session_id == sess.id))
    assert row is not None
    assert row.questionnaire_id == q.id


def test_block_saisie_without_assignment(db_session):
    sess = Session(code="AC0001", label="Session AC0001", active=True)
    q = Questionnaire(name="Q block", active=True, reference_score_20=15.0)
    db_session.add_all([sess, q])
    db_session.commit()

    assert can_start_saisie(db_session, sess.id) is False
    assign_questionnaire_to_session(db_session, sess.id, q.id, overwrite=True)
    assert can_start_saisie(db_session, sess.id) is True
