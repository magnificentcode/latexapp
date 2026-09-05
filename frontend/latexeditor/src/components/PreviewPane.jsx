import katex from 'katex';
import { useMemo } from 'react';
import { splitLatex } from './latexSplitter';

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderTextSegment(value) {
  return escapeHtml(value)
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${paragraph.replace(/\n/g, '<br/>')}</p>`)
    .join('');
}

function renderSegment(segment) {
  if (segment.type === 'text') {
    return renderTextSegment(segment.value);
  }
  // throwOnError: false keeps the rest of the preview alive when the
  // user is mid-typing an incomplete expression (e.g. "$x^{").
  return katex.renderToString(segment.value, {
    throwOnError: false,
    displayMode: segment.type === 'display',
  });
}

export default function PreviewPane({ source }) {
  const html = useMemo(
    () => splitLatex(source).map(renderSegment).join(''),
    [source]
  );

  return (
    <div className="preview-pane" dangerouslySetInnerHTML={{ __html: html }} />
  );
}
