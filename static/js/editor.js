const AUTOSAVE_DELAY_MS = 2000;

const documentId = new URLSearchParams(location.search).get('id');
if (!documentId) {
  window.location.href = '/dashboard';
}

const titleInput = document.getElementById('title-input');
const saveStatus = document.getElementById('save-status');
const saveBtn = document.getElementById('save-btn');
const exportBtn = document.getElementById('export-btn');
const centerToggle = document.getElementById('center-toggle');
const compileBtn = document.getElementById('compile-btn');
const compilePanel = document.getElementById('compile-panel');
const compilePanelTitle = document.getElementById('compile-panel-title');
const compileCloseBtn = document.getElementById('compile-close-btn');
const pdfFrame = document.getElementById('compile-pdf-frame');
const compileLog = document.getElementById('compile-log');
const openTabLink = document.getElementById('compile-open-tab');
const downloadLink = document.getElementById('compile-download');
const editorRoot = document.getElementById('rich-text-editor-root');

let latestAnswer = { answerHtml: '', answerText: '', imageCount: 0 };
let autosaveTimer = null;
let currentPdfUrl = null;

// The header can wrap to two lines on narrow windows (title + 3 buttons
// don't always fit one row) — editor.css reads this to keep the rich-text
// editor's own floating toolbar (position:fixed) below the header instead
// of a hardcoded pixel guess that breaks whenever the header's height
// changes.
const editorHeader = document.querySelector('.editor-header');
function syncHeaderHeight() {
  document.documentElement.style.setProperty(
    '--editor-header-height',
    `${editorHeader.getBoundingClientRect().height}px`
  );
}
syncHeaderHeight();
window.addEventListener('resize', syncHeaderHeight);

async function fetchJson(url, options) {
  const response = await fetch(url, { credentials: 'include', ...options });
  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Not authenticated');
  }
  return response;
}

async function saveDocument() {
  if (autosaveTimer) {
    clearTimeout(autosaveTimer);
    autosaveTimer = null;
  }
  saveStatus.textContent = 'Saving…';
  await fetchJson(`/api/documents/${documentId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: titleInput.value,
      content: latestAnswer.answerHtml,
      center_text: centerToggle.checked,
    }),
  });
  saveStatus.textContent = 'Saved';
}

function scheduleAutosave() {
  if (autosaveTimer) clearTimeout(autosaveTimer);
  saveStatus.textContent = 'Editing…';
  autosaveTimer = setTimeout(saveDocument, AUTOSAVE_DELAY_MS);
}

saveBtn.addEventListener('click', saveDocument);

exportBtn.addEventListener('click', async () => {
  await saveDocument();
  // A plain navigation (not fetch+blob) so the browser handles the
  // Content-Disposition: attachment response as a download on its own,
  // without leaving the editor page.
  window.location.href = `/api/documents/${documentId}/export`;
});
titleInput.addEventListener('input', scheduleAutosave);
centerToggle.addEventListener('change', saveDocument);

// The real exam answer sheet has no spellcheck/autocorrect/predictive-text —
// the package hardcodes spellCheck={false} on the contenteditable itself,
// but leaves autocorrect/autocapitalize unset (iOS/Android keyboards use
// those for inline suggestions), so they're set by hand once the element
// exists.
function disableTextSuggestions(el) {
  el.setAttribute('spellcheck', 'false');
  el.setAttribute('autocorrect', 'off');
  el.setAttribute('autocapitalize', 'off');
  el.setAttribute('autocomplete', 'off');
}

// The npm package only ships Finnish/Swedish UI strings — this app is
// English, so known FI strings are swapped for English ones once they
// appear. Pragmatic text-replacement rather than forking the library.
const LABEL_MAP = [
  ['Lisää kaava', 'Insert equation'],
  ['Näytä ohjeet', 'Show help'],
  ['Kuvakaappaukset', 'Screenshots'],
  ['Kaavat', 'Equations'],
  ['Pikakomennot kaavassa:', 'Shortcuts inside an equation:'],
  ['Jakoviiva', 'Fraction bar'],
  ['Kertomerkki', 'Multiplication sign'],
  ['Yläindeksi', 'Superscript'],
  ['Alaindeksi', 'Subscript'],
  ['Lisää kaava seuraavalle riville', 'Insert equation on next line'],
  ['Sulje kaava', 'Close equation'],
  ['Virhe LaTeX-koodissa', 'Error in LaTeX code'],
  [
    'Tee kuva haluamallasi ohjelmalla. Napsauta yläpalkista kuvakaappauskuvaketta ja rajaa haluamasi kuva-alue näytöltä.',
    'Take a screenshot with the tool of your choice, then paste it into the answer with',
  ],
  [' liittää kuvan vastauskenttään kursorin kohdalle. Voit vaihtaa kuvan paikkaa raahaamalla tai leikkaamalla kuvan komennolla ', '. Move an image by dragging it, or cut it with '],
  [' ja liittämällä sen komennolla ', ' and paste it with '],
  [' haluamaasi paikkaan.', ' wherever you want it.'],
  ['Kaava lisätään komennolla ', 'Insert an equation with '],
];

function relabelToEnglish(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let node;
  while ((node = walker.nextNode())) nodes.push(node);
  for (const textNode of nodes) {
    for (const [fi, en] of LABEL_MAP) {
      if (textNode.textContent.includes(fi)) {
        textNode.textContent = textNode.textContent.replace(fi, en);
      }
    }
  }
}

function watchForEnglishRelabeling() {
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const added of mutation.addedNodes) {
        if (added.nodeType === Node.ELEMENT_NODE) relabelToEnglish(added);
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function fallbackEditor() {
  editorRoot.innerHTML =
    '<div id="answer-editor" contenteditable="true" class="fallback-editor" style="min-height:60vh;padding:1.5rem 2rem;"></div>';
  const fallback = document.getElementById('answer-editor');
  disableTextSuggestions(fallback);
  fallback.addEventListener('input', () => {
    latestAnswer = { answerHtml: fallback.innerHTML, answerText: fallback.textContent || '', imageCount: 0 };
    scheduleAutosave();
  });
}

function initEditor(doc) {
  titleInput.value = doc.title;
  centerToggle.checked = doc.center_text;
  saveStatus.textContent = 'Saved';
  latestAnswer = { answerHtml: doc.content, answerText: '', imageCount: 0 };

  if (typeof window.makeRichText !== 'function') {
    fallbackEditor();
    return;
  }

  try {
    window.makeRichText({
      container: editorRoot,
      language: 'FI',
      // '' (not '/') matters: the package builds the equation image URL
      // as `${baseUrl}/math.svg?latex=...` — with '/' that becomes
      // `//math.svg?...`, a protocol-relative URL resolved against a
      // nonexistent host instead of hitting our own /math.svg route.
      baseUrl: '',
      allowedFileTypes: ['image/png', 'image/jpeg'],
      initialValue: doc.content,
      onValueChange: (answer) => {
        latestAnswer = answer;
        scheduleAutosave();
      },
      textAreaProps: { id: 'answer-editor' },
    });

    watchForEnglishRelabeling();

    // makeRichText renders asynchronously (a React tree mounted into the
    // container) — watch for the contenteditable instead of guessing a
    // delay.
    const existing = editorRoot.querySelector('[data-testid="rich-text-editor"]');
    if (existing) {
      disableTextSuggestions(existing);
    } else {
      const observer = new MutationObserver(() => {
        const el = editorRoot.querySelector('[data-testid="rich-text-editor"]');
        if (el) {
          disableTextSuggestions(el);
          observer.disconnect();
        }
      });
      observer.observe(editorRoot, { childList: true, subtree: true });
    }
  } catch (err) {
    console.error('Rich text editor init failed:', err);
    fallbackEditor();
  }
}

