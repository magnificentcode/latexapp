// Lightweight LaTeX -> preview splitter. Not a full LaTeX engine — just
// enough to give instant visual feedback while typing. Splits raw source
// into text and math segments; math segments get rendered with KaTeX,
// text segments are shown close to verbatim (macros like \section{} are
// NOT expanded here — that's what the real "Compile to PDF" button is
// for, via a full tectonic compile on the server).

// Display forms ($$...$$, \[...\]) are checked before inline forms
// ($...$, \(...\)) so a display block isn't mistaken for two inline ones.
const MATH_PATTERN =
  /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;

export function splitLatex(source) {
  const segments = [];
  let lastIndex = 0;
  let match;

  MATH_PATTERN.lastIndex = 0;
  while ((match = MATH_PATTERN.exec(source)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', value: source.slice(lastIndex, match.index) });
    }

    const [, display1, display2, inline1, inline2] = match;
    if (display1 !== undefined || display2 !== undefined) {
      segments.push({ type: 'display', value: display1 ?? display2 });
    } else {
      segments.push({ type: 'inline', value: inline1 ?? inline2 });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < source.length) {
    segments.push({ type: 'text', value: source.slice(lastIndex) });
  }

  return segments;
}
