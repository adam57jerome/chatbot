import html
import re
from html.parser import HTMLParser


class _HtmlToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        text = "".join(self.parts)
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip("\n")


def html_to_text(html_body: str) -> str:
    parser = _HtmlToTextParser()
    parser.feed(html_body)
    return parser.get_text()


def text_to_html(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n")]
    html_parts = [
        "<p>{}</p>".format(html.escape(p).replace("\n", "<br>"))
        for p in paragraphs
        if p
    ]
    return "\n".join(html_parts)


def detect_formality(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(vous|votre|vos|voudriez|merci de bien vouloir)\b", lower):
        return "vous"
    if re.search(r"\b(tu|ton|ta|tes|te|toi)\b", lower):
        return "tu"
    return "vous"


def split_signature(text: str) -> tuple[str, str, bool]:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() in {"--", "-- "}:
            body = "\n".join(lines[:idx]).rstrip()
            signature = "\n".join(lines[idx:]).rstrip()
            return body, signature, True
        if re.search(r"\b(tel|téléphone|portable|email|courriel)\b", line, re.I):
            body = "\n".join(lines[:idx]).rstrip()
            signature = "\n".join(lines[idx:]).rstrip()
            return body, signature, True
    return text, "", False


def join_signature(body: str, signature: str) -> str:
    if not signature:
        return body
    return f"{body}\n\n{signature}"


def normalize_spaces(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", text)
    return text


def capitalize_sentences(text: str) -> str:
    def _cap(match: re.Match[str]) -> str:
        return match.group(1) + match.group(2).upper()

    return re.sub(r"(^|[\.!?]\s+)([a-zà-ÿ])", _cap, text)


def reduce_repetitions(text: str, window: int = 3) -> str:
    words = text.split()
    result: list[str] = []
    for word in words:
        if word.lower() in [w.lower() for w in result[-window:]]:
            continue
        result.append(word)
    return " ".join(result)


def split_long_sentences(text: str, max_words: int = 25) -> str:
    sentences = re.split(r"(?<=[\.!?])\s+", text)
    output: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) <= max_words:
            output.append(sentence)
            continue
        split_done = False
        for connector in [" et ", " car ", " mais "]:
            if connector in sentence:
                parts = sentence.split(connector, 1)
                output.append(parts[0].strip() + ".")
                output.append(parts[1].strip().capitalize())
                split_done = True
                break
        if not split_done:
            output.append(sentence)
    return " ".join(output)


def replace_selection(text: str, selection: tuple[str, str], new_text: str) -> str:
    start, end = selection
    before = text[: _index_to_offset(text, start)]
    after = text[_index_to_offset(text, end) :]
    return f"{before}{new_text}{after}"


def _index_to_offset(text: str, index: str) -> int:
    line_str, col_str = index.split(".")
    line = int(line_str)
    col = int(col_str)
    lines = text.splitlines(keepends=True)
    offset = sum(len(lines[i]) for i in range(line - 1))
    return offset + col
