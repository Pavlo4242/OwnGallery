// ============ FULLSCREEN & PLAYBACK MANAGEMENT ============

/**
 * Open media in fullscreen mode
 * @param {string} fileName - Path to media file
 * Overlay and Slideshow logic.
 */



app.fullscreen = {
    open(fileName) {
        const s = app.state;
        if (s.overlayTransitioning) return;
        
        s.currentMediaIndex = s.allMediaFiles.indexOf(fileName);
        if (s.currentMediaIndex === -1) return;
        s._currentFullscreenFile = fileName; // #13: Track for rename

        const overlay = document.getElementById('fullscreenOverlay');
        const content = overlay.querySelector('.fullscreen-content');
        const info = s.MEDIA_DATA[fileName];

        // Content Creation
        content.innerHTML = '';
        let mediaEl;
        if (info.isVideo) {
            mediaEl = document.createElement('video');
            mediaEl.src = info.url;
            mediaEl.controls = true;
            mediaEl.autoplay = true;
        } else {
            // Fullscreen: load full-res directly (not lazy)
            mediaEl = document.createElement('img');
            mediaEl.src = info.url;
        }
        content.appendChild(mediaEl);

        // Update Info
        document.querySelector('.media-filename').textContent = info.name;
        document.querySelector('.media-counter').textContent = `${s.currentMediaIndex + 1} / ${s.allMediaFiles.length}`;

        // #12: Show dimensions and file size
        const metaEl = document.querySelector('.media-meta') || (() => {
            const el = document.createElement('div');
            el.className = 'media-meta';
            document.querySelector('.media-info').appendChild(el);
            return el;
        })();
        const sizeStr = info.size ? this.formatFileSize(info.size) : '';
        metaEl.textContent = sizeStr;
        if (!info.isVideo && mediaEl.tagName === 'IMG') {
            mediaEl.onload = () => {
                metaEl.textContent = `${mediaEl.naturalWidth} × ${mediaEl.naturalHeight}  •  ${sizeStr}`;
            };
        }

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
    },

    // #12: Human-readable file size
    formatFileSize(bytes) {
        if (!bytes) return '';
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        let size = bytes;
        while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
        return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
    },

    // #13: Rename current file
    async renameCurrentFile() {
        const s = app.state;
        const fileName = s._currentFullscreenFile;
        if (!fileName) return;
        const info = s.MEDIA_DATA[fileName];
        if (!info) return;

        const newName = prompt('Rename file:', info.name);
        if (!newName || newName === info.name) return;

        const res = await fetch('/api/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: fileName, newName })
        });

        if (res.ok) {
            app.utils.showToast('Renamed successfully', 'success');
            app.fullscreen.close();
            app.main.init();
        } else {
            app.utils.showToast('Rename failed: ' + (await res.text()), 'error');
        }
    },

    // Delete current fullscreen file
    async deleteCurrentFile() {
        const s = app.state;
        const fileName = s._currentFullscreenFile;
        if (!fileName) return;
        if (!confirm(`Delete "${s.MEDIA_DATA[fileName]?.name}"?`)) return;

        // Windows File Lock Fix: clear the fullscreen player
        const content = document.querySelector('.fullscreen-content');
        if (content) {
            const media = content.querySelector('video, img');
            if (media) {
                media.pause && media.pause();
                media.removeAttribute('src');
                media.load && media.load();
            }
            content.innerHTML = '';
        }

        // Wait a moment for the browser to completely release file handles
        await new Promise(r => setTimeout(r, 200));

        const res = await fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: [fileName] })
        });

        const data = await res.json().catch(() => null);
        if (data && (data.success || []).length > 0) {
            app.utils.showToast('Deleted file', 'success');
            // Navigate to next image or close if last
            const nextIdx = s.currentMediaIndex;
            // Remove from data
            delete s.MEDIA_DATA[fileName];
            s.allMediaFiles = s.allMediaFiles.filter(f => f !== fileName);
            if (s.allMediaFiles.length > 0) {
                const safeIdx = Math.min(nextIdx, s.allMediaFiles.length - 1);
                this.open(s.allMediaFiles[safeIdx]);
            } else {
                this.close();
                app.main.init();
            }
            app.gallery.updateCounter();
        } else {
            app.utils.showToast('Delete failed', 'error');
            console.error("Delete failures:", data?.failed);
            // Re-open since it failed
            this.open(fileName);
        }
    }
};
