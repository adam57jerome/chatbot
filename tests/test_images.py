from pathlib import Path

import pytest

from recipe_app.images import delete_image, save_uploaded_image


class FakeUpload:
    name = "plat.png"

    def getvalue(self) -> bytes:
        return b"image-content"


def test_save_and_delete_uploaded_image(tmp_path: Path):
    image_path = save_uploaded_image(FakeUpload(), tmp_path / "uploads")
    assert Path(image_path).read_bytes() == b"image-content"

    delete_image(image_path, tmp_path / "uploads")
    assert not Path(image_path).exists()


def test_reject_unsupported_image_format(tmp_path: Path):
    upload = FakeUpload()
    upload.name = "plat.svg"
    with pytest.raises(ValueError, match="Format d’image"):
        save_uploaded_image(upload, tmp_path / "uploads")
