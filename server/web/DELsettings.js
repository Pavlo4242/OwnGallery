// ============ SETTINGS & UTILITY FUNCTIONS ============

// ============ SETTINGS MANAGEMENT ============

/**
 * Load favorites from localStorage
 */
function loadFavorites() {
    const saved = localStorage.getItem('favoriteFiles');
    if (saved) {
        favoriteFiles = new Set(JSON.parse(saved));
    }
}

/**
 * Save favorites to localStorage
 */
function saveFavorites() {
    localStorage.setItem('favoriteFiles', JSON.stringify(Array.from(favoriteFiles)));
}

/**
 * Save all settings to localStorage
 */
function saveSettings() {
    const settings = {
        thumbWidth: document.getElementById('thumbnailWidth').value,
        shuffle: document.getElementById('shuffleToggle')?.checked || false,
        speed: document.getElementById('advanceTime').value,
        slideshowShuffle: slideshowShuffle,
        quickPreview: document.getElementById('quickPreviewToggle')?.checked || false,
        viewMode: viewMode,
        sequentialMode: sequentialMode
    };
    localStorage.setItem('gallerySettings', JSON.stringify(settings));
}

/**
 * Load settings from localStorage
 */
function loadSettings() {
    const saved = JSON.parse(localStorage.getItem('gallerySettings'));
    if (saved) {
        if (saved.thumbWidth) document.getElementById('thumbnailWidth').value = saved.thumbWidth;
        if (saved.shuffle && document.getElementById('shuffleToggle')) {
            document.getElementById('shuffleToggle').checked = saved.shuffle;
        }
        if (saved.speed) document.getElementById('advanceTime').value = saved.speed;
        if (saved.slideshowShuffle !== undefined) {
            slideshowShuffle = saved.slideshowShuffle;
            updateShuffleButtonText();
        }
        if (saved.quickPreview !== undefined && document.getElementById('quickPreviewToggle')) {
            quickPreviewEnabled = saved.quickPreview;
            document.getElementById('quickPreviewToggle').checked = saved.quickPreview;
        }
        if (saved.viewMode) {
            viewMode = saved.viewMode;
        }
        if (saved.sequentialMode !== undefined) {
            sequentialMode = saved.sequentialMode;
        }
    }
    loadFavorites();
}

// ============ UTILITY FUNCTIONS ============

/**
 * Update sequential mode UI display
 */
function updateSequentialModeUI() {
    const btn = document.getElementById('sequentialModeBtn');
    const modeText = document.getElementById('modeText');
    if (btn && modeText) {
        modeText.textContent = sequentialMode ? 'Sequential' : 'Random';
        if (sequentialMode) {
            btn.classList.remove('active');
        } else {
            btn.classList.add('active');
        }
    }
}

/**
 * Toggle sequential/random mode in slideshow
 */
function toggleSequentialMode() {
    sequentialMode = !sequentialMode;
    document.getElementById('modeText').textContent = sequentialMode ? 'Sequential' : 'Random';
    document.getElementById('sequentialModeBtn').classList.toggle('active');
    saveSettings();
}

/**
 * Toggle shuffle in slideshow
 */
function toggleShuffleInSlideshow() {
    slideshowShuffle = !slideshowShuffle;
    updateShuffleButtonText();
    saveSettings();
}

/**
 * Update shuffle button text based on current state
 */
function updateShuffleButtonText() {
    const btn = document.getElementById('toggleShuffleBtn');
    if (btn) {
        btn.textContent = slideshowShuffle ? '🔀 Shuffle: ON' : '🔀 Shuffle: OFF';
        btn.classList.toggle('active', slideshowShuffle);
    }
}

/**
 * Toggle quick preview feature
 */
function toggleQuickPreview() {
    quickPreviewEnabled = document.getElementById('quickPreviewToggle').checked;
    saveSettings();
    if (!quickPreviewEnabled) hideQuickPreview();
}

/**
 * Update thumbnail size and refresh layout
 */
function updateThumbnailSize() {
    const newWidth = parseInt(document.getElementById('thumbnailWidth').value);
    document.querySelectorAll('.grid-item').forEach(item => {
        item.style.width = `${newWidth}px`;
    });
    if (masonry) {
        masonry.options.columnWidth = newWidth;
        masonry.layout();
    }
    saveSettings();
}

/**
 * Update file counter display
 */
function updateFileCounter() {
    const total = allMediaFiles.length;
    const loaded = Math.min(loadedMediaCount, total);
    document.getElementById('fileCounter').textContent = `${total} files`;
    document.getElementById('loadedCount').textContent = loaded;
    document.getElementById('totalCount').textContent = total;
}

/**
 * Force reshuffle of current gallery
 */
function forceReshuffle() {
    filterGalleryByFolder(false);
}

/**
 * Reset viewed files tracking
 */
function resetViewed() {
    viewedFiles.clear();
    filterGalleryByFolder(false);
    populateFolderFilter();
}

// ============ API COMMUNICATION ============

/**
 * Update root path display from server
 */
async function updateRootPathDisplay() {
    try {
        const response = await fetch('/api/root_dir');
        if (response.ok) {
            const data = await response.json();
            currentRootPath = data.root_dir;
            document.getElementById('folderName').textContent = currentRootPath;
            document.getElementById('currentFolder').title = 'Current Root: ' + currentRootPath;
        } else {
            document.getElementById('folderName').textContent = 'Root Path Error';
        }
    } catch (e) {
        console.error("Failed to fetch root directory:", e);
        document.getElementById('folderName').textContent = 'API Error';
    }
}

/**
 * Open file explorer at current directory
 */
async function openExplorer() {
    try {
        const response = await fetch('/api/open_explorer');
        if (!response.ok) alert('Failed to open folder.');
    } catch (e) {
        alert('Connection error.');
    }
}

/**
 * Open explorer and show path (combined function)
 */
function openExplorerAndShowPath() {
    openExplorer();
}

/**
 * Quit the media server
 */
function quitServer() {
    if (!confirm('Stop the media server? You will need to restart it manually.')) return;
    fetch('/api/quit', { method: 'POST' })
        .then(() => {
            document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;color:#f44336;background:#0a0a0a;font-family:sans-serif;"><h1>Server Stopped</h1></div>';
        })
        .catch(e => alert('Error stopping server'));
}
