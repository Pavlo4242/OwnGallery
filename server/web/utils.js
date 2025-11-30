*API calls, LocalStorage, and helper functions.*
app.utils = {
    // --- API Calls ---
    async fetchFiles() {
        const response = await fetch('/api/files');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    },

    async fetchRootPath() {
        try {
            const res = await fetch('/api/root_dir');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('folderName').textContent = data.root_dir;
            }
        } catch (e) { console.error("Root path error", e); }
    },

    quitServer() {
        if (!confirm('Stop media server?')) return;
        fetch('/api/quit', { method: 'POST' })
            .then(() => document.body.innerHTML = '<h1 style="color:red;text-align:center">Server Stopped</h1>');
    },

    // --- Settings & Storage ---
    loadSettings() {
        const s = app.state;
        const saved = JSON.parse(localStorage.getItem('gallerySettings'));
        if (saved) {
            if (saved.thumbWidth) document.getElementById('thumbnailWidth').value = saved.thumbWidth;
            if (saved.speed) document.getElementById('advanceTime').value = saved.speed;
            if (saved.slideshowShuffle !== undefined) s.slideshowShuffle = saved.slideshowShuffle;
            if (saved.quickPreview !== undefined) s.quickPreviewEnabled = saved.quickPreview;
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
            quickPreview: app.state.quickPreviewEnabled
        };
        localStorage.setItem('gallerySettings', JSON.stringify(settings));
        localStorage.setItem('favoriteFiles', JSON.stringify(Array.from(app.state.favoriteFiles)));
    },

    // --- Favorites ---
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

    // --- Quick Preview ---
    toggleQuickPreview() {
        // Toggle logic if you have a UI button for it
        app.state.quickPreviewEnabled = !app.state.quickPreviewEnabled;
        this.saveSettings();
    },

    showQuickPreview(fileName) {
        if (!app.state.quickPreviewEnabled) return;
        
        clearTimeout(app.state.quickPreviewTimeout);
        app.state.quickPreviewTimeout = setTimeout(() => {
            const mediaInfo = app.state.MEDIA_DATA[fileName];
            if (!mediaInfo) return;
            
            let overlay = document.getElementById('quickPreviewOverlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'quickPreviewOverlay';
                overlay.className = 'quick-preview-overlay'; // Defined in style.css
                document.body.appendChild(overlay);
            }
            
            const mediaEl = mediaInfo.isVideo 
                ? `<video src="${mediaInfo.url}" autoplay muted loop style="max-width: 100%; max-height: 60vh;"></video>`
                : `<img src="${mediaInfo.url}" style="max-width: 100%; max-height: 60vh;">`;
            
            overlay.innerHTML = `
                ${mediaEl}
                <div class="quick-preview-info">
                    <strong>${mediaInfo.name}</strong><br>
                    <span style="color: #888;">${this.getFileExtension(mediaInfo.name)}</span>
                </div>
            `;
            overlay.style.display = 'block';
        }, 300);
    },

    hideQuickPreview() {
        clearTimeout(app.state.quickPreviewTimeout);
        const overlay = document.getElementById('quickPreviewOverlay');
        if (overlay) {
            overlay.style.display = 'none';
            overlay.innerHTML = '';
        }
    },

    // --- Helpers ---
    toggleSlideshowShuffle() {
        app.state.slideshowShuffle = !app.state.slideshowShuffle;
        this.updateShuffleUI();
        this.saveSettings();
    },

    updateShuffleUI() {
        const btn = document.getElementById('toggleShuffleBtn');
        if (btn) btn.textContent = app.state.slideshowShuffle ? '🔀 Shuffle: ON' : '🔀 Shuffle: OFF';
    },

    getFileExtension(fileName) {
        return fileName.split('.').pop().toUpperCase();
    },

    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
    }
};
