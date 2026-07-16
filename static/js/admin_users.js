const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const _origFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            if (options.method && options.method !== 'GET') {
                options.headers = options.headers || {};
                if (options.headers instanceof Headers) {
                    options.headers.set('X-CSRFToken', csrfToken);
                } else {
                    options.headers['X-CSRFToken'] = csrfToken;
                }
            }
            return _origFetch.call(this, url, options);
        };

        let currentResetUser = null;

        // Add user form
        document.getElementById('add-user-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('new-username').value.trim();
            const password = document.getElementById('new-password').value;
            const role = document.getElementById('new-role').value;

            try {
                const response = await fetch('/api/admin/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password, role })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showMessage('User created successfully', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showMessage(data.error || 'Failed to create user', 'error');
                }
            } catch (err) {
                showMessage('Error creating user', 'error');
            }
        });

        async function deleteUser(username) {
            if (!confirm(`Are you sure you want to delete user "${username}"?`)) return;

            try {
                const response = await fetch(`/api/admin/users/${username}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showMessage('User deleted', 'success');
                    document.querySelector(`tr[data-username="${username}"]`).remove();
                } else {
                    showMessage(data.error || 'Failed to delete user', 'error');
                }
            } catch (err) {
                showMessage('Error deleting user', 'error');
            }
        }

        function showResetPassword(username) {
            currentResetUser = username;
            document.getElementById('reset-username').textContent = username;
            document.getElementById('reset-password').value = '';
            document.getElementById('reset-modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('reset-modal').classList.remove('active');
            currentResetUser = null;
        }

        async function resetPassword() {
            const password = document.getElementById('reset-password').value;
            
            if (password.length < 12) {
                showMessage('Password must be at least 12 characters', 'error');
                return;
            }

            try {
                const response = await fetch(`/api/admin/users/${currentResetUser}/password`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showMessage('Password reset successfully', 'success');
                    closeModal();
                } else {
                    showMessage(data.error || 'Failed to reset password', 'error');
                }
            } catch (err) {
                showMessage('Error resetting password', 'error');
            }
        }

        function showMessage(text, type) {
            const el = document.getElementById('message');
            el.textContent = text;
            el.className = 'message ' + type;
            el.style.display = 'block';
            
            setTimeout(() => {
                el.style.display = 'none';
            }, 4000);
        }

        // Close modal on overlay click
        document.getElementById('reset-modal').addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
