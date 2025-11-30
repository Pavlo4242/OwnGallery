// ============ MODE MANAGEMENT ============

/**
 * Switch between the three main modes: Sorting, Comparing, Browsing
 * @param {string} mode - The mode to switch to
 */
function setMode(mode) {
    currentMode = mode;
    
    // Update mode buttons visual state
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.mode-${mode}`).classList.add('active');
    
    // Show/hide content areas
    document.querySelectorAll('.content-area').forEach(area => area.style.display = 'none');
    document.getElementById(`${mode}Content`).style.display = 'block';
    
    // Show/hide controls
    document.querySelectorAll('.controls-group').forEach(group => group.style.display = 'none');
    document.querySelectorAll(`.${mode}-controls`).forEach(group => group.style.display = 'flex');
    
    // Initialize mode-specific features
    switch(mode) {
        case 'sorting':
            initializeSortingMode();
            break;
        case 'comparing':
            initializeComparingMode();
            break;
        case 'browsing':
            initializeBrowsingMode();
            break;
    }
}

/**
 * Initialize Sorting Mode - the default gallery view
 */
function initializeSortingMode() {
    if (allMediaFiles.length === 0) {
        initializeGallery();
    }
}

/**
 * Initialize Comparing Mode - for side-by-side image comparison
 */
function initializeComparingMode() {
    generateComparisonPairs();
    loadNewComparisonPair();
}

/**
 * Initialize Browsing Mode - for casual gallery viewing without AI filtering
 */
function initializeBrowsingMode() {
    displayBrowsingGallery();
}

// ============ COMPARING MODE FUNCTIONS ============

/**
 * Generate pairs of similar images for comparison based on CLIP clustering
 */
function generateComparisonPairs() {
    comparisonPairs = [];
    
    // Group images by similarity (using CLIP cluster data if available)
    const similarityGroups = {};
    
    allMediaFiles.forEach(path => {
        const media = MEDIA_DATA[path];
        const scores = SCORE_DATA[media.name]; // Use name as key based on existing structure
        const clusterId = scores?.cluster_id || 'unknown';
        
        if (!similarityGroups[clusterId]) {
            similarityGroups[clusterId] = [];
        }
        similarityGroups[clusterId].push(path);
    });
    
    // Create pairs from groups with 2+ similar images
    Object.values(similarityGroups).forEach(group => {
        if (group.length >= 2) {
            // Shuffle and create pairs
            const shuffled = [...group].sort(() => Math.random() - 0.5);
            for (let i = 0; i < shuffled.length - 1; i += 2) {
                comparisonPairs.push([shuffled[i], shuffled[i + 1]]);
            }
        }
    });
    
    console.log(`Generated ${comparisonPairs.length} comparison pairs`);
}

/**
 * Load a new pair of images for comparison
 */
function loadNewComparisonPair() {
    if (comparisonPairs.length === 0) {
        document.getElementById('comparisonPair').innerHTML = '<div style="color:#666; text-align:center; padding:50px;">No more comparison pairs available</div>';
        return;
    }
    
    const pair = comparisonPairs.pop();
    const [path1, path2] = pair;
    
    const html = `
        <div class="compare-item" onclick="selectForKeep('${path1}')" data-path="${path1}">
            ${createMediaElement(path1).outerHTML}
            <div class="compare-info">${MEDIA_DATA[path1].name}</div>
        </div>
        <div style="color:#666; align-self:center;">VS</div>
        <div class="compare-item" onclick="selectForKeep('${path2}')" data-path="${path2}">
            ${createMediaElement(path2).outerHTML}
            <div class="compare-info">${MEDIA_DATA[path2].name}</div>
        </div>
    `;
    
    document.getElementById('comparisonPair').innerHTML = html;
    updateComparisonStats();
}

/**
 * Mark the selected image as "keep" and the other as "discard"
 * @param {string} selectedPath - Path of the selected image
 */
function selectForKeep(selectedPath) {
    const pairContainer = document.getElementById('comparisonPair');
    const items = pairContainer.querySelectorAll('.compare-item');
    
    items.forEach(item => {
        item.classList.remove('selected');
        if (item.dataset.path === selectedPath) {
            item.classList.add('selected');
            // Store decision
            comparisonResults.push({
                keep: selectedPath,
                discard: items.find(i => i.dataset.path !== selectedPath)?.dataset.path,
                timestamp: new Date().toISOString()
            });
        }
    });
    
    // Auto-advance after short delay
    setTimeout(() => {
        if (comparisonPairs.length > 0) {
            loadNewComparisonPair();
        }
    }, 1000);
}

/**
 * Mark both images in the current pair for keeping
 */
function markBothForKeep() {
    const pairContainer = document.getElementById('comparisonPair');
    const items = pairContainer.querySelectorAll('.compare-item');
    const paths = Array.from(items).map(item => item.dataset.path);
    
    comparisonResults.push({
        keep: paths.join(','),
        discard: null,
        timestamp: new Date().toISOString()
    });
    
    if (comparisonPairs.length > 0) {
        loadNewComparisonPair();
    }
}

/**
 * Mark both images in the current pair for discarding
 */
function markBothForDiscard() {
    const pairContainer = document.getElementById('comparisonPair');
    const items = pairContainer.querySelectorAll('.compare-item');
    const paths = Array.from(items).map(item => item.dataset.path);
    
    comparisonResults.push({
        keep: null,
        discard: paths.join(','),
        timestamp: new Date().toISOString()
    });
    
    if (comparisonPairs.length > 0) {
        loadNewComparisonPair();
    }
}

/**
 * Update comparison statistics display
 */
function updateComparisonStats() {
    document.getElementById('comparisonCount').textContent = comparisonResults.length;
    document.getElementById('decisionCount').textContent = comparisonPairs.length;
}

// ============ BROWSING MODE FUNCTIONS ============

/**
 * Display all images in browsing mode without AI filtering
 */
function displayBrowsingGallery() {
    const grid = document.getElementById('browsingGrid');
    grid.innerHTML = '';
    
    // Show all images without AI filtering
    const elements = allMediaFiles.map(path => {
        const item = document.createElement('div');
        item.className = 'grid-item';
        item.style.width = document.getElementById('thumbnailWidth').value + 'px';
        item.appendChild(createMediaElement(path));
        item.onclick = () => openFullscreen(path);
        return item;
    });
    grid.append(...elements);
    
    // Initialize Masonry for browsing grid if needed
    new Masonry(grid, {
        itemSelector: '.grid-item',
        columnWidth: parseInt(document.getElementById('thumbnailWidth').value),
        gutter: 15,
        fitWidth: true
    });
    
    // Calculate browsing stats
    updateBrowsingStats();
}

/**
 * Update browsing statistics (total images, unique scenes, cluster sizes)
 */
function updateBrowsingStats() {
    const clusterSizes = {};
    Object.values(SCORE_DATA).forEach(score => {
        const clusterId = score.cluster_id || 'unknown';
        clusterSizes[clusterId] = (clusterSizes[clusterId] || 0) + 1;
    });
    
    const uniqueScenes = Object.keys(clusterSizes).length;
    const avgClusterSize = uniqueScenes > 0 ? (allMediaFiles.length / uniqueScenes) : 0;
    
    document.getElementById('browseTotalCount').textContent = allMediaFiles.length;
    document.getElementById('browseSceneCount').textContent = uniqueScenes;
    document.getElementById('browseAvgCluster').textContent = avgClusterSize.toFixed(1);
}

/**
 * Toggle the browsing info panel visibility
 */
function toggleInfoPanel() {
    const panel = document.getElementById('browsingInfoPanel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

/**
 * Shuffle and re-render the browsing gallery
 */
function shuffleGallery() {
    allMediaFiles = [...allMediaFiles].sort(() => Math.random() - 0.5);
    displayBrowsingGallery();
}
