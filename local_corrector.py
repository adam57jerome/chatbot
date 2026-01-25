import importlib.util
from urllib.parse import urlparse


def _require_languagetool() -> None:
    if importlib.util.find_spec("language_tool_python") is None:
        raise RuntimeError(
            "language-tool-python n'est pas installé. Installez-le via `pip install language-tool-python`."
        )


def _validate_local_url(server_url: str) -> None:
    parsed = urlparse(server_url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError("URL LanguageTool invalide.")
    host = parsed.hostname or ""
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Le serveur LanguageTool doit être local (localhost).")


def correct_text(text: str, server_url: str) -> str:
    _require_languagetool()
    _validate_local_url(server_url)

    from language_tool_python import LanguageTool  # noqa: WPS433

    tool = LanguageTool("fr", server_url=server_url)
    return tool.correct(text)
