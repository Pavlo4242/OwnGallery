// ============ GALLERY NAVIGATION & FILTERING ============

/**
 * Filter gallery contents by folder selection
 * @param {boolean} recordHistory - Whether to record this navigation in history
 */
function filterGalleryByFolder(recordHistory = true) {
    const select = document.getElementById('folderFilter');
    const folderName = select.value;
    const grid = document.querySelector('.grid');
    const shuffleEnabled = document.getElementById('shuffleToggle')?.checked || false;
    const thumbnailWidth = document.getElementById('thumbnailWidth').value;
    
    const galleryDir = document.getElementById('galleryDir');
    galleryDir.textContent = folderName === 'all' ? 'Root' : folderName;
    
    if (recordHistory) {
        if (historyIndex === -1 || navigationHistory[historyIndex] !== folderName) {
            navigationHistory = navigationHistory.slice(0, historyIndex + 1);
            navigationHistory.push(folderName);
            historyIndex++;
        }
    }
    updateNavigationButtons();

    if (masonry) {
        masonry.destroy();
        masonry = null;
    }

    grid.innerHTML = '';
    
    const currentPrefix = folderName === 'all' ? '' : folderName + '/';
    const subfolders = allDirectories.filter(dir => {
        if (folderName === 'all') return !dir.includes('/'); 
        return dir.startsWith(currentPrefix) && 
               dir.slice(currentPrefix.length).indexOf('/') === -1 &&
               dir !== folderName;
    });

    // Add folder cards for subdirectories
    if (subfolders.length > 0) {
        const folderElements = subfolders.map(subDir => {
            const card = document.createElement('div');
            card.className = 'grid-item folder-card';
            card.style.width = `${thumbnailWidth}px`;
            
            const displayName = subDir.split('/').pop();
            card.innerHTML = `
                <div class="folder-icon">📁</div>
                <div class="item-name">${displayName}</div>
            `;
            card.onclick = () => {
                select.value = subDir;
                filterGalleryByFolder(true);
            };
            return card;
        });
        grid.append(...folderElements);
    }

    let displayList;
    if (folderName === 'all') {
        displayList = [...FOLDER_MAP['all']];
    } else {
        displayList = FOLDER_MAP['all'].filter(f => f.startsWith(folderName + '/'));
    }
    
    if (shuffleEnabled) {
        shuffleArray(displayList);
    }
    
    allMediaFiles = displayList;
    loadedMediaCount = 0;
    updateFileCounter();
    loadMoreMedia();
    saveSettings();
}

/**
 * Shuffle array with unviewed files prioritized
 * @param {Array} array - Array to shuffle
 */
function shuffleArray(array) {
    const unviewed = array.filter(file => !viewedFiles.has(file));
    const viewed = array.filter(file => viewedFiles.has(file));
    
    // Shuffle unviewed files
    for (let i = unviewed.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [unviewed[i], unviewed[j]] = [unviewed[j], unviewed[i]];
    }
    
    // Shuffle viewed files
    for (let i = viewed.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [viewed[i], viewed[j]] = [viewed[j], viewed[i]];
    }
    
    // Combine with unviewed first
    array.length = 0;
    array.push(...unviewed, ...viewed);
}

/**
 * Populate the folder filter dropdown
 */
function populateFolderFilter() {
    const select = document.getElementById('folderFilter');
    const currentVal = select.value;
    
    select.innerHTML = '<option value="all">All Files</option>';
    
    Object.keys(FOLDER_MAP).sort().forEach(folderName => {
        if (folderName === 'all') return;
        const option = document.createElement('option');
        option.value = folderName;
        const depth = (folderName.match(/\//g) || []).length;
        
        const filesInFolder = FOLDER_MAP[folderName];
        const viewedCount = filesInFolder.filter(f => viewedFiles.has(f)).length;
        
        option.textContent = '  '.repeat(depth) + folderName + ` (${viewedCount}/${filesInFolder.length} viewed)`;
        select.appendChild(option);
    });
    
    if (currentVal && FOLDER_MAP[currentVal]) {
        select.value = currentVal;
    }
}

/**
 * Populate the fullscreen folder selection dropdown
 */
function populateFullscreenFolderSelect() {
    const select = document.getElementById('fullscreenFolderSelect');
    select.innerHTML = '<option value="">Jump to Folder...</option>';
    
    Object.keys(FOLDER_MAP).sort().forEach(folderName => {
        if (folderName === 'all') return;
        const option = document.createElement('option');
        option.value = folderName;
        const depth = (folderName.match(/\//g) || []).length;
        option.textContent = '  '.repeat(depth) + folderName;
        select.appendChild(option);
    });
}

// ============ NAVIGATION FUNCTIONS ============

/**
 * Navigate to parent folder
 */
function navigateUp() {
    const current = document.getElementById('folderFilter').value;
    if (current === 'all') return;
    
    const parts = current.split('/');
    parts.pop();
    const parent = parts.length === 0 ? 'all' : parts.join('/');
    
    document.getElementById('folderFilter').value = parent;
    filterGalleryByFolder(true);
}

/**
 * Navigate back in history
 */
function navigateBack() {
    if (historyIndex > 0) {
        historyIndex--;
        const folder = navigationHistory[historyIndex];
        document.getElementById('folderFilter').value = folder;
        filterGalleryByFolder(false);
    }
}

/**
 * Navigate forward in history
 */
function navigateForward() {
    if (historyIndex < navigationHistory.length - 1) {
        historyIndex++;
        const folder = navigationHistory[historyIndex];
        document.getElementById('folderFilter').value = folder;
        filterGalleryByFolder(false);
    }
}

/**
 * Navigate to root folder
 */
function navigateRoot() {
    document.getElementById('folderFilter').value = 'all';
    filterGalleryByFolder(true);
}

/**
 * Jump to folder from fullscreen mode
 * @param {string} folderName - Folder to jump to
 */
function jumpToFolderFromFullscreen(folderName) {
    if (!folderName) return;
    document.getElementById('folderFilter').value = folderName;
    closeFullscreen();
    filterGalleryByFolder(true);
    scrollToTop();
}

/**
 * Update navigation button states based on history
 */
function updateNavigationButtons() {
    document.getElementById('navBackBtn').disabled = historyIndex <= 0;
    document.getElementById('navForwardBtn').disabled = historyIndex >= navigationHistory.length - 1;
}

/**
 * Scroll to top of page and close fullscreen if open
 */
function scrollToTop() {
    const overlay = document.getElementById('fullscreenOverlay');
    if (overlay.classList.contains('visible')) closeFullscreen();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Scroll by specified amount
 * @param {number} amount - Pixels to scroll
 */
function scrollByAmount(amount) {
    window.scrollBy({ top: amount, behavior: 'smooth' });
}

/**
 * Return to root folder from fullscreen mode
 */
function returnToRootFromFullscreen() {
    closeFullscreen();
    navigateRoot();
}
