import importlib.util


def _require_pywin32() -> None:
    if importlib.util.find_spec("win32com.client") is None:
        raise RuntimeError(
            "pywin32 n'est pas installé. Installez-le via `pip install pywin32`."
        )


def get_active_item_text() -> tuple[object, str, bool]:
    _require_pywin32()
    from win32com.client import Dispatch  # noqa: WPS433

    outlook = Dispatch("Outlook.Application")
    inspector = outlook.ActiveInspector()
    if inspector is None:
        raise RuntimeError("Aucune fenêtre Outlook active.")
    item = inspector.CurrentItem
    if item is None:
        raise RuntimeError("Aucun élément actif dans Outlook.")

    html_body = getattr(item, "HTMLBody", None)
    if html_body:
        return item, html_body, True
    return item, item.Body, False


def set_item_text(item: object, text: str, is_html: bool) -> None:
    if is_html:
        setattr(item, "HTMLBody", text)
    else:
        setattr(item, "Body", text)
