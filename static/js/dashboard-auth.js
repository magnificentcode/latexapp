(function () {
  const listEl = document.getElementById('doc-list');
  const skeletonEl = document.getElementById('doc-list-skeleton');
  const emptyEl = document.getElementById('empty-state');

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value;
    return div.innerHTML;
  }

  function formatRelativeTime(isoString) {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const minutes = Math.round(diffMs / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.round(hours / 24);
    return `${days}d ago`;
  }

  // Two-step delete instead of a native confirm() dialog or a modal: the
  // first click arms a button ("Sure?", danger-colored); a second click
  // within a few seconds actually deletes. Clicking elsewhere, or letting
  // it time out, disarms it. State lives at module scope (not inside
  // loadDocuments) so re-rendering the list after a delete doesn't pile
  // up duplicate document-level click listeners.
  let armedBtn = null;
  let armedTimer = null;

  function disarm() {
    if (armedBtn) {
      armedBtn.classList.remove('doc-delete-armed');
      armedBtn.title = 'Delete';
    }
    clearTimeout(armedTimer);
    armedBtn = null;
  }

  document.addEventListener('click', (event) => {
    if (armedBtn && !armedBtn.contains(event.target)) disarm();
  });

  async function loadDocuments() {
    const response = await fetch('/api/documents', { credentials: 'include' });
    if (response.status === 401) {
      window.location.href = '/login';
      return;
    }
    const docs = await response.json();
    skeletonEl.hidden = true;

    if (docs.length === 0) {
      emptyEl.hidden = false;
      listEl.hidden = true;
      listEl.innerHTML = '';
      return;
    }

    emptyEl.hidden = true;
    listEl.hidden = false;
    listEl.innerHTML = docs
      .map(
        (doc) => `
        <div class="doc-item">
          <a href="/editor?id=${doc.id}" class="doc-item-link">
            <div class="doc-title">${escapeHtml(doc.title)}</div>
            <div class="doc-updated">Updated ${formatRelativeTime(doc.updated_at)}</div>
          </a>
          <button class="doc-delete" data-id="${doc.id}" title="Delete">
            <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.4">
              <path d="M3 4.5h10M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5M4.5 4.5l.6 8.4a1 1 0 0 0 1 .93h3.8a1 1 0 0 0 1-.93l.6-8.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>`
      )
      .join('');

    listEl.querySelectorAll('.doc-delete').forEach((btn) => {
      btn.addEventListener('click', async (event) => {
        event.preventDefault();

        if (btn !== armedBtn) {
          disarm();
          armedBtn = btn;
          btn.classList.add('doc-delete-armed');
          btn.title = 'Click again to delete';
          armedTimer = setTimeout(disarm, 3000);
          return;
        }

        disarm();
        await fetch(`/api/documents/${btn.dataset.id}`, {
          method: 'DELETE',
          credentials: 'include',
        });
        loadDocuments();
      });
    });
  }

  document.getElementById('new-doc-btn').addEventListener('click', async () => {
    const response = await fetch('/api/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });
    const doc = await response.json();
    window.location.href = `/editor?id=${doc.id}`;
  });

  document.getElementById('logout-btn').addEventListener('click', async () => {
    await fetch('/api/logout', { method: 'POST', credentials: 'include' });
    window.location.href = '/login';
  });

  loadDocuments();
})();
