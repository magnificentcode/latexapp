import 'katex/dist/katex.min.css';
import { createRoot } from 'react-dom/client';
import LatexEditor from './components/LatexEditor';
import './editor.css';

const rootEl = document.getElementById('latex-editor-root');
if (rootEl) {
  const documentId = rootEl.dataset.documentId;
  if (!documentId) {
    window.location.href = '/dashboard';
  } else {
    createRoot(rootEl).render(<LatexEditor documentId={documentId} />);
  }
}
