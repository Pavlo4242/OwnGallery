// ============ MEDIA RENDERING & DISPLAY FUNCTIONS ============

/**
 * Create appropriate media element (image or video) for a file
 * @param {string} fileName - Path to the media file
 * @returns {HTMLElement} Created media element
 */
function createMediaElement(fileName) {
    const mediaInfo = MEDIA_DATA[fileName];
    const isVideo = mediaInfo.isVideo;
    let mediaElement;

    if (isVideo) {
        mediaElement = document.createElement('video');
        mediaElement.autoplay = false;
        mediaElement.muted = true;
        mediaElement.loop = true;
        mediaElement.preload = 'metadata';
        mediaElement.src = mediaInfo.url;
    } else {
        mediaElement = document.createElement('img');
        mediaElement.loading = 'lazy';
        
        if (fileName.toLowerCase().endsWith('.webp')) {
            mediaElement.dataset.src = mediaInfo.url;
            mediaElement.classList.add('lazy-anim');
            if (animObserver) animObserver.observe(mediaElement);
        } else {
            mediaElement.src = mediaInfo.url;
        }
    }
    return mediaElement;
}

/**
 * Append media items to the gallery grid
 * @param {Array} files - Array of file paths to append
 */
function appendMediaToGrid(files) {
    const grid = document.querySelector('.grid');
    if (files.length === 0) {
        if (!masonry && grid.children.length > 0 && viewMode === 'grid') initializeMasonry();
        return;
    }
    
    const thumbnailWidth = document.getElementById('thumbnailWidth').value;

    const elements = files.map((fileName) => {
        const mediaInfo = MEDIA_DATA[fileName];
        const isFavorite = favoriteFiles.has(fileName);
        
        if (viewMode === 'list') {
            return createListItem(fileName, mediaInfo, isFavorite);
        } else {
            return createGridItem(fileName, mediaInfo, isFavorite, thumbnailWidth);
        }
    });

    grid.append(...elements);

    if (viewMode === 'grid') {
        if (masonry) {
            masonry.appended(elements);
            imagesLoaded(elements, () => {
                masonry.layout();
                setTimeout(manageVideoPlayback, 200);
            });
        } else {
            imagesLoaded(elements, () => {
                if(!masonry){ 
                    initializeMasonry();
                    setTimeout(() => masonry && masonry.layout(), 50);
                }
            });
        }
    }
    
    setTimeout(manageVideoPlayback, 500);
    updateFileCounter();
}

/**
 * Create list view item
 * @param {string} fileName - File path
 * @param {Object} mediaInfo - Media metadata
 * @param {boolean} isFavorite - Whether file is favorited
 * @returns {HTMLElement} List item element
 */
function createListItem(fileName, mediaInfo, isFavorite) {
    const listItem = document.createElement('div');
    listItem.className = 'list-item';
    listItem.onclick = () => openFullscreen(fileName);
    
    const thumbnail = createMediaElement(fileName);
    thumbnail.className = 'list-item-thumbnail';
    
    const checkbox = multiSelectMode ? `<input type="checkbox" class="grid-item-checkbox" onchange="toggleFileSelection('${fileName.replace(/'/g, "\\'")}', this)">` : '';
    
    listItem.innerHTML = `
        ${checkbox}
        <div class="list-item-info">
            <div class="list-item-name">${mediaInfo.name}</div>
            <div class="list-item-meta">${getFileExtension(mediaInfo.name)} • ${mediaInfo.isVideo ? 'Video' : 'Image'}</div>
        </div>
    `;
    
    const starBtn = document.createElement('div');
    starBtn.className = `favorite-star ${isFavorite ? 'is-favorite' : ''}`;
    starBtn.textContent = isFavorite ? '★' : '☆';
    starBtn.onclick = (e) => toggleFavorite(fileName, e);
    listItem.appendChild(starBtn);
    
    listItem.insertBefore(thumbnail, listItem.children[multiSelectMode ? 1 : 0]);
    return listItem;
}

/**
 * Create grid view item
 * @param {string} fileName - File path
 * @param {Object} mediaInfo - Media metadata
 * @param {boolean} isFavorite - Whether file is favorited
 * @param {number} thumbnailWidth - Width of thumbnail
 * @returns {HTMLElement} Grid item element
 */
