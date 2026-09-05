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
_LATEX_LINEBREAK = r"\\\relax" + "\n"

_DATA_IMAGE_RE = re.compile(r"^data:image/(\w+);base64,(.+)$", re.DOTALL)

_PREAMBLE = (
    "\\documentclass{article}\n"
    "\\usepackage{amsmath,amssymb,graphicx}\n"
    "\\begin{document}\n"
)
_POSTAMBLE = "\n\\end{document}\n"


def _escape_latex(text: str) -> str:
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


class _AnswerHtmlParser(HTMLParser):
    """Converts the rich-text editor's saved answerHtml (a flat run of
    text, <br>, and <img> tags — block elements are already flattened to
    <br> upstream by the editor's own sanitize step) into LaTeX source.
    """

    def __init__(self, assets_dir: Path):
        super().__init__(convert_charrefs=True)
        self.assets_dir = assets_dir
        self._parts: list[str] = []
        self._image_count = 0

    def handle_starttag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def _handle_tag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "br":
            self._parts.append(_LATEX_LINEBREAK)
        elif tag == "img":
            self._handle_img(attrs_dict)

    def handle_data(self, data):
        self._parts.append(_escape_latex(data))

    def _handle_img(self, attrs: dict):
        src = attrs.get("src") or ""
        alt = attrs.get("alt") or ""

        if src.startswith("data:"):
            filename = self._save_data_image(src)
            if filename:
                self._parts.append(
                    f"\n\n\\includegraphics[width=0.8\\linewidth]{{{filename}}}\n\n"
                )
            return

        # Equation images: the editor sets both `src=".../math.svg?latex=..."`
        # and `alt=<raw latex>` — alt is already plain, un-encoded LaTeX.
        latex = alt or self._latex_from_math_svg_src(src)
        if latex:
            self._parts.append(f"${latex}$")

    @staticmethod
    def _latex_from_math_svg_src(src: str) -> str:
        query = urllib.parse.urlparse(src).query
        values = urllib.parse.parse_qs(query).get("latex")
        return urllib.parse.unquote(values[0]) if values else ""

    def _save_data_image(self, data_url: str) -> str | None:
        match = _DATA_IMAGE_RE.match(data_url)
        if not match:
            return None
        ext, b64data = match.groups()
        ext = "jpg" if ext == "jpeg" else ext
        try:
            data = base64.b64decode(b64data)
        except (ValueError, binascii.Error):
            return None

        self._image_count += 1
        filename = f"image{self._image_count}.{ext}"
        (self.assets_dir / filename).write_bytes(data)
        return filename

    def get_body(self) -> str:
        return "".join(self._parts).strip()


def answer_html_to_tex(answer_html: str, assets_dir: Path) -> str:
    """Renders a document's saved rich-text content into a full, compilable
    .tex source. Embedded equations (<img alt="latex">) become `$latex$`;
    pasted screenshots (base64 <img src="data:...">) are decoded to files
    in `assets_dir` and included via \\includegraphics.
    """
    parser = _AnswerHtmlParser(assets_dir)
    parser.feed(answer_html or "")
    body = parser.get_body() or "% (empty document)"
    return _PREAMBLE + body + _POSTAMBLE
