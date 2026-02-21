from app.qcm_service import compute_note_sur_20, normalize_answer


def test_normalize_multi_reponse_order_independent():
    assert normalize_answer("A,C") == normalize_answer("C,A")
    assert normalize_answer(" a , c ") == "A,C"


def test_note_sur_20_from_score_7_on_10():
    assert compute_note_sur_20(7, 10) == 14.0


def test_note_sur_20_with_zero_question():
    assert compute_note_sur_20(0, 0) == 0.0


def test_note_sur_20_weighted_points():
    # 3 points obtenus sur 5 possibles => 12/20
    assert compute_note_sur_20(3, 5) == 12.0
