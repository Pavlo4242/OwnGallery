// ============ FULLSCREEN & PLAYBACK MANAGEMENT ============

/**
 * Open media in fullscreen mode
 * @param {string} fileName - Path to media file
Overlay and Slideshow logic.*
 
 */*


app.fullscreen = {
    open(fileName) {
        const s = app.state;
        if (s.overlayTransitioning) return;
        
        s.currentMediaIndex = s.allMediaFiles.indexOf(fileName);
        if (s.currentMediaIndex === -1) return;

        const overlay = document.getElementById('fullscreenOverlay');
        const content = overlay.querySelector('.fullscreen-content');
        const info = s.MEDIA_DATA[fileName];

        // Content Creation
        content.innerHTML = '';
        const mediaEl = app.media.createElement(fileName);
        if(info.isVideo) {
            mediaEl.controls = true;
            mediaEl.autoplay = true;
        }
        content.appendChild(mediaEl);

        // Update Info
        document.querySelector('.media-filename').textContent = info.name;
        document.querySelector('.media-counter').textContent = `${s.currentMediaIndex + 1} / ${s.allMediaFiles.length}`;

        // Sync Select Dropdown
        const dir = fileName.split('/').slice(0, -1).join('/') || 'Root';
        const fsSelect = document.getElementById('fullscreenFolderSelect');
        if(fsSelect.querySelector(`option[value="${dir}"]`)) fsSelect.value = dir;

        overlay.classList.add('visible');
        this.updateNavButtons();
    },

    close() {
        document.getElementById('fullscreenOverlay').classList.remove('visible');
        document.querySelector('.fullscreen-content').innerHTML = ''; // Stop video
        this.stopSlideshow();
    },

    navigate(dir) {
        const s = app.state;
        let newIndex = s.currentMediaIndex + dir;
        
        if (s.slideshowShuffle && dir === 1) {
            // Random index logic
            newIndex = Math.floor(Math.random() * s.allMediaFiles.length);
        }

        if (newIndex >= 0 && newIndex < s.allMediaFiles.length) {
            this.open(s.allMediaFiles[newIndex]);
        } else {
            this.stopSlideshow();
        }
    },

    updateNavButtons() {
        const s = app.state;
        document.getElementById('prevBtn').disabled = s.currentMediaIndex <= 0;
        document.getElementById('nextBtn').disabled = s.currentMediaIndex >= s.allMediaFiles.length - 1;
        this.updateProgressBar();
    },

    // --- Slideshow ---
    toggleSlideshow() {
        app.state.isPlaying ? this.stopSlideshow() : this.startSlideshow();
    },

    startSlideshow() {
        const delay = parseInt(document.getElementById('advanceTime').value) || 3000;
        app.state.isPlaying = true;
        document.getElementById('playPauseBtn').textContent = '⏸ Pause';
        
        app.state.autoAdvanceInterval = setInterval(() => {
            this.navigate(1);
        }, delay);
    },

    stopSlideshow() {
        clearInterval(app.state.autoAdvanceInterval);
        app.state.isPlaying = false;
        document.getElementById('playPauseBtn').textContent = '▶ Play';
    },
    
    // --- Progress ---
    updateProgressBar() {
        const pct = ((app.state.currentMediaIndex + 1) / app.state.allMediaFiles.length) * 100;
        document.getElementById('progressFill').style.height = `${pct}%`;
    },

    jumpToProgress(e) {
        const bar = document.getElementById('verticalProgress');
        const pct = (e.clientY - bar.getBoundingClientRect().top) / bar.offsetHeight;
        const index = Math.floor(pct * app.state.allMediaFiles.length);
        this.open(app.state.allMediaFiles[index]);
    }
};
