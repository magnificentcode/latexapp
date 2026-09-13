import base64

import pytest

from app.services.latex_render import answer_html_to_tex

# 1x1 transparent PNG — content doesn't matter, the renderer just base64
# decodes and writes bytes to disk without validating image data.
TINY_PNG_B64 = base64.b64encode(b"not-a-real-png-but-bytes-are-bytes").decode()


def _body(tex: str) -> str:
    """Strips the fixed preamble/postamble so assertions focus on content."""
    start = tex.index("\\begin{document}") + len("\\begin{document}\n")
    end = tex.index("\\end{document}")
    return tex[start:end]


class TestEscaping:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("100%", r"100\%"),
            ("a & b", r"a \& b"),
            ("$5", r"\$5"),
            ("#1", r"\#1"),
            ("a_b", r"a\_b"),
            ("{x}", r"\{x\}"),
            ("a~b", r"a\textasciitilde{}b"),
            ("2^3", r"2\textasciicircum{}3"),
            ("C:\\path", r"C:\textbackslash{}path"),
        ],
    )
    def test_special_characters_are_escaped(self, tmp_path, raw, expected):
        tex = answer_html_to_tex(raw, tmp_path)
        assert expected in _body(tex)

    def test_plain_text_is_untouched(self, tmp_path):
        tex = answer_html_to_tex("Exercise 1: solve for x", tmp_path)
        assert "Exercise 1: solve for x" in _body(tex)

    def test_html_entities_are_decoded_then_escaped(self, tmp_path):
        # HTMLParser(convert_charrefs=True) turns &amp; into a literal "&"
        # before our own escaping ever sees it.
        tex = answer_html_to_tex("A &amp; B", tmp_path)
        assert r"A \& B" in _body(tex)


class TestLineBreaks:
    def test_single_br_is_a_hard_break(self, tmp_path):
        tex = answer_html_to_tex("line one<br>line two", tmp_path)
        body = _body(tex)
        assert "line one" in body and "line two" in body
        assert r"\\\relax" in body
        assert "\n\n" not in body

    def test_multiple_consecutive_br_become_a_paragraph_break(self, tmp_path):
        tex = answer_html_to_tex("para one<br><br>para two", tmp_path)
        body = _body(tex)
        assert "\n\npara two" in body or "para one\n\n" in body
        assert r"\\\relax" not in body

    def test_three_or_more_br_still_collapse_to_one_paragraph_break(self, tmp_path):
        tex = answer_html_to_tex("a<br><br><br>b", tmp_path)
        body = _body(tex)
        assert body.count("\n\n") == 1


class TestEquations:
    def test_inline_equation_uses_dollar_signs(self, tmp_path):
        html = 'before <img alt="x^2" src="/math.svg?latex=x%5E2"> after'
        tex = answer_html_to_tex(html, tmp_path)
        assert "$x^2$" in _body(tex)
        assert r"\[" not in tex

    def test_standalone_equation_between_breaks_uses_display_math(self, tmp_path):
        html = 'text<br><br><img alt="E=mc^2" src="x"><br><br>more text'
        tex = answer_html_to_tex(html, tmp_path)
        body = _body(tex)
        assert r"\[E=mc^2\]" in body

    def test_standalone_equation_at_document_edges_uses_display_math(self, tmp_path):
        html = '<img alt="a+b" src="x">'
        tex = answer_html_to_tex(html, tmp_path)
        assert r"\[a+b\]" in _body(tex)

    def test_equation_surrounded_by_blank_text_is_still_standalone(self, tmp_path):
        html = 'a<br><br>   <img alt="x" src="y">   <br><br>b'
        tex = answer_html_to_tex(html, tmp_path)
        assert r"\[x\]" in _body(tex)

    def test_display_equation_absorbs_adjacent_break_tokens(self, tmp_path):
        # The paragraph breaks around the standalone equation must not also
        # render as their own blank lines, or the gap doubles up.
        html = 'a<br><br><img alt="x" src="y"><br><br>b'
        tex = answer_html_to_tex(html, tmp_path)
        body = _body(tex)
        assert r"\\\relax" not in body
        assert body.count("\n\n\\[x\\]\n\n") == 1

    def test_latex_taken_from_alt_attribute_preferred_over_src(self, tmp_path):
        html = '<img alt="y" src="/math.svg?latex=x">'
        tex = answer_html_to_tex(html, tmp_path)
        assert "y" in _body(tex) and "$x$" not in _body(tex)

    def test_latex_extracted_from_src_when_alt_missing(self, tmp_path):
        html = '<img src="/math.svg?latex=%5Cfrac%7B1%7D%7B2%7D">'
        tex = answer_html_to_tex(html, tmp_path)
        assert r"\[\frac{1}{2}\]" in _body(tex)

    def test_equation_latex_is_not_escaped(self, tmp_path):
        # Equation content is real LaTeX math, not prose — it must pass
        # through untouched (escaping $, {, } etc. would break it).
        html = '<img alt="\\frac{a}{b} \\& x_1" src="y">'
        tex = answer_html_to_tex(html, tmp_path)
        assert r"\frac{a}{b} \& x_1" in _body(tex)


