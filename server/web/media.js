*DOM creation and Grid management.*
app.media = {
    // Create Media Element (Video/Img)
    createElement(fileName) {
        const info = app.state.MEDIA_DATA[fileName];
        let el;
        
        if (info.isVideo) {
            el = document.createElement('video');
            el.muted = true;
            el.loop = true;
            el.src = info.url;
            el.preload = 'metadata'; 
        } else {
            el = document.createElement('img');
            el.loading = 'lazy';
            if (fileName.toLowerCase().endsWith('.webp')) {
                el.dataset.src = info.url;
                if (app.state.animObserver) app.state.animObserver.observe(el);
            } else {
                el.src = info.url;
            }
        }
        return el;
    },

    // Render Batch
    appendBatch(files) {
        const grid = document.querySelector('.grid');
        const width = document.getElementById('thumbnailWidth').value;
        const isListView = app.state.viewMode === 'list';

        // Toggle Grid/List Class
        if (isListView) {
            grid.classList.add('list-view');
            if(app.state.masonry) { app.state.masonry.destroy(); app.state.masonry = null; }
        } else {
            grid.classList.remove('list-view');
        }

        const elements = files.map(fileName => {
            const info = app.state.MEDIA_DATA[fileName];
            const isFavorite = app.state.favoriteFiles.has(fileName);
            const isSelected = app.state.selectedFiles.has(fileName);
            
            const item = document.createElement('div');
            item.className = isListView ? 'list-item' : 'grid-item';
            if (!isListView) item.style.width = `${width}px`;
            if (isSelected) item.classList.add('selected');

            // 1. Multi-Select Checkbox
            if (app.state.multiSelectMode) {
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.className = 'grid-item-checkbox';
                cb.checked = isSelected;
                cb.onclick = (e) => { e.stopPropagation(); app.utils.toggleSelection(fileName, item, cb.checked); };
                item.appendChild(cb);
            }

            // 2. Media Content
            const mediaWrap = isListView ? document.createElement('div') : item;
            if(isListView) mediaWrap.className = 'list-item-thumbnail';
            
            mediaWrap.appendChild(this.createElement(fileName));
            if(isListView) item.appendChild(mediaWrap);

            // 3. Favorite Star
            const star = document.createElement('div');
            star.className = `favorite-star ${isFavorite ? 'is-favorite' : ''}`;
            star.textContent = isFavorite ? '★' : '☆';
            star.onclick = (e) => { e.stopPropagation(); app.utils.toggleFavorite(fileName, star); };
            item.appendChild(star);

            // 4. Info/Metadata
            const infoDiv = document.createElement('div');
            infoDiv.className = isListView ? 'list-item-info' : 'item-info';
            infoDiv.innerHTML = `<div class="item-name">${info.name}</div>`;
            if(isListView) infoDiv.innerHTML += `<div class="list-item-meta">${app.utils.getFileExtension(info.name)} • ${info.isVideo ? 'Video' : 'Image'}</div>`;
            item.appendChild(infoDiv);

            // 5. Interaction
            item.onclick = (e) => {
                if (e.target.tagName === 'INPUT' || e.target.classList.contains('favorite-star')) return;
                
                if (app.state.multiSelectMode) {
                    const cb = item.querySelector('input[type="checkbox"]');
                    if (cb) { cb.checked = !cb.checked; app.utils.toggleSelection(fileName, item, cb.checked); }
                } else {
                    app.fullscreen.open(fileName);
                }
            };

            // 6. Hover Events
            if (!isListView) {
                item.onmouseenter = () => { 
                app.state.hoveredMedia = item; 
                app.media.managePlayback(); 
                if (app.state.quickPreviewEnabled) app.utils.showQuickPreview(fileName);
            };
                item.onmouseleave = () => { app.state.hoveredMedia = null; app.media.managePlayback(); app.utils.hideQuickPreview(); };
            }

            return item;
        });

        grid.append(...elements);

        // Masonry Layout (Grid Only)
        if (!isListView) {
            if (app.state.masonry) {
                app.state.masonry.appended(elements);
                imagesLoaded(elements, () => app.state.masonry.layout());
            } else {
                imagesLoaded(elements, () => this.initMasonry());
            }
        }
        
        app.gallery.updateCounter();
    },

    appendNextFolderCard(currentFolder) {
        // Logic to find next folder
        const folders = Object.keys(app.state.FOLDER_MAP).filter(k => k !== 'all').sort();
        const idx = folders.indexOf(currentFolder);
        if (idx === -1 || idx >= folders.length - 1) return;

        const nextFolder = folders[idx + 1];
        const width = document.getElementById('thumbnailWidth').value;
        const grid = document.querySelector('.grid');

        const card = document.createElement('div');
        card.className = 'grid-item folder-card next-folder-card';
        card.style.width = `${width}px`;
        card.innerHTML = `<div class="folder-icon">➡️</div><div>Next: ${nextFolder.split('/').pop()}</div>`;
        card.onclick = () => {
            document.getElementById('folderFilter').value = nextFolder;
            app.gallery.filterByFolder(true);
            window.scrollTo({top: 0, behavior: 'smooth'});
        };

        grid.appendChild(card);
        if (app.state.masonry) app.state.masonry.appended([card]);
    },

    initMasonry() {
        const grid = document.querySelector('.grid');
        if (app.state.masonry) app.state.masonry.destroy();
        app.state.masonry = new Masonry(grid, {
            itemSelector: '.grid-item',
            columnWidth: parseInt(document.getElementById('thumbnailWidth').value),
            gutter: 15,
            fitWidth: true
        });
    },

    managePlayback() {
        // ... (Same as previous step's managePlayback)
        const items = Array.from(document.querySelectorAll('.grid-item'));
        const visibleItems = items.filter(item => {
            const rect = item.getBoundingClientRect();
            return rect.top < window.innerHeight && rect.bottom > 0;
        });
        const activeSet = new Set();
        if (app.state.hoveredMedia) activeSet.add(app.state.hoveredMedia);
        for (const item of visibleItems) {
            if (activeSet.size >= app.state.videoPlayLimit) break;
            if (item.querySelector('video') || item.querySelector('img[data-src]')) activeSet.add(item);
        }
        items.forEach(item => {
            const vid = item.querySelector('video');
            const webp = item.querySelector('img[data-src]');
            const shouldPlay = activeSet.has(item);
            if (vid) shouldPlay && vid.paused ? vid.play().catch(()=>{}) : vid.pause();
            if (webp && shouldPlay && !webp.src) webp.src = webp.dataset.src;
        });
    }
};
