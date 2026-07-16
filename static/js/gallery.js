let images = [];
        let selectedImages = new Set();
        let currentFilter = 'all';
        let globalMatColor = '#2c2c2c';

        // Load global settings and images
        loadGlobalSettings();
        loadGallery();

        async function loadGlobalSettings() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                globalMatColor = settings.mat_color || '#2c2c2c';
            } catch (err) {
                console.error('Failed to load settings');
            }
        }

        async function loadGallery() {
            try {
                const response = await fetch('/api/gallery');
                const data = await response.json();
                images = data.images;
                renderGallery();
                updateStats();
            } catch (err) {
                showMessage('Failed to load gallery', 'error');
            }
        }

        function renderGallery() {
            const grid = document.getElementById('image-grid');
            const emptyState = document.getElementById('empty-state');
            
            // Filter images
            let filtered = images;
            if (currentFilter === 'enabled') {
                filtered = images.filter(img => img.enabled);
            } else if (currentFilter === 'disabled') {
                filtered = images.filter(img => !img.enabled);
            }

            if (images.length === 0) {
                grid.style.display = 'none';
                emptyState.style.display = 'block';
                return;
            }

            grid.style.display = 'grid';
            emptyState.style.display = 'none';

            grid.innerHTML = filtered.map(img => `
                <div class="image-card ${img.enabled ? '' : 'disabled'} ${selectedImages.has(img.filename) ? 'selected' : ''}"
                     data-filename="${img.filename}">
                    <div class="image-wrapper">
                        <input type="checkbox" class="image-checkbox"
                               ${selectedImages.has(img.filename) ? 'checked' : ''}
                               data-onchange="toggleSelect('${img.filename}')">
                        <span class="status-badge ${img.enabled ? 'status-enabled' : 'status-disabled'}">
                            ${img.enabled ? 'Visible' : 'Hidden'}
                        </span>
                        <img src="/uploads/${img.filename}" alt="${img.filename}" loading="lazy">
                    </div>
                    <div class="image-info">
                        <div class="image-filename" title="${img.filename}">${cleanFilename(img.filename)}</div>
                        <div class="image-meta">
                            <span>${formatSize(img.size)}</span>
                            <span>${img.uploaded_by || 'Unknown'}</span>
                        </div>
                        <div class="mat-color-row">
                            <label>Mat:</label>
                            <input type="color"
                                   class="mat-color-picker"
                                   value="${img.mat_color || globalMatColor}"
                                   data-filename="${img.filename}"
                                   data-onchange="updateMatColor('${img.filename}', this.value)">
                        </div>
                        <div class="image-actions">
                            <button class="btn ${img.enabled ? 'btn-warning' : 'btn-success'}"
                                    data-onclick="toggleImage('${img.filename}', ${!img.enabled})">
                                ${img.enabled ? '⊘ Hide' : '✓ Show'}
                            </button>
                            <button class="btn btn-danger" data-onclick="deleteImage('${img.filename}')">🗑</button>
                        </div>
                    </div>
                </div>
            `).join('');

            updateSelectionUI();
        }

        function cleanFilename(filename) {
            // Remove the UUID prefix
            return filename.replace(/^[a-f0-9]+_/, '');
        }

        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }

        function updateStats() {
            const total = images.length;
            const enabled = images.filter(img => img.enabled).length;
            const disabled = total - enabled;

            document.getElementById('total-count').textContent = total;
            document.getElementById('enabled-count').textContent = enabled;
            document.getElementById('disabled-count').textContent = disabled;
        }

        // Selection handling
        function toggleSelect(filename) {
            if (selectedImages.has(filename)) {
                selectedImages.delete(filename);
            } else {
                selectedImages.add(filename);
            }
            updateSelectionUI();
        }

        function updateSelectionUI() {
            document.getElementById('selected-count').textContent = selectedImages.size;
            
            const hasSelection = selectedImages.size > 0;
            document.getElementById('bulk-enable').disabled = !hasSelection;
            document.getElementById('bulk-disable').disabled = !hasSelection;
            document.getElementById('bulk-delete').disabled = !hasSelection;

            // Update select all checkbox
            const visibleImages = getVisibleImages();
            const allSelected = visibleImages.length > 0 && 
                               visibleImages.every(img => selectedImages.has(img.filename));
            document.getElementById('select-all').checked = allSelected;

            // Update card styles
            document.querySelectorAll('.image-card').forEach(card => {
                const filename = card.dataset.filename;
                card.classList.toggle('selected', selectedImages.has(filename));
                card.querySelector('.image-checkbox').checked = selectedImages.has(filename);
            });
        }

        function getVisibleImages() {
            if (currentFilter === 'enabled') return images.filter(img => img.enabled);
            if (currentFilter === 'disabled') return images.filter(img => !img.enabled);
            return images;
        }

        // Select all
        document.getElementById('select-all').addEventListener('change', (e) => {
            const visibleImages = getVisibleImages();
            if (e.target.checked) {
                visibleImages.forEach(img => selectedImages.add(img.filename));
            } else {
                visibleImages.forEach(img => selectedImages.delete(img.filename));
            }
            updateSelectionUI();
        });

        // Filter tabs
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentFilter = tab.dataset.filter;
                renderGallery();
            });
        });

        // Single image actions
        async function updateMatColor(filename, color) {
            try {
                const response = await fetch(`/api/gallery/${filename}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mat_color: color })
                });

                if (response.ok) {
                    const img = images.find(i => i.filename === filename);
                    if (img) img.mat_color = color;
                    showMessage('Mat color updated', 'success');
                }
            } catch (err) {
                showMessage('Failed to update mat color', 'error');
            }
        }

        async function toggleImage(filename, enabled) {
            try {
                const response = await fetch(`/api/gallery/${filename}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled })
                });
                
                if (response.ok) {
                    const img = images.find(i => i.filename === filename);
                    if (img) img.enabled = enabled;
                    renderGallery();
                    updateStats();
                    showMessage(enabled ? 'Image will now be shown' : 'Image hidden from display', 'success');
                }
            } catch (err) {
                showMessage('Failed to update image', 'error');
            }
        }

        async function deleteImage(filename) {
            if (!confirm('Delete this image permanently?')) return;

            try {
                const response = await fetch(`/api/gallery/${filename}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    images = images.filter(i => i.filename !== filename);
                    selectedImages.delete(filename);
                    renderGallery();
                    updateStats();
                    showMessage('Image deleted', 'success');
                }
            } catch (err) {
                showMessage('Failed to delete image', 'error');
            }
        }

        // Bulk actions
        document.getElementById('bulk-enable').addEventListener('click', async () => {
            await bulkAction('enable');
        });

        document.getElementById('bulk-disable').addEventListener('click', async () => {
            await bulkAction('disable');
        });

        document.getElementById('bulk-delete').addEventListener('click', async () => {
            if (!confirm(`Delete ${selectedImages.size} images permanently?`)) return;
            await bulkAction('delete');
        });

        async function bulkAction(action) {
            const filenames = Array.from(selectedImages);
            
            try {
                const response = await fetch('/api/gallery/bulk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, filenames })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showMessage(data.message, 'success');
                    
                    if (action === 'delete') {
                        images = images.filter(i => !filenames.includes(i.filename));
                    } else {
                        filenames.forEach(f => {
                            const img = images.find(i => i.filename === f);
                            if (img) img.enabled = (action === 'enable');
                        });
                    }
                    
                    selectedImages.clear();
                    renderGallery();
                    updateStats();
                } else {
                    showMessage(data.error || 'Action failed', 'error');
                }
            } catch (err) {
                showMessage('Action failed', 'error');
            }
        }

        function showMessage(text, type) {
            const el = document.getElementById('message');
            el.textContent = text;
            el.className = 'message ' + type;
            
            setTimeout(() => {
                el.className = 'message';
            }, 3000);
        }
