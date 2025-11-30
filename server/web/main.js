Restores: Wiring up the listeners for Delete, View Mode, and History buttons.*

```javascript
app.main = {
    async init() {
        const grid = document.querySelector('.grid');
        grid.innerHTML = '<div class="loading">Loading...</div>';
        
        app.utils.loadSettings();
        await app.utils.fetchRootPath();
        this.setupObservers();
        
        try {
            const data = await app.utils.fetchFiles();
            app.state.allDirectories = data.directories || [];
            app.state.FOLDER_MAP = { 'all': [] };
            app.state.allDirectories.forEach(dir => app.state.FOLDER_MAP[dir] = []);

            const files = data.files || [];
            files.sort((a, b) => a.path.localeCompare(b.path, undefined, {numeric: true}));
            
            files.forEach(f => {
                const webUrl = `/media/${f.path}`;
                app.state.MEDIA_DATA[f.path] = { name: f.name, isVideo: f.isVideo, url: webUrl };
                app.state.FOLDER_MAP['all'].push(f.path);
                const dir = f.path.split('/').slice(0, -1).join('/');
                if(app.state.FOLDER_MAP[dir]) app.state.FOLDER_MAP[dir].push(f.path);
            });

            app.gallery.populateDropdowns();
            app.gallery.filterByFolder(true);
        } catch (e) {
            grid.innerHTML = `<div class="loading">Error: ${e.message}</div>`;
        }
        
        this.setupEventListeners();
    },

    setupObservers() {
        app.state.animObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const img = entry.target;
                if (entry.isIntersecting && img.dataset.src) img.src = img.dataset.src;
            });
        }, { rootMargin: '200px' });
    },

    setupEventListeners() {
        let lastScrollY = 0;
        let videoScrollTimeout;

        // Scroll Handling
        window.addEventListener('scroll', () => {
            const currentY = window.scrollY;
            const controls = document.getElementById('topControls');
            if (currentY > lastScrollY && currentY > 100) controls.classList.add('hidden');
            else controls.classList.remove('hidden');
            lastScrollY = currentY;

            if ((window.innerHeight + currentY) >= document.body.offsetHeight - 500) {
                app.gallery.loadMore();
            }

            clearTimeout(videoScrollTimeout);
            videoScrollTimeout = setTimeout(() => app.media.managePlayback(), 100);
        });

        document.addEventListener('mousemove', (e) => {
            if (e.clientY < 100) document.getElementById('topControls').classList.remove('hidden');
        });

        // UI Inputs
        document.getElementById('thumbnailWidth').addEventListener('input', (e) => {
             document.querySelectorAll('.grid-item').forEach(el => el.style.width = `${e.target.value}px`);
             if(app.state.masonry) app.state.masonry.layout();
             app.utils.saveSettings();
        });

        // Button Listeners (if present in HTML)
        const btnDelete = document.getElementById('deleteBtn');
        if (btnDelete) btnDelete.onclick = () => app.utils.deleteSelected();

        const btnMulti = document.getElementById('multiSelectToggle');
        if (btnMulti) btnMulti.onclick = () => app.utils.toggleMultiSelect();

        const btnBack = document.getElementById('navBackBtn');
        if (btnBack) btnBack.onclick = () => app.gallery.navigateHistory(-1);

        const btnFwd = document.getElementById('navForwardBtn');
        if (btnFwd) btnFwd.onclick = () => app.gallery.navigateHistory(1);

        const btnGrid = document.getElementById('gridViewBtn');
        if (btnGrid) btnGrid.onclick = () => { app.state.viewMode = 'grid'; app.gallery.filterByFolder(false); app.utils.saveSettings(); };

        const btnList = document.getElementById('listViewBtn');
        if (btnList) btnList.onclick = () => { app.state.viewMode = 'list'; app.gallery.filterByFolder(false); app.utils.saveSettings(); };

        // Fullscreen Keyboard
        document.addEventListener('keydown', (e) => {
            if (!document.getElementById('fullscreenOverlay').classList.contains('visible')) return;
            if (e.key === 'ArrowRight') app.fullscreen.navigate(1);
            if (e.key === 'ArrowLeft') app.fullscreen.navigate(-1);
            if (e.key === 'Escape') app.fullscreen.close();
            if (e.key === ' ') { e.preventDefault(); app.fullscreen.toggleSlideshow(); }
        });
        
        document.getElementById('playPauseBtn').onclick = () => app.fullscreen.toggleSlideshow();
        document.getElementById('prevBtn').onclick = () => app.fullscreen.navigate(-1);
        document.getElementById('nextBtn').onclick = () => app.fullscreen.navigate(1);
    }
};

window.addEventListener('DOMContentLoaded', () => app.main.init());
