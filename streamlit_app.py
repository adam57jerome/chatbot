import json
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom

import streamlit as st


st.set_page_config(page_title="QCM Moodle (sans API)", page_icon="📝", layout="wide")

DEFAULT_TF_CHOICES = ["Vrai", "Faux"]


def blank_question() -> dict:
    return {
        "category": "Général",
        "type": "mcq",
        "title": "Nouvelle question",
        "question": "Énoncez la question ici.",
        "choices": ["Option 1", "Option 2"],
        "correct_index": 0,
        "feedback_correct": "Bravo !",
        "feedback_incorrect": "Réessayez.",
    }


def gift_escape(text: str) -> str:
    if text is None:
        return ""
    escaped = text.replace("\\", "\\\\")
    for char in ["~", "=", "#", "{", "}", ":"]:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def normalize_question(raw: dict) -> dict:
    question = blank_question()
    question.update(raw)
    if not isinstance(question.get("choices"), list):
        question["choices"] = []
    if question.get("type") == "tf" and not question["choices"]:
        question["choices"] = DEFAULT_TF_CHOICES.copy()
    return question


def validate_question(question: dict, index: int) -> list[str]:
    errors = []
    required = [
        "category",
        "type",
        "title",
        "question",
        "choices",
        "correct_index",
        "feedback_correct",
        "feedback_incorrect",
    ]
    for key in required:
        if key not in question:
            errors.append(f"Question {index + 1}: champ manquant '{key}'.")
    q_type = question.get("type")
    if q_type not in {"mcq", "tf"}:
        errors.append(
            f"Question {index + 1}: type invalide '{q_type}', attendu 'mcq' ou 'tf'."
        )
    choices = question.get("choices", [])
    if not isinstance(choices, list):
        errors.append(f"Question {index + 1}: 'choices' doit être une liste.")
        choices = []
    if q_type == "mcq" and len(choices) < 2:
        errors.append(
            f"Question {index + 1}: une question MCQ nécessite au moins 2 choix."
        )
    if q_type == "tf" and len(choices) != 2:
        errors.append(
            f"Question {index + 1}: une question Vrai/Faux nécessite exactement 2 choix."
        )
    correct_index = question.get("correct_index")
    if not isinstance(correct_index, int):
        errors.append(
            f"Question {index + 1}: 'correct_index' doit être un entier (0-based)."
        )
    elif choices and not (0 <= correct_index < len(choices)):
        errors.append(
            f"Question {index + 1}: 'correct_index' hors limites (0 à {len(choices) - 1})."
        )
    return errors


def validate_questions(questions: list[dict]) -> list[str]:
    errors: list[str] = []
    for idx, question in enumerate(questions):
        errors.extend(validate_question(question, idx))
    return errors


def question_choices_to_text(choices: list[str]) -> str:
    return "\n".join(choices)


