"""Gestion locale des images téléversées."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def save_uploaded_image(uploaded_file: object, upload_dir: Path) -> str:
    """Enregistre une image Streamlit avec un nom non prédictible."""
    filename = str(getattr(uploaded_file, "name", ""))
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Format d’image non accepté. Utilisez JPG, PNG ou WebP.")
    upload_dir = upload_dir.resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid4().hex}{extension}"
    destination.write_bytes(uploaded_file.getvalue())
    return str(destination)


def delete_image(image_path: str, upload_dir: Path) -> None:
    """Supprime uniquement une image située dans le dossier d’uploads."""
    if not image_path:
        return
    path = Path(image_path).resolve()
    safe_dir = upload_dir.resolve()
    if path.is_relative_to(safe_dir) and path.is_file():
        path.unlink()
