
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
                app.state.MEDIA_DATA[f.path] = { name: f.name, isVideo: f.isVideo, url: webUrl, size: f.size, modified: f.modified };
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

        // The HTML is assumed to have a quickPreviewToggle checkbox
        const btnQuickPreview = document.getElementById('quickPreviewToggle');
        if (btnQuickPreview) btnQuickPreview.onchange = (e) => app.utils.toggleQuickPreview(e.target.checked);
        
        // The HTML is assumed to have a filterFavorites button
        const btnFavorites = document.getElementById('filterFavoritesBtn');
        if (btnFavorites) btnFavorites.onclick = () => app.utils.filterFavorites();

        
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

        // Fullscreen & Global Keyboard
        document.addEventListener('keydown', (e) => {
            const isFullscreen = document.getElementById('fullscreenOverlay').classList.contains('visible');
            const isModal = document.getElementById('moveModal').style.display === 'flex';
            
            if (isFullscreen) {
                if (e.key === 'ArrowRight') app.fullscreen.navigate(1);
                if (e.key === 'ArrowLeft') app.fullscreen.navigate(-1);
                if (e.key === 'Escape') app.fullscreen.close();
                if (e.key === ' ') { e.preventDefault(); app.fullscreen.toggleSlideshow(); }
                return;
            }

            if (isModal) {
                if (e.key === 'Escape') app.utils.closeMoveModal();
                if (e.key === 'Enter' && !e.target.tagName === 'TEXTAREA') app.utils.submitMove();
                return;
            }

            // Grid Navigation
            if (e.key === 'ArrowRight') { e.preventDefault(); app.gallery.moveFocus('right'); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); app.gallery.moveFocus('left'); }
            if (e.key === 'ArrowUp') { e.preventDefault(); app.gallery.moveFocus('up'); }
            if (e.key === 'ArrowDown') { e.preventDefault(); app.gallery.moveFocus('down'); }

            // Actions
            if (e.key === 'Enter') {
                const idx = app.state.focusedIndex;
                const items = document.querySelectorAll('.grid-item');
                if (idx !== -1 && items[idx]) items[idx].click();
            }
            if (e.key === ' ' && app.state.multiSelectMode) {
                e.preventDefault();
                const idx = app.state.focusedIndex;
                const items = document.querySelectorAll('.grid-item');
                if (idx !== -1 && items[idx]) {
                    const cb = items[idx].querySelector('input[type="checkbox"]');
                    if (cb) { cb.checked = !cb.checked; app.utils.toggleSelection(null, items[idx], cb.checked); }
                }
            }
            if (e.key === 'm' || e.key === 'M') app.utils.toggleMultiSelect();
            if (e.key === 'Delete') app.utils.deleteSelected();
            if (e.key === 's' || e.key === 'S') app.gallery.shuffle();
            if (e.key === 'f' || e.key === 'F') app.utils.filterFavorites();
            if (e.key === 'r' || e.key === 'R') app.main.init();
            
            // Numeric Sort Shortcuts (1-6)
            if (e.key >= '1' && e.key <= '6') {
                const sortSelect = document.getElementById('sortFilter');
                if (sortSelect) {
                    sortSelect.selectedIndex = parseInt(e.key) - 1;
                    app.gallery.handleSortChange();
                }
            }
        });
        
        document.getElementById('playPauseBtn').onclick = () => app.fullscreen.toggleSlideshow();
        document.getElementById('prevBtn').onclick = () => app.fullscreen.navigate(-1);
        document.getElementById('nextBtn').onclick = () => app.fullscreen.navigate(1);
    }
};

window.addEventListener('DOMContentLoaded', () => app.main.init());
