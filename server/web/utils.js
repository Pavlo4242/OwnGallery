*API calls, LocalStorage, and helper functions.*

```javascript
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
        }
        
        const favs = localStorage.getItem('favoriteFiles');
        if (favs) s.favoriteFiles = new Set(JSON.parse(favs));
        
        this.updateShuffleUI();
    },

    saveSettings() {
        const settings = {
            thumbWidth: document.getElementById('thumbnailWidth').value,
            speed: document.getElementById('advanceTime').value,
            slideshowShuffle: app.state.slideshowShuffle
        };
        localStorage.setItem('gallerySettings', JSON.stringify(settings));
        localStorage.setItem('favoriteFiles', JSON.stringify(Array.from(app.state.favoriteFiles)));
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
