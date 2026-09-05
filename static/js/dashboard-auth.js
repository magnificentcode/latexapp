(function () {
  const listEl = document.getElementById('doc-list');
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

  async function loadDocuments() {
    const response = await fetch('/api/documents', { credentials: 'include' });
    if (response.status === 401) {
      window.location.href = '/login';
      return;
    }
    const docs = await response.json();

    if (docs.length === 0) {
      emptyEl.style.display = 'block';
      listEl.innerHTML = '';
      return;
    }

    emptyEl.style.display = 'none';
    listEl.innerHTML = docs
      .map(
        (doc) => `
        <div class="doc-item">
          <a href="/editor?id=${doc.id}" style="flex:1; text-decoration:none; color:inherit;">
            <div class="doc-title">${escapeHtml(doc.title)}</div>
            <div class="doc-updated">Updated ${formatRelativeTime(doc.updated_at)}</div>
          </a>
          <button class="doc-delete" data-id="${doc.id}">Delete</button>
        </div>`
      )
      .join('');

    listEl.querySelectorAll('.doc-delete').forEach((btn) => {
      btn.addEventListener('click', async (event) => {
        event.preventDefault();
        if (!confirm('Delete this document?')) return;
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