function closeCompilePanel() {
  if (currentPdfUrl) {
    URL.revokeObjectURL(currentPdfUrl);
    currentPdfUrl = null;
  }
  compilePanel.hidden = true;
  pdfFrame.hidden = true;
  pdfFrame.src = '';
  compileLog.hidden = true;
}

compileCloseBtn.addEventListener('click', closeCompilePanel);

compileBtn.addEventListener('click', async () => {
  await saveDocument();

  compileBtn.disabled = true;
  compileBtn.textContent = 'Compiling…';

  try {
    const response = await fetch(`/api/documents/${documentId}/compile`, {
      method: 'POST',
      credentials: 'include',
    });

    if (response.status === 401) {
      window.location.href = '/login';
      return;
    }

    if (response.status === 422) {
      const data = await response.json();
      compilePanelTitle.textContent = data.detail || 'LaTeX compile failed';
      compileLog.textContent = data.log || '';
      compileLog.hidden = false;
      pdfFrame.hidden = true;
      compilePanel.hidden = false;
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      compilePanelTitle.textContent = data.detail || `Compile failed (${response.status})`;
      compileLog.hidden = true;
      pdfFrame.hidden = true;
      compilePanel.hidden = false;
      return;
    }

    const blob = await response.blob();
    if (currentPdfUrl) URL.revokeObjectURL(currentPdfUrl);
    currentPdfUrl = URL.createObjectURL(blob);

    compilePanelTitle.textContent = 'Compiled PDF';
    pdfFrame.src = currentPdfUrl;
    pdfFrame.hidden = false;
    compileLog.hidden = true;
    openTabLink.href = currentPdfUrl;
    downloadLink.href = currentPdfUrl;
    downloadLink.download = `${titleInput.value || 'document'}.pdf`;
    compilePanel.hidden = false;
  } catch (err) {
    compilePanelTitle.textContent = 'Could not reach the server.';
    compileLog.hidden = true;
    pdfFrame.hidden = true;
    compilePanel.hidden = false;
  } finally {
    compileBtn.disabled = false;
    compileBtn.textContent = 'Compile to PDF';
  }
});

(async () => {
  const response = await fetchJson(`/api/documents/${documentId}`);
  const doc = await response.json();
  initEditor(doc);
})();
