# app/services/latex_render.py

import base64
import binascii
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

# Order doesn't matter here since each source character is looked up once
# and replaced independently (no chained string.replace() passes, which
# would risk re-escaping a backslash introduced by an earlier replacement).
_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# `\\` alone would let a following `[` be swallowed as LaTeX's optional
# "extra vertical space" argument to the line-break command; `\relax`
# right after it is the standard no-op that blocks that.
_LATEX_HARDBREAK = r"\\\relax" + "\n"

_DATA_IMAGE_RE = re.compile(r"^data:image/(\w+);base64,(.+)$", re.DOTALL)

_PREAMBLE = (
    "\\documentclass[11pt]{article}\n"
    "\\usepackage[margin=1in]{geometry}\n"
    "\\usepackage{amsmath,amssymb,graphicx}\n"
    # No first-line paragraph indent, a modest gap between paragraphs
    # instead — the flat, note-like structure of a rich-text answer
    # (short lines, occasional blank-line breaks between problems) reads
    # far better this way than with indented block paragraphs.
    "\\usepackage{parskip}\n"
    # Page number top-right instead of article's default bottom-center;
    # no header rule for a clean, minimal look.
    "\\usepackage{fancyhdr}\n"
    "\\pagestyle{fancy}\n"
    "\\fancyhf{}\n"
    "\\fancyhead[R]{\\thepage}\n"
    "\\renewcommand{\\headrulewidth}{0pt}\n"
    "\\begin{document}\n"
)
_POSTAMBLE = "\n\\end{document}\n"


def _escape_latex(text: str) -> str:
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def _is_blank(text: str) -> bool:
    return text.strip() == ""


