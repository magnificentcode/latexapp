(function () {
  const form = document.getElementById('login-form');
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
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        showError(data.detail || 'Invalid email or password.');
        return;
      }

      window.location.href = '/dashboard';
    } catch (err) {
      showError('Could not reach the server. Please try again.');
    }
  });
})();