class TestImages:
    def test_data_image_is_written_to_assets_dir_and_included(self, tmp_path):
        html = f'<img src="data:image/png;base64,{TINY_PNG_B64}">'
        tex = answer_html_to_tex(html, tmp_path)
        body = _body(tex)
        assert r"\includegraphics[width=0.8\linewidth]{image1.png}" in body
        saved = tmp_path / "image1.png"
        assert saved.exists()
        assert saved.read_bytes() == base64.b64decode(TINY_PNG_B64)

    def test_jpeg_extension_is_normalized_to_jpg(self, tmp_path):
        html = f'<img src="data:image/jpeg;base64,{TINY_PNG_B64}">'
        tex = answer_html_to_tex(html, tmp_path)
        assert (tmp_path / "image1.jpg").exists()
        assert "image1.jpg" in _body(tex)

    def test_multiple_images_get_incrementing_filenames(self, tmp_path):
        html = (
            f'<img src="data:image/png;base64,{TINY_PNG_B64}">'
            f'<img src="data:image/png;base64,{TINY_PNG_B64}">'
        )
        tex = answer_html_to_tex(html, tmp_path)
        assert "image1.png" in _body(tex)
        assert "image2.png" in _body(tex)

    def test_malformed_base64_is_silently_skipped(self, tmp_path):
        html = '<img src="data:image/png;base64,not-valid-base64!!!">'
        tex = answer_html_to_tex(html, tmp_path)
        assert "includegraphics" not in _body(tex)
        assert list(tmp_path.iterdir()) == []

    def test_non_data_non_equation_img_is_ignored(self, tmp_path):
        html = '<img src="https://example.com/pic.png">before'
        tex = answer_html_to_tex(html, tmp_path)
        assert "before" in _body(tex)
        assert "includegraphics" not in _body(tex)


class TestCentering:
    def test_center_true_adds_centering_command(self, tmp_path):
        tex = answer_html_to_tex("hi", tmp_path, center=True)
        assert r"\centering" in tex

    def test_center_false_omits_centering_command(self, tmp_path):
        tex = answer_html_to_tex("hi", tmp_path, center=False)
        assert r"\centering" not in tex

    def test_display_math_is_unaffected_by_center_flag(self, tmp_path):
        # \[...\] is inherently centered by LaTeX regardless of body
        # alignment — center only controls surrounding prose.
        html = '<img alt="x" src="y">'
        centered = answer_html_to_tex(html, tmp_path, center=True)
        left_aligned = answer_html_to_tex(html, tmp_path, center=False)
        assert r"\[x\]" in _body(centered)
        assert r"\[x\]" in _body(left_aligned)


class TestEdgeCases:
    def test_empty_input_produces_placeholder_comment(self, tmp_path):
        tex = answer_html_to_tex("", tmp_path)
        assert "% (empty document)" in _body(tex)

    def test_none_like_falsy_input_is_treated_as_empty(self, tmp_path):
        tex = answer_html_to_tex(None, tmp_path)
        assert "% (empty document)" in _body(tex)

    def test_whitespace_only_input_produces_placeholder_comment(self, tmp_path):
        tex = answer_html_to_tex("   <br><br>   ", tmp_path)
        assert "% (empty document)" in _body(tex)

    def test_output_is_wrapped_in_a_compilable_document_shell(self, tmp_path):
        tex = answer_html_to_tex("hi", tmp_path)
        assert tex.startswith("\\documentclass")
        assert "\\begin{document}" in tex
        assert tex.rstrip().endswith("\\end{document}")