function createGridItem(fileName, mediaInfo, isFavorite, thumbnailWidth) {
    const gridItem = document.createElement('div');
    gridItem.classList.add('grid-item');
    gridItem.style.width = `${thumbnailWidth}px`;
    
    if (selectedFiles.has(fileName)) gridItem.classList.add('selected');
    
    // Add checkbox for multi-select mode
    if (multiSelectMode) {
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'grid-item-checkbox';
        checkbox.checked = selectedFiles.has(fileName);
        checkbox.onclick = (e) => {
            e.stopPropagation();
            toggleFileSelection(fileName, e.target);
        };
        gridItem.appendChild(checkbox);
    }
    
    // Add favorite star
    const star = document.createElement('div');
    star.className = `favorite-star ${isFavorite ? 'is-favorite' : ''}`;
    star.textContent = isFavorite ? '★' : '☆';
    star.onclick = (e) => toggleFavorite(fileName, e);
    gridItem.appendChild(star);
    
    // Add media element
    const mediaEl = createMediaElement(fileName);
    gridItem.appendChild(mediaEl);
    
    // Add info overlay
    const infoDiv = document.createElement('div');
    infoDiv.className = 'item-info';
    infoDiv.innerHTML = `
        <div class="item-name" title="${mediaInfo.name}">${mediaInfo.name}</div>
        <div class="item-type">${getFileExtension(mediaInfo.name)} • ${mediaInfo.isVideo ? 'Video' : 'Image'}</div>
    `;
    gridItem.appendChild(infoDiv);
    
    // Add event listeners
    gridItem.addEventListener('click', (e) => {
        if (multiSelectMode) {
            const checkbox = gridItem.querySelector('.grid-item-checkbox');
            if (checkbox && e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                toggleFileSelection(fileName, checkbox);
            }
        } else {
            openFullscreen(fileName);
        }
    });
    
    gridItem.addEventListener('mouseenter', () => showQuickPreview(fileName));
    gridItem.addEventListener('mouseleave', hideQuickPreview);
    
    gridItem.addEventListener('mouseenter', () => {
        hoveredMedia = gridItem;
        manageVideoPlayback();
    });
    gridItem.addEventListener('mouseleave', () => {
        hoveredMedia = null;
        manageVideoPlayback();
    });

    return gridItem;
}

/**
 * Load more media files for infinite scrolling
 */
function loadMoreMedia() {
    const nextBatch = allMediaFiles.slice(loadedMediaCount, loadedMediaCount + filesPerLoad);
    if (nextBatch.length > 0) {
        appendMediaToGrid(nextBatch);
        loadedMediaCount += nextBatch.length;
    } else {
        const currentFolder = document.getElementById('folderFilter').value;
        if (currentFolder !== 'all' && !document.getElementById('nextFolderCard')) {
            addNextFolderCard(currentFolder);
        }
    }
}

/**
 * Add "Next Folder" navigation card
 * @param {string} currentFolder - Current folder path
 */
function addNextFolderCard(currentFolder) {
    const sortedFolders = Object.keys(FOLDER_MAP).filter(k => k !== 'all').sort();
    const currentIndex = sortedFolders.indexOf(currentFolder);
    
    if (currentIndex !== -1 && currentIndex < sortedFolders.length - 1) {
        const nextFolder = sortedFolders[currentIndex + 1];
        const grid = document.querySelector('.grid');
        const thumbnailWidth = document.getElementById('thumbnailWidth').value;
        
        const card = document.createElement('div');
        card.id = 'nextFolderCard';
        card.className = 'grid-item folder-card next-folder-card';
        card.style.width = `${thumbnailWidth}px`;
        card.innerHTML = `
            <div class="folder-icon">➡️</div>
            <div class="item-name">Next: ${nextFolder.split('/').pop()}</div>
        `;
        
        card.onclick = () => {
            document.getElementById('folderFilter').value = nextFolder;
            filterGalleryByFolder(true);
            scrollToTop();
        };
        
        grid.appendChild(card);
        if (masonry) masonry.appended([card]);
    }
}

/**
 * Initialize Masonry layout for grid view
 */
function initializeMasonry() {
    const grid = document.querySelector('.grid');
    if (masonry) masonry.destroy();
    
    masonry = new Masonry(grid, {
        itemSelector: '.grid-item',
        columnWidth: parseInt(document.getElementById('thumbnailWidth').value),
        gutter: 15,
        fitWidth: true
    });
}

/**
 * Get file extension from filename
 * @param {string} fileName - Filename
 * @returns {string} File extension in uppercase
 */
function getFileExtension(fileName) {
    const parts = fileName.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : 'FILE';
}
