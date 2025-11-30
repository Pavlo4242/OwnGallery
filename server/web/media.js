*DOM creation and Grid management.*

app.media = {
    // Create Image or Video element
    createElement(fileName) {
        const info = app.state.MEDIA_DATA[fileName];
        let el;
        
        if (info.isVideo) {
            el = document.createElement('video');
            el.muted = true;
            el.loop = true;
            el.src = info.url;
            el.preload = 'metadata'; // Performance optimization
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

    // Render items to grid
    appendBatch(files) {
        const grid = document.querySelector('.grid');
        const width = document.getElementById('thumbnailWidth').value;

        if (files.length === 0) {
            if (!app.state.masonry && grid.children.length > 0) this.initMasonry();
            return;
        }

        const elements = files.map(fileName => {
            const info = app.state.MEDIA_DATA[fileName];
            const isFavorite = app.state.favoriteFiles.has(fileName);
            
            const item = document.createElement('div');
            item.className = 'grid-item';
            item.style.width = `${width}px`;

            // Media
            item.appendChild(this.createElement(fileName));

            // Favorite Star
            const star = document.createElement('div');
            star.className = `favorite-star ${isFavorite ? 'is-favorite' : ''}`;
            star.textContent = isFavorite ? '★' : '☆';
            star.onclick = (e) => {
                e.stopPropagation();
                app.utils.toggleFavorite(fileName, star);
            };
            item.appendChild(star);

            // Info Overlay
            const infoDiv = document.createElement('div');
            infoDiv.className = 'item-info';
            infoDiv.innerHTML = `<div class="item-name">${info.name}</div>`;
            item.appendChild(infoDiv);

            // Interaction
            item.onclick = (e) => {
                // Ignore clicks on star
                if(e.target.classList.contains('favorite-star')) return;
                app.fullscreen.open(fileName);
            };

            // Hover Events (Playback & Quick Preview)
            item.onmouseenter = () => { 
                app.state.hoveredMedia = item; 
                app.media.managePlayback();
                app.utils.showQuickPreview(fileName);
            };
            item.onmouseleave = () => { 
                app.state.hoveredMedia = null; 
                app.media.managePlayback();
                app.utils.hideQuickPreview();
            };

            return item;
        });

        grid.append(...elements);

        if (app.state.masonry) {
            app.state.masonry.appended(elements);
            imagesLoaded(elements, () => app.state.masonry.layout());
        } else {
            imagesLoaded(elements, () => this.initMasonry());
        }
        
        app.gallery.updateCounter();
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

    // Intelligent Video Autoplay
    managePlayback() {
        // 1. Get all videos currently in the viewport
        const items = Array.from(document.querySelectorAll('.grid-item'));
        const visibleItems = items.filter(item => {
            const rect = item.getBoundingClientRect();
            return rect.top < window.innerHeight && rect.bottom > 0;
        });

        const activeSet = new Set();
        
        // Always play the hovered item
        if (app.state.hoveredMedia) activeSet.add(app.state.hoveredMedia);

        // Fill remaining slots with visible videos up to limit
        for (const item of visibleItems) {
            if (activeSet.size >= app.state.videoPlayLimit) break;
            if (item.querySelector('video') || item.querySelector('img[data-src]')) {
                activeSet.add(item);
            }
        }

        // Apply Play/Pause
        items.forEach(item => {
            const vid = item.querySelector('video');
            const webp = item.querySelector('img[data-src]');
            const shouldPlay = activeSet.has(item);

            if (vid) {
                if (shouldPlay) { if(vid.paused) vid.play().catch(()=>{}); }
                else { vid.pause(); }
            }
            if (webp) {
                 if (shouldPlay && !webp.src) webp.src = webp.dataset.src;
                 // Optional: Clear src when offscreen to save memory, depends on browser cache
            }
        });
    }
};
