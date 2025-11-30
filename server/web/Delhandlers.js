// ============ EVENT HANDLERS & SCROLL MANAGEMENT ============

// Scroll state variables
let lastScrollY = 0;
let scrollTimeout = null;
let controlsVisible = true;
let videoScrollTimeout;

/**
 * Handle scroll events for UI controls and infinite loading
 */
function handleScroll() {
    const controls = document.getElementById('topControls');
    const currentScrollY = window.scrollY;
    
    clearTimeout(scrollTimeout);
    
    // Hide controls when scrolling down
    if (currentScrollY > lastScrollY && currentScrollY > 100) {
        controls.classList.add('hidden');
        controlsVisible = false;
    }
    
    lastScrollY = currentScrollY;
    
    // Show controls after scrolling stops
    scrollTimeout = setTimeout(() => {
        if (!controlsVisible) {
            controls.classList.remove('hidden');
            controlsVisible = true;
        }
    }, 1500);
    
    // Manage video playback based on visibility
    manageVideoPlayback();
    
    // Infinite loading when near bottom
    if ((window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 500) &&
        loadedMediaCount < allMediaFiles.length) {
        loadMoreMedia();
    }
}

// ============ EVENT LISTENER SETUP ============

/**
 * Set up all event listeners
 */
function setupEventListeners() {
    // Thumbnail size slider
    document.getElementById('thumbnailWidth').addEventListener('input', (e) => {
        const newWidth = parseInt(e.target.value);
        document.querySelectorAll('.grid-item').forEach(item => {
            item.style.width = `${newWidth}px`;
        });
        if (masonry) {
            masonry.options.columnWidth = newWidth;
            masonry.layout();
        }
    });

    // Fullscreen controls
    document.querySelector('.close-btn').addEventListener('click', closeFullscreen);
    document.getElementById('prevBtn').addEventListener('click', () => navigateFullscreen(-1));
    document.getElementById('nextBtn').addEventListener('click', () => navigateFullscreen(1));
    document.getElementById('playPauseBtn').addEventListener('click', () => {
        isPlaying ? stopAutoAdvance() : startAutoAdvance();
    });

    // Global keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        const overlay = document.getElementById('fullscreenOverlay');
        if (!overlay.classList.contains('visible')) return;
        
        if (e.key === 'ArrowRight' || e.key === 'd') navigateFullscreen(1);
        else if (e.key === 'ArrowLeft' || e.key === 'a') navigateFullscreen(-1);
        else if (e.key === 'Escape') closeFullscreen();
        else if (e.key === ' ') {
            e.preventDefault();
            isPlaying ? stopAutoAdvance() : startAutoAdvance();
        }
    });

    // Fullscreen mouse interactions
    document.getElementById('fullscreenOverlay').addEventListener('mousedown', (e) => {
        if (overlayTransitioning) return; // Ignore clicks during open animation
        
        // Middle click to close
        if (e.button === 1) {
            e.preventDefault();
            closeFullscreen();
            return;
        }
        // Ignore clicks on interactive elements
        if (e.target.closest('.close-btn, .playback-controls, .nav-btn, .bottom-right-root, .top-left-close, .fullscreen-folder-select, .vertical-progress-bar')) return;
        if (e.target.tagName === 'VIDEO') return;
        
        e.preventDefault();
        // Left click to advance
        if (e.button === 0 && currentMediaIndex < allMediaFiles.length - 1) {
            navigateFullscreen(1);
        }
    });

    // Right click to go back
    document.getElementById('fullscreenOverlay').addEventListener('contextmenu', (e) => {
        if (e.target.tagName === 'VIDEO') return;
        e.preventDefault();
        if (isPlaying) {
            stopAutoAdvance();
        } else {
            if (currentMediaIndex > 0) navigateFullscreen(-1, true);
        }
    });
    
    // Mouse wheel navigation
    document.getElementById('fullscreenOverlay').addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.deltaY > 0) navigateFullscreen(1, true);
        else if (e.deltaY < 0) navigateFullscreen(-1, true);
    });

    // Reset controls timer on mouse move
    document.getElementById('fullscreenOverlay').addEventListener('mousemove', resetControlsTimer);

    // Scroll event with debouncing
    window.addEventListener('scroll', () => {
        clearTimeout(videoScrollTimeout);
        videoScrollTimeout = setTimeout(handleScroll, 100);
    });

    // Show controls when mouse near top
    document.addEventListener('mousemove', (e) => {
        if (e.clientY < 100) {
            document.getElementById('topControls').classList.remove('hidden');
            controlsVisible = true;
        }
    });
}

// ============ INITIALIZATION ============

// Initialize when DOM is loaded
window.addEventListener('DOMContentLoaded', () => {
    initializeGallery();
    setupEventListeners();
});
