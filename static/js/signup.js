(function () {
  const form = document.getElementById('signup-form');
  const errorEl = document.getElementById('error');

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.add('visible');
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorEl.classList.remove('visible');

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
      const response = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        showError(data.detail || 'Could not create account.');
        return;
      }

      window.location.href = '/dashboard';
    } catch (err) {
      showError('Could not reach the server. Please try again.');
    }
  });
})();
