"""Interface Streamlit du carnet de recettes."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from recipe_app.database import DEFAULT_DB_PATH, Recipe, RecipeRepository
from recipe_app.images import delete_image, save_uploaded_image
from recipe_app.importer import parse_recipe


ROOT_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = (ROOT_DIR / "data" / "uploads").resolve()

st.set_page_config(page_title="Mon carnet de recettes", page_icon="🍲", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1500px;}
    [data-testid="stMetric"] {background: #fff7ed; border: 1px solid #fed7aa; padding: .75rem; border-radius: .8rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_repository() -> RecipeRepository:
    return RecipeRepository(DEFAULT_DB_PATH)


def lines_to_list(value: str) -> list[str]:
    return [line.strip().lstrip("-*• ").strip() for line in value.splitlines() if line.strip()]


def render_recipe(recipe: Recipe) -> None:
    with st.container(border=True):
        image_column, content_column = st.columns([1, 2])
        with image_column:
            if recipe.image_path and Path(recipe.image_path).is_file():
                st.image(recipe.image_path, use_container_width=True)
            else:
                st.info("📷 Aucune image")
        with content_column:
            st.subheader(recipe.title)
            if recipe.description:
                st.write(recipe.description)
            metrics = st.columns(3)
            metrics[0].metric("Préparation", recipe.prep_time or "—")
            metrics[1].metric("Cuisson", recipe.cook_time or "—")
            metrics[2].metric("Portions", recipe.servings or "—")
            with st.expander("Voir la recette"):
                st.markdown("#### Ingrédients")
                for ingredient in recipe.ingredients:
                    st.markdown(f"- {ingredient}")
                st.markdown("#### Préparation")
                for number, instruction in enumerate(recipe.instructions, start=1):
                    st.markdown(f"**{number}.** {instruction}")


def recipe_fields(prefix: str, recipe: Recipe | None = None) -> tuple[dict[str, object], object]:
    title = st.text_input("Titre *", value=recipe.title if recipe else "", key=f"{prefix}_title")
    description = st.text_area("Description", value=recipe.description if recipe else "", key=f"{prefix}_description")
    col1, col2, col3 = st.columns(3)
    prep_time = col1.text_input("Temps de préparation", value=recipe.prep_time if recipe else "", key=f"{prefix}_prep")
    cook_time = col2.text_input("Temps de cuisson", value=recipe.cook_time if recipe else "", key=f"{prefix}_cook")
    servings = col3.text_input("Portions", value=recipe.servings if recipe else "", key=f"{prefix}_servings")
    ingredients = st.text_area(
        "Ingrédients * (un par ligne)",
        value="\n".join(recipe.ingredients) if recipe else "",
        height=180,
        key=f"{prefix}_ingredients",
    )
    instructions = st.text_area(
        "Étapes * (une par ligne)",
        value="\n".join(recipe.instructions) if recipe else "",
        height=220,
        key=f"{prefix}_instructions",
    )
    upload = st.file_uploader("Image de la recette (JPG, PNG ou WebP)", type=["jpg", "jpeg", "png", "webp"], key=f"{prefix}_image")
    return {
        "title": title,
        "description": description,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "servings": servings,
        "ingredients": lines_to_list(ingredients),
        "instructions": lines_to_list(instructions),
        "image_path": recipe.image_path if recipe else "",
        "source_text": recipe.source_text if recipe else "",
    }, upload


repository = get_repository()
st.title("🍲 Mon carnet de recettes")
st.caption("Enregistrez vos recettes, ajoutez leurs photos et importez facilement un texte généré par ChatGPT.")

gallery_tab, create_tab, import_tab, manage_tab = st.tabs(["📚 Mes recettes", "➕ Nouvelle recette", "✨ Import ChatGPT", "⚙️ Modifier / supprimer"])

with gallery_tab:
    search = st.text_input("Rechercher une recette", placeholder="Ex. tarte, curry, pâtes…")
    recipes = repository.list_recipes(search)
    st.caption(f"{len(recipes)} recette(s)")
    if not recipes:
        st.info("Aucune recette trouvée. Créez votre première recette ou importez-en une depuis ChatGPT.")
    for item in recipes:
        render_recipe(item)

with create_tab:
    st.subheader("Créer une recette")
    with st.form("create_recipe", clear_on_submit=True):
        values, uploaded_image = recipe_fields("create")
        create_submitted = st.form_submit_button("Créer la recette", type="primary", use_container_width=True)
    if create_submitted:
        if not values["title"] or not values["ingredients"] or not values["instructions"]:
            st.error("Le titre, les ingrédients et les étapes sont obligatoires.")
        else:
            try:
                if uploaded_image:
                    values["image_path"] = save_uploaded_image(uploaded_image, UPLOAD_DIR)
                repository.create_recipe(values)
                st.success("Recette créée avec succès.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

with import_tab:
    st.subheader("Importer une recette copiée depuis ChatGPT")
    st.write("Collez une réponse structurée avec les titres **Ingrédients** et **Préparation**. Vous pourrez ensuite la modifier.")
    with st.expander("Exemple de format à demander à ChatGPT"):
        st.code("# Tarte aux pommes\nPréparation : 20 min\nCuisson : 35 min\nPortions : 6\n\n## Ingrédients\n- 4 pommes\n- 1 pâte\n\n## Préparation\n1. Préchauffer le four.\n2. Garnir puis cuire.", language="markdown")
    with st.form("import_recipe", clear_on_submit=True):
        pasted_recipe = st.text_area("Texte de la recette *", height=350, placeholder="Collez ici la recette générée par ChatGPT…")
        imported_image = st.file_uploader("Image facultative", type=["jpg", "jpeg", "png", "webp"], key="import_image")
        import_submitted = st.form_submit_button("Importer la recette", type="primary", use_container_width=True)
    if import_submitted:
        try:
            imported_values = parse_recipe(pasted_recipe)
            imported_values["image_path"] = save_uploaded_image(imported_image, UPLOAD_DIR) if imported_image else ""
            repository.create_recipe(imported_values)
            st.success("Recette importée. Elle est disponible dans « Mes recettes ».")
            st.rerun()
        except ValueError as error:
            st.error(str(error))

with manage_tab:
    st.subheader("Modifier ou supprimer une recette")
    all_recipes = repository.list_recipes()
    if not all_recipes:
        st.info("Aucune recette à modifier.")
    else:
        recipe_by_id = {recipe.id: recipe for recipe in all_recipes}
        selected_id = st.selectbox("Recette", options=list(recipe_by_id), format_func=lambda recipe_id: recipe_by_id[recipe_id].title)
        selected_recipe = repository.get_recipe(selected_id)
        if selected_recipe:
            with st.form(f"edit_recipe_{selected_recipe.id}"):
                edited_values, new_image = recipe_fields(f"edit_{selected_recipe.id}", selected_recipe)
                update_submitted = st.form_submit_button("Enregistrer les modifications", type="primary", use_container_width=True)
            if update_submitted:
                if not edited_values["title"] or not edited_values["ingredients"] or not edited_values["instructions"]:
                    st.error("Le titre, les ingrédients et les étapes sont obligatoires.")
                else:
                    old_image = selected_recipe.image_path
                    if new_image:
                        edited_values["image_path"] = save_uploaded_image(new_image, UPLOAD_DIR)
                    repository.update_recipe(selected_recipe.id, edited_values)
                    if new_image:
                        delete_image(old_image, UPLOAD_DIR)
                    st.success("Recette mise à jour.")
                    st.rerun()

            st.divider()
            with st.form(f"delete_recipe_{selected_recipe.id}"):
                confirmed = st.checkbox(f"Je confirme la suppression définitive de « {selected_recipe.title} ».")
                delete_submitted = st.form_submit_button("Supprimer la recette", type="secondary", use_container_width=True)
            if delete_submitted:
                if not confirmed:
                    st.error("Cochez la confirmation avant de supprimer.")
                else:
                    deleted = repository.delete_recipe(selected_recipe.id)
                    if deleted:
                        delete_image(deleted.image_path, UPLOAD_DIR)
                    st.success("Recette supprimée.")
                    st.rerun()