class _AnswerHtmlParser(HTMLParser):
    """Tokenizes the rich-text editor's saved answerHtml (a flat run of
    text, <br>, and <img> tags — block elements are already flattened to
    <br> upstream by the editor's own sanitize step).

    Produces raw tokens only; grouping consecutive <br>s into paragraph
    vs. hard breaks and deciding which equations stand alone on their own
    line happens afterwards in `_render_tokens`, which needs to look at a
    token's neighbors — not available while still streaming through
    HTMLParser's callbacks.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens: list[tuple] = []

    def handle_starttag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def _handle_tag(self, tag, attrs):
        if tag == "br":
            self.tokens.append(("br",))
        elif tag == "img":
            self._handle_img(dict(attrs))

    def handle_data(self, data):
        self.tokens.append(("text", data))

    def _handle_img(self, attrs: dict):
        src = attrs.get("src") or ""
        alt = attrs.get("alt") or ""

        if src.startswith("data:"):
            self.tokens.append(("img_data", src))
            return

        # Equation images: the editor sets both `src=".../math.svg?latex=..."`
        # and `alt=<raw latex>` — alt is already plain, un-encoded LaTeX.
        latex = alt or self._latex_from_math_svg_src(src)
        if latex:
            self.tokens.append(("img_eq", latex))

    @staticmethod
    def _latex_from_math_svg_src(src: str) -> str:
        query = urllib.parse.urlparse(src).query
        values = urllib.parse.parse_qs(query).get("latex")
        return urllib.parse.unquote(values[0]) if values else ""


def _prev_significant(tokens: list[tuple], i: int) -> tuple | None:
    """Nearest earlier token, skipping over blank/whitespace-only text."""
    i -= 1
    while i >= 0:
        if tokens[i][0] == "text" and _is_blank(tokens[i][1]):
            i -= 1
            continue
        return tokens[i]
    return None


def _next_significant(tokens: list[tuple], i: int) -> tuple | None:
    i += 1
    while i < len(tokens):
        if tokens[i][0] == "text" and _is_blank(tokens[i][1]):
            i += 1
            continue
        return tokens[i]
    return None


def _render_tokens(tokens: list[tuple], assets_dir: Path) -> str:
    # Pass 1: collapse runs of consecutive <br> tokens. A single <br> is a
    # deliberate mid-thought line break (kept tight, no extra space); two
    # or more in a row is the user visually separating sections and reads
    # far better as a real LaTeX paragraph break than as several stacked
    # hard breaks, which (unlike a word processor) each force a full,
    # non-collapsing blank line and were producing huge, uneven gaps.
    grouped: list[tuple] = []
    i = 0
    while i < len(tokens):
        if tokens[i][0] == "br":
            run = 0
            while i < len(tokens) and tokens[i][0] == "br":
                run += 1
                i += 1
            grouped.append(("parabreak" if run > 1 else "hardbreak",))
        else:
            grouped.append(tokens[i])
            i += 1

    # Pass 2: an equation with only breaks/blank-text (or the document
    # edge) on both sides sits alone on its own line — typeset it as
    # centered display math instead of a small inline fraction, and
    # absorb the adjacent break tokens into its own spacing so it doesn't
    # end up with a break *and* a blank paragraph line stacked together.
    skip: set[int] = set()
    is_standalone: dict[int, bool] = {}
    for idx, tok in enumerate(grouped):
        if tok[0] != "img_eq":
            continue
        prev_tok = _prev_significant(grouped, idx)
        next_tok = _next_significant(grouped, idx)
        prev_ok = prev_tok is None or prev_tok[0] in ("parabreak", "hardbreak")
        next_ok = next_tok is None or next_tok[0] in ("parabreak", "hardbreak")
        is_standalone[idx] = prev_ok and next_ok
        if is_standalone[idx]:
            if idx > 0 and grouped[idx - 1][0] in ("parabreak", "hardbreak"):
                skip.add(idx - 1)
            if idx + 1 < len(grouped) and grouped[idx + 1][0] in ("parabreak", "hardbreak"):
                skip.add(idx + 1)

    # Pass 3: render.
    image_count = 0
    parts: list[str] = []
    for idx, tok in enumerate(grouped):
        if idx in skip:
            continue
        kind = tok[0]
        if kind == "text":
            parts.append(_escape_latex(tok[1]))
        elif kind == "hardbreak":
            parts.append(_LATEX_HARDBREAK)
        elif kind == "parabreak":
            parts.append("\n\n")
        elif kind == "img_eq":
            latex = tok[1]
            if is_standalone[idx]:
                parts.append(f"\n\n\\[{latex}\\]\n\n")
            else:
                parts.append(f"${latex}$")
        elif kind == "img_data":
            image_count += 1
            filename = _save_data_image(tok[1], assets_dir, image_count)
            if filename:
                parts.append(f"\n\n\\includegraphics[width=0.8\\linewidth]{{{filename}}}\n\n")

    return "".join(parts).strip()


def _save_data_image(data_url: str, assets_dir: Path, index: int) -> str | None:
    match = _DATA_IMAGE_RE.match(data_url)
    if not match:
        return None
    ext, b64data = match.groups()
    ext = "jpg" if ext == "jpeg" else ext
    try:
        data = base64.b64decode(b64data)
    except (ValueError, binascii.Error):
        return None

    filename = f"image{index}.{ext}"
    (assets_dir / filename).write_bytes(data)
    return filename


def answer_html_to_tex(answer_html: str, assets_dir: Path, center: bool = True) -> str:
    """Renders a document's saved rich-text content into a full, compilable
    .tex source. Embedded equations (<img alt="latex">) become inline
    `$latex$` math, or `\\[latex\\]` display math (always centered,
    regardless of `center` — that's inherent to LaTeX's display-math
    environment) when the equation sits alone on its own line; pasted
    screenshots (base64 <img src="data:...">) are decoded to files in
    `assets_dir` and included via \\includegraphics.

    `center` controls only the surrounding body *text*: centered (the
    default, matching how it looks in the editor) or left-aligned/
    justified.
    """
    parser = _AnswerHtmlParser()
    parser.feed(answer_html or "")
    body = _render_tokens(parser.tokens, assets_dir) or "% (empty document)"
    preamble = _PREAMBLE + ("\\centering\n" if center else "")
    return preamble + body + _POSTAMBLE
