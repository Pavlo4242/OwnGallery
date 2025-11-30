*DOM creation and Grid management.*

```javascript
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
        } else {
            el = document.createElement('img');
            el.loading = 'lazy';
            if (fileName.toLowerCase().endsWith('.webp')) {
                el.dataset.src = info.url; // Setup for intersection observer
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
            const item = document.createElement('div');
            item.className = 'grid-item';
            item.style.width = `${width}px`;

            // Media
            item.appendChild(this.createElement(fileName));

            // Info Overlay
            const infoDiv = document.createElement('div');
            infoDiv.className = 'item-info';
            infoDiv.innerHTML = `<div class="item-name">${info.name}</div>`;
            item.appendChild(infoDiv);

            // Interaction
            item.onclick = () => app.fullscreen.open(fileName);
            item.onmouseenter = () => { app.state.hoveredMedia = item; app.media.managePlayback(); };
            item.onmouseleave = () => { app.state.hoveredMedia = null; app.media.managePlayback(); };

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

    // Intelligent Video Autoplay (Performance optimized)
    managePlayback() {
        const playables = Array.from(document.querySelectorAll('.grid-item video'));
        
        // Simple logic: Play hovered, pause others (or limit concurrents)
        playables.forEach(vid => {
            const isHovered = vid.closest('.grid-item') === app.state.hoveredMedia;
            if (isHovered) {
                vid.play().catch(() => {});
            } else {
                vid.pause();
            }
        });
    }
};
