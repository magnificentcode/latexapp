import { useCallback, useEffect, useRef, useState } from 'react';
import { createEditor } from './codemirrorSetup';
import PreviewPane from './PreviewPane';

const AUTOSAVE_DELAY_MS = 2000;

async function fetchJson(url, options) {
  const response = await fetch(url, { credentials: 'include', ...options });
  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Not authenticated');
  }
  return response;
}

export default function LatexEditor({ documentId }) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saveStatus, setSaveStatus] = useState('Loading…');
  const [compileState, setCompileState] = useState({ status: 'idle' });

  const editorContainerRef = useRef(null);
  const editorViewRef = useRef(null);
  const contentRef = useRef('');
  const titleRef = useRef('');
  const autosaveTimerRef = useRef(null);

  const saveDocument = useCallback(async () => {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    setSaveStatus('Saving…');
    await fetchJson(`/api/documents/${documentId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: titleRef.current, content: contentRef.current }),
    });
    setSaveStatus('Saved');
  }, [documentId]);

  const scheduleAutosave = useCallback(() => {
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    setSaveStatus('Editing…');
    autosaveTimerRef.current = setTimeout(saveDocument, AUTOSAVE_DELAY_MS);
  }, [saveDocument]);

  // Initial load.
  useEffect(() => {
    (async () => {
      const response = await fetchJson(`/api/documents/${documentId}`);
      const doc = await response.json();
      setTitle(doc.title);
      setContent(doc.content);
      contentRef.current = doc.content;
      titleRef.current = doc.title;
      setSaveStatus('Saved');
    })();
  }, [documentId]);

  // Mount CodeMirror once we have initial content.
  useEffect(() => {
    if (!editorContainerRef.current || editorViewRef.current || saveStatus === 'Loading…') {
      return;
    }
    editorViewRef.current = createEditor({
      parent: editorContainerRef.current,
      doc: contentRef.current,
      onChange: (value) => {
        contentRef.current = value;
        setContent(value);
        scheduleAutosave();
      },
    });
    return () => {
      editorViewRef.current?.destroy();
      editorViewRef.current = null;
    };
  }, [saveStatus, scheduleAutosave]);

  function handleTitleChange(event) {
    const value = event.target.value;
    setTitle(value);
    titleRef.current = value;
    scheduleAutosave();
  }

  async function handleCompile() {
    await saveDocument();
    setCompileState({ status: 'compiling' });
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
        setCompileState({ status: 'error', message: data.detail, log: data.log });
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setCompileState({
          status: 'error',
          message: data.detail || `Compile failed (${response.status})`,
        });
        return;
      }
      const blob = await response.blob();
      const pdfUrl = URL.createObjectURL(blob);
      setCompileState({ status: 'success', pdfUrl });
    } catch (err) {
      setCompileState({ status: 'error', message: 'Could not reach the server.' });
    }
  }

  function closeCompilePanel() {
    if (compileState.pdfUrl) URL.revokeObjectURL(compileState.pdfUrl);
    setCompileState({ status: 'idle' });
  }

  return (
    <div className="editor-shell">
      <header className="editor-header">
        <a href="/dashboard" className="editor-back">
          ← Documents
        </a>
        <input
          className="editor-title-input"
          value={title}
          onChange={handleTitleChange}
          placeholder="Untitled"
        />
        <span className="editor-save-status">{saveStatus}</span>
        <button className="btn btn-secondary" onClick={saveDocument}>
          Save
        </button>
        <button
          className="btn"
          onClick={handleCompile}
          disabled={compileState.status === 'compiling'}
        >
          {compileState.status === 'compiling' ? 'Compiling…' : 'Compile to PDF'}
        </button>
      </header>

      <div className="editor-panes">
        <div className="editor-pane" ref={editorContainerRef} />
        <PreviewPane source={content} />
      </div>

      {compileState.status === 'error' && (
        <div className="compile-panel compile-panel-error">
          <div className="compile-panel-header">
            <strong>{compileState.message}</strong>
            <button className="btn btn-secondary" onClick={closeCompilePanel}>
              Close
            </button>
          </div>
          {compileState.log && <pre className="compile-log">{compileState.log}</pre>}
        </div>
      )}

      {compileState.status === 'success' && (
        <div className="compile-panel">
          <div className="compile-panel-header">
            <strong>Compiled PDF</strong>
            <div>
              <a href={compileState.pdfUrl} target="_blank" rel="noreferrer">
                Open in new tab
              </a>
              {' · '}
              <a href={compileState.pdfUrl} download={`${title || 'document'}.pdf`}>
                Download
              </a>
              <button className="btn btn-secondary" onClick={closeCompilePanel}>
                Close
              </button>
            </div>
          </div>
          <iframe className="compile-pdf-frame" src={compileState.pdfUrl} title="Compiled PDF" />
        </div>
      )}
    </div>
  );
}
