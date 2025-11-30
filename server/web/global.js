
```javascript
// Define the global application namespace
window.app = window.app || {};

// Global State
app.state = {
    // Data
    allMediaFiles: [],
    MEDIA_DATA: {},
    FOLDER_MAP: {},
    allDirectories: [],
    viewedFiles: new Set(),
    favoriteFiles: new Set(),
    selectedFiles: new Set(),
    
    // Comparison Mode
    comparisonPairs: [],
    comparisonResults: [],
    
    // UI/View State
    currentMode: 'sorting',
    viewMode: 'grid', // 'grid' or 'list'
    loadedMediaCount: 0,
    filesPerLoad: 30,
    historyIndex: -1,
    navigationHistory: [],
    
    // Playback/Interaction
    masonry: null,
    animObserver: null,
    hoveredMedia: null,
    videoPlayLimit: 5,
    overlayTransitioning: false,
    
    // Settings
    slideshowShuffle: false,
    quickPreviewEnabled: false,
    sequentialMode: true,
    
    // Fullscreen State
    currentMediaIndex: -1,
    isPlaying: false,
    autoAdvanceInterval: null,
    controlsHideTimer: null
};