def text_to_choices(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_gift(questions: list[dict]) -> str:
    lines: list[str] = []
    last_category = None
    for question in questions:
        category = (question.get("category") or "Sans catégorie").strip()
        if category != last_category:
            lines.append(f"$CATEGORY: {gift_escape(category)}")
            last_category = category
        title = gift_escape(question.get("title", ""))
        stem = gift_escape(question.get("question", ""))
        if question.get("type") == "tf":
            correct_index = question.get("correct_index", 0)
            correct_feedback = gift_escape(question.get("feedback_correct", ""))
            incorrect_feedback = gift_escape(question.get("feedback_incorrect", ""))
            if correct_index == 0:
                true_part = "T"
                false_part = "F"
                if correct_feedback:
                    true_part += f"#{correct_feedback}"
                if incorrect_feedback:
                    false_part += f"#{incorrect_feedback}"
            else:
                true_part = "T"
                false_part = "F"
                if incorrect_feedback:
                    true_part += f"#{incorrect_feedback}"
                if correct_feedback:
                    false_part += f"#{correct_feedback}"
            answers = f"{true_part} {false_part}"
        else:
            answers_list = []
            choices = question.get("choices", [])
            correct_index = question.get("correct_index", 0)
            correct_feedback = gift_escape(question.get("feedback_correct", ""))
            incorrect_feedback = gift_escape(question.get("feedback_incorrect", ""))
            for idx, choice in enumerate(choices):
                prefix = "=" if idx == correct_index else "~"
                feedback = (
                    correct_feedback if idx == correct_index else incorrect_feedback
                )
                escaped_choice = gift_escape(choice)
                if feedback:
                    answers_list.append(f"{prefix}{escaped_choice}#{feedback}")
                else:
                    answers_list.append(f"{prefix}{escaped_choice}")
            answers = " ".join(answers_list)
        lines.append(f"::{title}:: {stem} {{{answers}}}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def prettify_xml(element: ET.Element) -> str:
    rough = ET.tostring(element, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def add_text_element(parent: ET.Element, tag: str, text: str | None) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = "" if text is None else text
    return child


def build_moodle_xml(questions: list[dict]) -> str:
    quiz = ET.Element("quiz")
    last_category = None
    for question in questions:
        category = (question.get("category") or "Sans catégorie").strip()
        if category != last_category:
            cat_question = ET.SubElement(quiz, "question", {"type": "category"})
            category_el = ET.SubElement(cat_question, "category")
            add_text_element(category_el, "text", category)
            last_category = category
        q_type = question.get("type")
        if q_type == "tf":
            q_el = ET.SubElement(quiz, "question", {"type": "truefalse"})
        else:
            q_el = ET.SubElement(quiz, "question", {"type": "multichoice"})
        name_el = ET.SubElement(q_el, "name")
        add_text_element(name_el, "text", question.get("title", ""))
        qtext_el = ET.SubElement(q_el, "questiontext", {"format": "html"})
        add_text_element(qtext_el, "text", question.get("question", ""))
        add_text_element(q_el, "generalfeedback", "")
        if q_type == "tf":
            correct_index = question.get("correct_index", 0)
            correct_feedback = question.get("feedback_correct", "")
            incorrect_feedback = question.get("feedback_incorrect", "")
            true_answer = ET.SubElement(
                q_el, "answer", {"fraction": "100" if correct_index == 0 else "0"}
            )
            add_text_element(true_answer, "text", "true")
            feedback_true = ET.SubElement(true_answer, "feedback")
            add_text_element(
                feedback_true,
                "text",
                correct_feedback if correct_index == 0 else incorrect_feedback,
            )
            false_answer = ET.SubElement(
                q_el, "answer", {"fraction": "100" if correct_index == 1 else "0"}
            )
            add_text_element(false_answer, "text", "false")
            feedback_false = ET.SubElement(false_answer, "feedback")
            add_text_element(
                feedback_false,
                "text",
                correct_feedback if correct_index == 1 else incorrect_feedback,
            )
        else:
            add_text_element(q_el, "single", "true")
            add_text_element(q_el, "shuffleanswers", "true")
            add_text_element(q_el, "answernumbering", "none")
            choices = question.get("choices", [])
            correct_index = question.get("correct_index", 0)
            correct_feedback = question.get("feedback_correct", "")
            incorrect_feedback = question.get("feedback_incorrect", "")
            for idx, choice in enumerate(choices):
                fraction = "100" if idx == correct_index else "0"
                answer_el = ET.SubElement(q_el, "answer", {"fraction": fraction})
                add_text_element(answer_el, "text", choice)
                feedback_el = ET.SubElement(answer_el, "feedback")
                add_text_element(
                    feedback_el,
                    "text",
                    correct_feedback if idx == correct_index else incorrect_feedback,
                )
    return prettify_xml(quiz)


def init_state() -> None:
    if "questions" not in st.session_state:
        st.session_state.questions = [blank_question()]


def load_questions_from_json(payload: str) -> tuple[list[dict] | None, list[str]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        return None, [f"JSON invalide : {exc}"]
    if not isinstance(data, list):
        return None, ["Le JSON doit être une liste d'objets question."]
    questions = [normalize_question(item) for item in data]
    errors = validate_questions(questions)
    return (questions if not errors else None), errors


init_state()

st.title("📝 QCM Moodle (sans API)")

st.markdown(
    """
Créez, éditez et exportez vos questions Moodle sans API. Tout reste local à votre machine.
"""
)

with st.expander("Importer par copier/coller", expanded=True):
    json_payload = st.text_area(
        "Coller JSON",
        height=200,
        placeholder="[ { 'category': '...', 'type': 'mcq', ... } ]",
    )
    if st.button("Importer", type="primary"):
        questions, errors = load_questions_from_json(json_payload)
        if errors:
            st.error("\n".join(errors))
        else:
            st.session_state.questions = questions
            st.success(f"{len(questions)} questions importées.")

with st.expander("Importer un fichier JSON", expanded=False):
    uploaded_json = st.file_uploader(
        "Choisir un fichier JSON", type=["json"], accept_multiple_files=False
    )
    if uploaded_json is not None:
        content = uploaded_json.read().decode("utf-8")
        questions, errors = load_questions_from_json(content)
        if errors:
            st.error("\n".join(errors))
        else:
            st.session_state.questions = questions
            st.success(f"{len(questions)} questions importées depuis le fichier.")

st.subheader("Questions")

col_add, col_download = st.columns([1, 3])
with col_add:
    if st.button("Ajouter une question"):
        st.session_state.questions.append(blank_question())
        st.rerun()
with col_download:
    st.caption("Les modifications sont enregistrées en mémoire locale de la session.")

questions = st.session_state.questions

for idx, question in enumerate(questions):
    st.markdown(f"#### Question {idx + 1}")
    btn_cols = st.columns([1, 1, 1, 1, 1])
    if btn_cols[0].button("Dupliquer", key=f"duplicate_{idx}"):
        questions.insert(idx + 1, json.loads(json.dumps(question)))
        st.rerun()
    if btn_cols[1].button("Supprimer", key=f"delete_{idx}"):
        questions.pop(idx)
        if not questions:
            questions.append(blank_question())
        st.rerun()
    if btn_cols[2].button("Monter", key=f"up_{idx}", disabled=idx == 0):
        questions[idx - 1], questions[idx] = questions[idx], questions[idx - 1]
        st.rerun()
    if btn_cols[3].button(
        "Descendre", key=f"down_{idx}", disabled=idx == len(questions) - 1
    ):
        questions[idx + 1], questions[idx] = questions[idx], questions[idx + 1]
        st.rerun()
    if btn_cols[4].button("Réinitialiser", key=f"reset_{idx}"):
        questions[idx] = blank_question()
        st.rerun()

    category = st.text_input(
        "Catégorie Moodle",
        value=question.get("category", ""),
        key=f"category_{idx}",
    )
    question["category"] = category

    q_type = st.selectbox(
        "Type",
        options=["mcq", "tf"],
        index=0 if question.get("type") == "mcq" else 1,
        format_func=lambda option: "Choix multiple" if option == "mcq" else "Vrai/Faux",
        key=f"type_{idx}",
    )
    question["type"] = q_type

    title = st.text_input(
        "Titre",
        value=question.get("title", ""),
        key=f"title_{idx}",
    )
    question["title"] = title

    stem = st.text_area(
        "Énoncé",
        value=question.get("question", ""),
        height=100,
        key=f"question_{idx}",
    )
    question["question"] = stem

    choices_text = question_choices_to_text(question.get("choices", []))
    choices_input = st.text_area(
        "Choix (un par ligne)",
        value=choices_text,
        height=120,
        key=f"choices_{idx}",
    )
    choices = text_to_choices(choices_input)
    if q_type == "tf" and len(choices) != 2:
        st.warning(
            "Une question Vrai/Faux doit contenir exactement 2 choix (ex: Vrai / Faux)."
        )
    question["choices"] = choices

    max_index = max(len(choices) - 1, 0)
    default_index = question.get("correct_index", 0)
    if not isinstance(default_index, int):
        default_index = 0
    if default_index > max_index:
        default_index = max_index
    correct_index = st.number_input(
        "Index de la bonne réponse (0 = premier choix)",
        min_value=0,
        max_value=max_index,
        value=default_index,
        step=1,
        key=f"correct_{idx}",
    )
    question["correct_index"] = int(correct_index)

    feedback_correct = st.text_area(
        "Feedback si correct",
        value=question.get("feedback_correct", ""),
        height=80,
        key=f"feedback_correct_{idx}",
    )
    question["feedback_correct"] = feedback_correct

    feedback_incorrect = st.text_area(
        "Feedback si incorrect",
        value=question.get("feedback_incorrect", ""),
        height=80,
        key=f"feedback_incorrect_{idx}",
    )
    question["feedback_incorrect"] = feedback_incorrect

    st.divider()

validation_errors = validate_questions(questions)
if validation_errors:
    st.error("\n".join(validation_errors))

st.subheader("Export")

export_cols = st.columns(3)

if validation_errors:
    st.warning("Corrigez les erreurs avant d'exporter.")
else:
    gift_data = build_gift(questions)
    xml_data = build_moodle_xml(questions)
    json_data = json.dumps(questions, ensure_ascii=False, indent=2)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_cols[0].download_button(
        "Exporter GIFT (.txt)",
        data=gift_data,
        file_name=f"moodle_questions_{timestamp}.txt",
        mime="text/plain",
    )
    export_cols[1].download_button(
        "Exporter Moodle XML (.xml)",
        data=xml_data,
        file_name=f"moodle_questions_{timestamp}.xml",
        mime="application/xml",
    )
    export_cols[2].download_button(
        "Sauvegarder JSON (.json)",
        data=json_data,
        file_name=f"questions_{timestamp}.json",
        mime="application/json",
    )

st.caption(
    "Astuce : utilisez la sauvegarde JSON pour reprendre votre travail plus tard."
)
