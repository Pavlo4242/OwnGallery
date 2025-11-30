// ============ FULLSCREEN & PLAYBACK MANAGEMENT ============

/**
 * Open media in fullscreen mode
 * @param {string} fileName - Path to media file
 */
function openFullscreen(fileName) {
    if (overlayTransitioning) return; // Block accidental re-triggers
    overlayTransitioning = true;
    setTimeout(() => { overlayTransitioning = false; }, 100); // Release lock after animation

    const overlay = document.getElementById('fullscreenOverlay');
    const content = document.querySelector('.fullscreen-content');
    
    currentMediaIndex = allMediaFiles.indexOf(fileName);
    if (currentMediaIndex === -1) return;
    
    viewedFiles.add(fileName);
    populateFolderFilter();
    
    const mediaInfo = MEDIA_DATA[fileName];
    const isVideo = mediaInfo.isVideo;
    content.innerHTML = '';

    let mediaElement;
    if (isVideo) {
        mediaElement = document.createElement('video');
        mediaElement.controls = true;
        mediaElement.autoplay = true;
        mediaElement.muted = false;
        mediaElement.loop = false;
        mediaElement.preload = 'auto';
        
        mediaElement.addEventListener('keydown', (e) => {
            if (['ArrowLeft', 'ArrowRight', 'a', 'd'].includes(e.key)) {
                e.preventDefault();
                if (e.key === 'ArrowRight' || e.key === 'd') navigateFullscreen(1);
                if (e.key === 'ArrowLeft' || e.key === 'a') navigateFullscreen(-1);
            }
        });
    } else {
        mediaElement = document.createElement('img');
    }

    mediaElement.src = mediaInfo.url;
    content.appendChild(mediaElement);
    
    updateProgressBar();
    updateFullscreenInfo(fileName);
    
    const dirParts = fileName.split('/');
    const dirPath = dirParts.length > 1 ? dirParts.slice(0, -1).join('/') : 'Root';
    document.getElementById('fullscreenDir').textContent = dirPath;
    
    if (!isPlaying) {
         const fsSelect = document.getElementById('fullscreenFolderSelect');
         if (FOLDER_MAP[dirPath]) {
             fsSelect.value = dirPath;
         } else {
             fsSelect.value = "";
         }
    }

    updateShuffleButtonText();
    overlay.classList.add('visible');
    resetControlsTimer();
}

/**
 * Update fullscreen info display
 * @param {string} fileName - Current file name
 */
function updateFullscreenInfo(fileName) {
    const mediaInfo = MEDIA_DATA[fileName];
    const infoDiv = document.getElementById('mediaInfo');
    
    infoDiv.querySelector('.media-counter').textContent = `${currentMediaIndex + 1} / ${allMediaFiles.length}`;
    infoDiv.querySelector('.media-filename').textContent = mediaInfo.name;
    infoDiv.querySelector('.media-filetype').textContent = `${getFileExtension(mediaInfo.name)} • ${mediaInfo.isVideo ? 'Video' : 'Image'}`;
    
    document.getElementById('prevBtn').disabled = currentMediaIndex <= 0;
    document.getElementById('nextBtn').disabled = currentMediaIndex >= allMediaFiles.length - 1;
}

/**
 * Navigate to next/previous media in fullscreen
 * @param {number} direction - 1 for next, -1 for previous
 * @param {boolean} forceSequential - Force sequential navigation
 */
function navigateFullscreen(direction, forceSequential = false) {
    // Always follow the current list order (which is sorted or shuffled based on the checkbox)
    let newIndex = currentMediaIndex + direction;
    
    if (newIndex >= 0 && newIndex < allMediaFiles.length) {
        currentMediaIndex = newIndex;
        openFullscreen(allMediaFiles[currentMediaIndex]);
    } else if (newIndex >= allMediaFiles.length) {
        stopAutoAdvance();
    }
}

/**
 * Close fullscreen mode
 */
function closeFullscreen() {
    document.getElementById('fullscreenOverlay').classList.remove('visible');
    stopAutoAdvance();
    currentMediaIndex = -1;
    const content = document.querySelector('.fullscreen-content');
    content.innerHTML = ''; 
}

/**
 * Start auto-advance slideshow
 */
function startAutoAdvance() {
    stopAutoAdvance();
    let delay = parseInt(document.getElementById('advanceTime').value);
    if (isNaN(delay) || delay < 500) {
        delay = 500;
        document.getElementById('advanceTime').value = 500;
    }

    autoAdvanceInterval = setInterval(() => {
        if (currentMediaIndex < allMediaFiles.length - 1) {
            navigateFullscreen(1);
            updateProgressBar();
        } else {
            stopAutoAdvance();
        }
    }, delay);
    isPlaying = true;
    document.getElementById('playPauseBtn').textContent = '⏸ Pause';
    document.getElementById('playPauseBtn').classList.add('active');
    updateProgressBar();
}

/**
 * Stop auto-advance slideshow
 */
function stopAutoAdvance() {
    if (autoAdvanceInterval) {
        clearInterval(autoAdvanceInterval);
        autoAdvanceInterval = null;
    }
    isPlaying = false;
    document.getElementById('playPauseBtn').textContent = '▶ Play';
    document.getElementById('playPauseBtn').classList.remove('active');
}

/**
 * Seek video playback
 * @param {number} seconds - Seconds to seek (positive or negative)
 */
function seekVideo(seconds) {
    const video = document.querySelector('.fullscreen-content video');
    if (video) {
        video.currentTime += seconds;
    }
}

/**
 * Update vertical progress bar
 */
function updateProgressBar() {
    const progressBar = document.getElementById('verticalProgress');
    const progressFill = document.getElementById('progressFill');
    
    progressBar.style.display = 'block';
    const progressPercent = ((currentMediaIndex + 1) / allMediaFiles.length) * 100;
    progressFill.style.height = progressPercent + '%';
}

/**
 * Jump to specific position in gallery via progress bar click
 * @param {Event} e - Click event
 */
function jumpToProgress(e) {
    e.stopPropagation();
    const progressBar = document.getElementById('verticalProgress');
    const rect = progressBar.getBoundingClientRect();
    const clickY = e.clientY - rect.top;
    const height = rect.height;
    const percentage = clickY / height;
    
    let newIndex = Math.floor(percentage * allMediaFiles.length);
    newIndex = Math.max(0, Math.min(newIndex, allMediaFiles.length - 1));
    
    openFullscreen(allMediaFiles[newIndex]);
}

/**
 * Reset controls auto-hide timer
 */
function resetControlsTimer() {
    const controls = document.getElementById('playbackControls');
    controls.classList.remove('auto-hide');
    clearTimeout(controlsHideTimer);
    controlsHideTimer = setTimeout(() => {
        if (isPlaying) controls.classList.add('auto-hide');
    }, 3000);
}
