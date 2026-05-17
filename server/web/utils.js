/*Restores: Delete Logic, Multi-select Toggle, Favorites, and Quick Preview.*/


app.utils = {
    // --- API Calls ---
    async fetchFiles() {
        const response = await fetch('/api/files?t=' + Date.now()); // Prevent caching
        return await response.json();
    },
    async fetchRootPath() {
        try {
            const res = await fetch('/api/root_dir');
            if (res.ok) document.getElementById('folderName').textContent = (await res.json()).root_dir;
        } catch (e) { }
    },
    quitServer() {
        if (!confirm('Stop media server?')) return;
        fetch('/api/quit', { method: 'POST' }).then(() => document.body.innerHTML = '<h1>Server Stopped</h1>');
    },
    openExplorer() {
        fetch('/api/open_explorer').catch(() => {});
    },

    getFileExtension(fileName) {
        const parts = fileName.split('.');
        return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : 'FILE';
    },

    // --- Update toggleQuickPreview logic in utils.js to manage DOM ---
    toggleQuickPreview: (isChecked) => {
        app.state.quickPreviewEnabled = isChecked;
        app.utils.saveSettings();
        if (!isChecked) app.utils.hideQuickPreview();
    },

    // --- Add Favorites Filtering (from DELui.js) ---
    filterFavorites: () => {
        const s = app.state;
        document.getElementById('folderFilter').value = 'all';

        // Filter the full map down to only files that are in the favorites Set
        s.allMediaFiles = Array.from(s.favoriteFiles).filter(f => s.MEDIA_DATA[f]);
        s.loadedMediaCount = 0;

        // Reset Grid
        const grid = document.querySelector('.grid');
        if (s.masonry) { s.masonry.destroy(); s.masonry = null; }
        grid.innerHTML = '';

        app.gallery.updateCounter();
        app.gallery.loadMore();
    },

    // --- Selection & Deletion ---
    toggleMultiSelect() {
        app.state.multiSelectMode = !app.state.multiSelectMode;
        const isOn = app.state.multiSelectMode;
        
        // Update button text and style
        const btn = document.getElementById('multiSelectToggle');
        if (btn) {
            btn.textContent = isOn ? '☑ Multi-Select ON' : '☑ Multi-Select';
            btn.style.background = isOn ? 'rgba(33,150,243,0.4)' : '';
            btn.style.borderColor = isOn ? 'rgba(33,150,243,0.6)' : '';
        }

        // Patch existing grid items: add or remove checkboxes WITHOUT re-rendering
        document.querySelectorAll('.grid-item:not(.folder-card)').forEach(item => {
            const fileName = item.dataset.fileName;
            if (!fileName) return;
            
            if (isOn) {
                // Add checkbox if not already there
                if (!item.querySelector('.grid-item-checkbox')) {
                    const cb = document.createElement('input');
                    cb.type = 'checkbox';
                    cb.className = 'grid-item-checkbox';
                    cb.checked = app.state.selectedFiles.has(fileName);
                    cb.onclick = (e) => { e.stopPropagation(); app.utils.toggleSelection(fileName, item, cb.checked); };
                    item.insertBefore(cb, item.firstChild);
                }
            } else {
                // Remove checkbox
                const cb = item.querySelector('.grid-item-checkbox');
                if (cb) cb.remove();
                if (!app.state.selectedFiles.has(fileName)) {
                    item.classList.remove('selected');
                }
            }
        });

        // We no longer clear app.state.selectedFiles when turning off multi-select
        this.updateDeleteBtn();
    },
    toggleSelection(fileName, itemDom, isChecked) {
        // Resolve fileName from DOM if not provided (keyboard shortcut path)
        if (!fileName && itemDom) fileName = itemDom.dataset.fileName;
        if (!fileName) return;

        if (isChecked) {
            app.state.selectedFiles.add(fileName);
            itemDom.classList.add('selected');
        } else {
            app.state.selectedFiles.delete(fileName);
            itemDom.classList.remove('selected');
        }
        this.updateDeleteBtn();
    },
    updateDeleteBtn() {
        const btn = document.getElementById('deleteBtn');
        const moveBtn = document.getElementById('moveBtn');
        const hasSelection = app.state.selectedFiles.size > 0;

        if (btn) btn.style.display = hasSelection ? 'inline-block' : 'none';
        if (moveBtn) moveBtn.style.display = hasSelection ? 'inline-block' : 'none';

        const count = document.getElementById('selectedCount');
        if (count) count.textContent = app.state.selectedFiles.size;

        const countMove = document.getElementById('selectedCountMove');
        if (countMove) countMove.textContent = app.state.selectedFiles.size;
    },
    // #8: Toast notification system
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    },

    async deleteSelected() {
        if (app.state.selectedFiles.size === 0) return;
        if (app.state.isDeleting) return; // Prevent popup spam if holding Delete key
        app.state.isDeleting = true;

        try {
            // Disabled delete confirmation for multi-select as requested
            // if (!confirm(`Delete ${app.state.selectedFiles.size} files?`)) return;

            const paths = Array.from(app.state.selectedFiles);

            // Windows File Lock Fix: Remove elements from DOM and clear src to release browser locks
            app.state.selectedFiles.forEach(fileName => {
                const el = document.querySelector(`.grid-item[data-file-name="${CSS.escape(fileName)}"]`);
                if (el) {
                    const media = el.querySelector('video, img');
                    if (media) {
                        media.pause && media.pause();
                        media.removeAttribute('src'); 
                        media.load && media.load(); // Force video lock release
                    }
                    el.remove();
                }
            });

            // Wait a moment for the browser to completely release file handles
            await new Promise(r => setTimeout(r, 200));

            const res = await fetch('/api/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paths })
            });

            const data = await res.json().catch(() => null);
            if (data) {
                const ok = (data.success || []).length;
                const fail = (data.failed || []).length;
                if (ok > 0) this.showToast(`Deleted ${ok} file(s)`, 'success');
                if (fail > 0) {
                    this.showToast(`${fail} file(s) failed to delete`, 'error');
                    console.error("Delete failures:", data.failed);
                }
            }

            app.state.selectedFiles.clear();
            app.main.init(); // Reload
        } finally {
            setTimeout(() => { app.state.isDeleting = false; }, 500);
        }
    },

    // --- Move & Folder Logic ---
    openMoveModal() {
        const modal = document.getElementById('moveModal');
        const select = document.getElementById('moveFolderSelect');
        const title = document.getElementById('modalTitle');

        title.textContent = `Move ${app.state.selectedFiles.size} files`;

        // Populate folders
        const folders = Object.keys(app.state.FOLDER_MAP).filter(f => f !== 'all').sort();
        select.innerHTML = '<option value="">Select destination...</option>' +
            folders.map(f => `<option value="${f}">${f}</option>`).join('');

        // Reset state
        document.getElementById('createNewFolderCheck').checked = false;
        this.toggleNewFolderInput();
        document.getElementById('newFolderName').value = '';

        modal.style.display = 'flex';
    },

    closeMoveModal() {
        document.getElementById('moveModal').style.display = 'none';
    },

    toggleNewFolderInput() {
        const isChecked = document.getElementById('createNewFolderCheck').checked;
        const input = document.getElementById('newFolderName');
        const select = document.getElementById('moveFolderSelect');

        if (isChecked) {
            input.style.display = 'block';
            select.disabled = true;
        } else {
            input.style.display = 'none';
            select.disabled = false;
        }
    },

    openNewFolderModal() {
        const modal = document.getElementById('moveModal');
        const title = document.getElementById('modalTitle');
        title.textContent = 'Create New Folder';

        document.getElementById('modalDescription').style.display = 'none';
        document.getElementById('moveFolderSelect').style.display = 'none';
        document.getElementById('createNewFolderCheck').parentElement.style.display = 'none';

        const input = document.getElementById('newFolderName');
        input.style.display = 'block';
        input.value = '';

        // Temporarily override submitMove logic to just create folder
        modal.dataset.mode = 'create_only';
        modal.style.display = 'flex';
    },

    async submitMove() {
        const modal = document.getElementById('moveModal');
        const isCreateOnly = modal.dataset.mode === 'create_only';
        let targetFolder = '';

        const isNewFolder = document.getElementById('createNewFolderCheck').checked || isCreateOnly;

        if (isNewFolder) {
            targetFolder = document.getElementById('newFolderName').value.trim();
            if (!targetFolder) {
                alert('Please enter a folder name.');
                return;
            }
            // Optional: call mkdir first (though move endpoint can auto-create if we update it, we updated move to MkdirAll)
        } else {
            targetFolder = document.getElementById('moveFolderSelect').value;
            if (!targetFolder) {
                alert('Please select a destination folder.');
                return;
            }
        }

        if (isCreateOnly) {
            const res = await fetch('/api/mkdir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: targetFolder })
            });
            if (res.ok) this.showToast(`Created folder: ${targetFolder}`, 'success');
            else this.showToast('Failed to create folder', 'error');
        } else {
            const paths = Array.from(app.state.selectedFiles);
            const res = await fetch('/api/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paths, target: targetFolder })
            });
            // #5: Parse detailed response
            const data = await res.json().catch(() => null);
            if (data) {
                const ok = (data.success || []).length;
                const fail = (data.failed || []).length;
                if (ok > 0) this.showToast(`Moved ${ok} file(s) to ${targetFolder}`, 'success');
                if (fail > 0) this.showToast(`${fail} file(s) failed to move`, 'error');
            }
            app.state.selectedFiles.clear();
        }

        // Reset modal state
        modal.dataset.mode = '';
        document.getElementById('modalDescription').style.display = 'block';
        document.getElementById('moveFolderSelect').style.display = 'block';
        document.getElementById('createNewFolderCheck').parentElement.style.display = 'block';
        this.closeMoveModal();
        app.main.init(); // Reload
    },

    // --- Settings & Favorites ---
    loadSettings() {
        const s = app.state;
        const saved = JSON.parse(localStorage.getItem('gallerySettings'));
        if (saved) {
            if (saved.thumbWidth) document.getElementById('thumbnailWidth').value = saved.thumbWidth;
            if (saved.speed) document.getElementById('advanceTime').value = saved.speed;
            if (saved.slideshowShuffle !== undefined) s.slideshowShuffle = saved.slideshowShuffle;
            if (saved.quickPreview !== undefined) s.quickPreviewEnabled = saved.quickPreview;
            if (saved.viewMode) s.viewMode = saved.viewMode;
            if (saved.sortBy) s.sortBy = saved.sortBy;
            const sortFilter = document.getElementById('sortFilter');
            if (sortFilter && saved.sortBy) sortFilter.value = saved.sortBy;
            // #10: Restore current folder
            if (saved.currentFolder) app.state._pendingFolder = saved.currentFolder;
        }
        const favs = localStorage.getItem('favoriteFiles');
        if (favs) s.favoriteFiles = new Set(JSON.parse(favs));
        this.updateShuffleUI();
    },
    saveSettings() {
        const settings = {
            thumbWidth: document.getElementById('thumbnailWidth').value,
            speed: document.getElementById('advanceTime').value,
            slideshowShuffle: app.state.slideshowShuffle,
            quickPreview: app.state.quickPreviewEnabled,
            viewMode: app.state.viewMode,
            sortBy: app.state.sortBy,
            currentFolder: document.getElementById('folderFilter').value // #10
        };
        localStorage.setItem('gallerySettings', JSON.stringify(settings));
        localStorage.setItem('favoriteFiles', JSON.stringify(Array.from(app.state.favoriteFiles)));
    },
    toggleFavorite(fileName, starElement) {
        if (app.state.favoriteFiles.has(fileName)) {
            app.state.favoriteFiles.delete(fileName);
            starElement.classList.remove('is-favorite');
            starElement.textContent = '☆';
        } else {
            app.state.favoriteFiles.add(fileName);
            starElement.classList.add('is-favorite');
            starElement.textContent = '★';
        }
        this.saveSettings();
    },

    // --- Preview & Helpers ---
    showQuickPreview(fileName) {
        if (!app.state.quickPreviewEnabled) return;
        clearTimeout(app.state.quickPreviewTimeout);
        app.state.quickPreviewTimeout = setTimeout(() => {
            const info = app.state.MEDIA_DATA[fileName];
            let overlay = document.getElementById('quickPreviewOverlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'quickPreviewOverlay';
                overlay.className = 'quick-preview-overlay';
                document.body.appendChild(overlay);
            }
            const media = info.isVideo ? `<video src="${info.url}" autoplay muted loop></video>` : `<img src="${info.url}">`;
            overlay.innerHTML = `${media}<div class="quick-preview-info">${info.name}</div>`;
            overlay.style.display = 'block';
        }, 300);
    },
    hideQuickPreview() {
        clearTimeout(app.state.quickPreviewTimeout);
        const ov = document.getElementById('quickPreviewOverlay');
        if (ov) ov.style.display = 'none';
    },
    toggleSlideshowShuffle() {
        app.state.slideshowShuffle = !app.state.slideshowShuffle;
        this.updateShuffleUI();
        this.saveSettings();
    },
    updateShuffleUI() {
        const btn = document.getElementById('toggleShuffleBtn');
        if (btn) btn.textContent = app.state.slideshowShuffle ? '🔀 Shuffle: ON' : '🔀 Shuffle: OFF';
    },
    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
    }
};
