// ============ UI FEATURES & INTERACTIONS ============

// ============ VIEW MODE FUNCTIONS ============

/**
 * Set gallery view mode (grid or list)
 * @param {string} mode - View mode ('grid' or 'list')
 */
function setViewMode(mode) {
    viewMode = mode;
    document.getElementById('gridViewBtn').classList.toggle('active', mode === 'grid');
    document.getElementById('listViewBtn').classList.toggle('active', mode === 'list');
    saveSettings();
    refreshGalleryView();
}

/**
 * Refresh gallery view based on current view mode
 */
function refreshGalleryView() {
    const grid = document.querySelector('.grid');
    if (viewMode === 'list') {
        grid.classList.add('list-view');
        grid.classList.remove('masonry-grid');
        if (masonry) {
            masonry.destroy();
            masonry = null;
        }
    } else {
        grid.classList.remove('list-view');
        grid.classList.add('masonry-grid');
    }
    filterGalleryByFolder(false);
}

// ============ MULTI-SELECT FUNCTIONS ============

/**
 * Toggle multi-select mode on/off
 */
function toggleMultiSelect() {
    multiSelectMode = document.getElementById('multiSelectToggle').checked;
    const grid = document.querySelector('.grid');
    if (multiSelectMode) {
        grid.classList.add('multi-select-mode');
    } else {
        grid.classList.remove('multi-select-mode');
        selectedFiles.clear();
    }
    updateSelectedCount();
}

/**
 * Toggle file selection in multi-select mode
 * @param {string} fileName - File to toggle selection for
 * @param {HTMLElement} checkbox - Checkbox element
 */
function toggleFileSelection(fileName, checkbox) {
    const gridItem = checkbox.closest('.grid-item');
    if (checkbox.checked) {
        selectedFiles.add(fileName);
        if (gridItem) gridItem.classList.add('selected');
    } else {
        selectedFiles.delete(fileName);
        if (gridItem) gridItem.classList.remove('selected');
    }
    updateSelectedCount();
}

/**
 * Update selected files count display
 */
function updateSelectedCount() {
    const count = selectedFiles.size;
    document.getElementById('selectedCount').textContent = count;
    document.getElementById('deleteBtn').style.display = count > 0 ? 'inline-block' : 'none';
}

/**
 * Delete selected files after confirmation
 */
function deleteSelected() {
    if (selectedFiles.size === 0) return;
    const confirmed = confirm(`Are you sure you want to delete ${selectedFiles.size} file(s)?\n\nThis action cannot be undone!`);
    if (!confirmed) return;
    
    const deletePromises = Array.from(selectedFiles).map(fileName => {
        return fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: fileName })
        });
    });
    
    Promise.all(deletePromises)
        .then(() => {
            alert(`Deleted ${selectedFiles.size} file(s)`);
            selectedFiles.clear();
            initializeGallery();
        })
        .catch(err => {
            alert('Error deleting files: ' + err.message);
        });
}

// ============ FAVORITES FUNCTIONS ============

/**
 * Toggle favorite status for a file
 * @param {string} fileName - File to toggle favorite for
 * @param {Event} event - Click event
 */
function toggleFavorite(fileName, event) {
    event.stopPropagation();
    if (favoriteFiles.has(fileName)) {
        favoriteFiles.delete(fileName);
    } else {
        favoriteFiles.add(fileName);
    }
    saveFavorites();
    const star = event.currentTarget;
    star.classList.toggle('is-favorite');
    star.textContent = favoriteFiles.has(fileName) ? '★' : '☆';
}

/**
 * Filter gallery to show only favorites
 */
function filterFavorites() {
    const select = document.getElementById('folderFilter');
    select.value = 'all'; 
    
    allMediaFiles = Array.from(favoriteFiles).filter(f => MEDIA_DATA[f]);
    loadedMediaCount = 0;
    const grid = document.querySelector('.grid');
    if (masonry) {
        masonry.destroy();
        masonry = null;
    }
    grid.innerHTML = '';
    updateFileCounter();
    loadMoreMedia();
}

// ============ QUICK PREVIEW FUNCTIONS ============

/**
 * Show quick preview overlay on hover
 * @param {string} fileName - File to preview
 */
function showQuickPreview(fileName) {
    if (!quickPreviewEnabled) return;
    clearTimeout(quickPreviewTimeout);
    quickPreviewTimeout = setTimeout(() => {
        const mediaInfo = MEDIA_DATA[fileName];
        if (!mediaInfo) return;
        
        let overlay = document.getElementById('quickPreviewOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'quickPreviewOverlay';
            overlay.className = 'quick-preview-overlay';
            document.body.appendChild(overlay);
        }
        
        const mediaEl = mediaInfo.isVideo 
            ? `<video src="${mediaInfo.url}" autoplay muted loop style="max-width: 100%; max-height: 60vh;"></video>`
            : `<img src="${mediaInfo.url}" style="max-width: 100%; max-height: 60vh;">`;
        
        overlay.innerHTML = `
            ${mediaEl}
            <div class="quick-preview-info">
                <strong>${mediaInfo.name}</strong><br>
                <span style="color: #888;">${getFileExtension(mediaInfo.name)}</span>
            </div>
        `;
        overlay.style.display = 'block';
    }, 300);
}

/**
 * Hide quick preview overlay
 */
function hideQuickPreview() {
    clearTimeout(quickPreviewTimeout);
    const overlay = document.getElementById('quickPreviewOverlay');
    if (overlay) {
        overlay.style.display = 'none';
        overlay.innerHTML = '';
    }
}

// ============ VIDEO PLAYBACK MANAGEMENT ============

/**
 * Manage video playback based on visibility and hover state
 * Limits concurrent video playback to improve performance
 */
function manageVideoPlayback() {
    const viewportItems = Array.from(document.querySelectorAll('.grid-item'));
    const visibleItems = viewportItems.filter(item => {
        const rect = item.getBoundingClientRect();
        return rect.top < window.innerHeight && rect.bottom > 0;
    });

    const playables = visibleItems.map(item => {
        const video = item.querySelector('video');
        const webp = item.querySelector('img[src$=".webp"]');
        return { item, video, webp };
    }).filter(obj => obj.video || obj.webp);

    const activeSet = new Set();
    
    if (hoveredMedia) {
        const hoveredObj = playables.find(p => p.item === hoveredMedia);
        if (hoveredObj) activeSet.add(hoveredObj);
    }

    const others = playables.filter(p => !activeSet.has(p));
    for (let i = others.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [others[i], others[j]] = [others[j], others[i]];
    }

    for (const obj of others) {
        if (activeSet.size >= videoPlayLimit) break;
        activeSet.add(obj);
    }

    playables.forEach(obj => {
        const shouldPlay = activeSet.has(obj);
        
        if (obj.video) {
            if (shouldPlay) {
                if (obj.video.paused) obj.video.play().catch(() => {});
            } else {
                obj.video.pause();
            }
        }
        
        if (obj.webp) {
            const originalSrc = obj.webp.dataset.src || obj.webp.src;
            if (!obj.webp.dataset.src) obj.webp.dataset.src = originalSrc;

           if (shouldPlay && obj.webp) {
               if (!obj.webp.getAttribute('src')) obj.webp.src = originalSrc;
            } else {
                // Optional: clear src to stop animation/save memory
                // if (obj.webp) obj.webp.removeAttribute('src'); 
            }
        }
    });
}
