// ============ GLOBAL VARIABLES & CORE INITIALIZATION ============

// --- Application State ---
let currentMode = 'sorting';
let allMediaFiles = [];
let MEDIA_DATA = {};
let SCORE_DATA = {};
let FOLDER_MAP = {};
let allDirectories = [];
let masonry;
let loadedMediaCount = 0;
const filesPerLoad = 30;
let currentMediaIndex = -1;
let autoAdvanceInterval = null;
let isPlaying = false;
let viewedFiles = new Set();
let controlsHideTimer = null;
let currentRootPath = 'Loading...';
let globalVolume = 1.0;
let slideshowShuffle = false;
let viewMode = 'grid';
let multiSelectMode = false;
let selectedFiles = new Set();
let favoriteFiles = new Set();
let quickPreviewEnabled = false;
let quickPreviewTimeout = null;
let sequentialMode = true;
let videoPlayLimit = 5;
let animObserver = null;
let hoveredMedia = null;
let overlayTransitioning = false;

// --- Mode-Specific State ---
let comparisonPairs = [];
let comparisonResults = [];

// --- Navigation History ---
let navigationHistory = [];
let historyIndex = -1;

/**
 * Main initialization function - called when DOM is loaded
 * Sets up the gallery, loads settings, and fetches media data
 */
async function initializeGallery() {
    const grid = document.querySelector('.grid');
    grid.innerHTML = '<div class="loading">Loading media files</div>';
    
    loadSettings();
    initAnimObserver();
    
    // Reset navigation history
    navigationHistory = [];
    historyIndex = -1;
    updateNavigationButtons();

    await updateRootPathDisplay();
    
    // Set up view mode buttons
    document.getElementById('gridViewBtn')?.classList?.toggle('active', viewMode === 'grid');
    document.getElementById('listViewBtn')?.classList?.toggle('active', viewMode === 'list');
    
    try {
        const response = await fetch('/api/files');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const apiData = await response.json();
        const fileList = apiData.files || [];
        
        // Sort files alphabetically for deterministic order
        fileList.sort((a, b) => a.path.localeCompare(b.path, undefined, {numeric: true, sensitivity: 'base'}));

        allDirectories = apiData.directories || [];

        if (fileList.length === 0 && allDirectories.length === 0) {
            grid.innerHTML = '<div class="loading">No media files or folders found</div>';
            return;
        }
        
        // Initialize data structures
        FOLDER_MAP = { 'all': [] };
        MEDIA_DATA = {};
        
        // Build folder map and media data
        allDirectories.forEach(folderName => {
            if (!FOLDER_MAP[folderName]) FOLDER_MAP[folderName] = [];
        });
        
        fileList.forEach((fileInfo) => {
            const relativePath = fileInfo.path;
            const webUrl = '/media/' + relativePath.split('/').map(encodeURIComponent).join('/');
            
            MEDIA_DATA[relativePath] = {
                url: webUrl,
                name: fileInfo.name,
                isVideo: fileInfo.isVideo
            };
            FOLDER_MAP['all'].push(relativePath);
            
            // Organize by folder
            const parts = relativePath.split('/');
            if (parts.length > 1) {
                const folderName = parts.slice(0, -1).join('/');
                if (!FOLDER_MAP[folderName]) FOLDER_MAP[folderName] = [];
                FOLDER_MAP[folderName].push(relativePath);
            }
        });
        
        populateFolderFilter();
        populateFullscreenFolderSelect();
        filterGalleryByFolder(true);
        
    } catch (error) {
        console.error('Error:', error);
        grid.innerHTML = `<div class="loading">Error: ${error.message}</div>`;
    }
}

/**
 * Initialize Intersection Observer for lazy loading animations
 */
function initAnimObserver() {
    if (animObserver) return;
    
    animObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const img = entry.target;
            if (entry.isIntersecting) {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                }
            } else {
                if (img.src && img.dataset.src) {
                    img.style.height = img.offsetHeight + 'px'; 
                    img.src = ''; 
                }
            }
        });
    }, { rootMargin: '200px' });
}
