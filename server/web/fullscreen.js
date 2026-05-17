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
        // Hide EXIF panel if open
        const panel = document.getElementById('exifPanel');
        if (panel && panel.style.display === 'block') panel.style.display = 'none';

        s._currentFullscreenFile = fileName; // #13: Track for rename
        this.updateMarkStatus();
        const drawer = document.getElementById('fsFileDrawer');
        if (drawer && drawer.classList.contains('open')) this.populateDrawer();

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
        const panel = document.getElementById('exifPanel');
        if (panel) panel.style.display = 'none';
        app.state._currentFullscreenFile = null;
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

    // --- File List Drawer ---
    toggleDrawer() {
        const drawer = document.getElementById('fsFileDrawer');
        if (!drawer) return;
        if (drawer.classList.contains('open')) {
            drawer.classList.remove('open');
        } else {
            drawer.classList.add('open');
            this.populateDrawer();
        }
    },

    populateDrawer() {
        const content = document.getElementById('fsDrawerContent');
        if (!content) return;
        
        const s = app.state;
        const currentFile = s._currentFullscreenFile;
        if (!currentFile) return;
        
        // Find current directory
        const dir = currentFile.split('/').slice(0, -1).join('/') || 'all';
        const files = s.FOLDER_MAP[dir] || [];
        
        let html = '';
        files.forEach((f, idx) => {
            const info = s.MEDIA_DATA[f];
            if (!info) return;
            const isActive = f === currentFile ? 'active' : '';
            // Only use thumbnails for images to avoid loading heavy videos unnecessarily
            const thumbStyle = !info.isVideo ? `background-image: url('${CSS.escape(info.url)}');` : `background: #555; display:flex; align-items:center; justify-content:center; font-size:10px;`;
            const thumbContent = info.isVideo ? '🎥' : '';
            
            html += `<div class="drawer-item ${isActive}" onclick="app.fullscreen.open('${CSS.escape(f)}')">
                        <div class="drawer-item-thumb" style="${thumbStyle}">${thumbContent}</div>
                        <div class="drawer-item-name" title="${info.name}">${info.name}</div>
                     </div>`;
        });
        
        content.innerHTML = html;
        
        // Scroll active into view
        setTimeout(() => {
            const activeEl = content.querySelector('.active');
            if (activeEl) activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    },

    // Toggle EXIF / AI Prompt metadata panel
    async toggleExif() {
        let panel = document.getElementById('exifPanel');
        if (!panel) {
            panel = document.createElement('div');
            panel.id = 'exifPanel';
            panel.className = 'exif-panel';
            document.getElementById('fullscreenOverlay').appendChild(panel);
        }
        
        if (panel.style.display === 'block') {
            panel.style.display = 'none';
            return;
        }

        const fileName = app.state._currentFullscreenFile;
        if (!fileName) return;
        const info = app.state.MEDIA_DATA[fileName];
        panel.style.display = 'block';
        panel.innerHTML = '<h4>EXIF / Prompt Data</h4>Loading...';

        try {
            let output = '';
            
            // Ultra-lightweight native PNG tEXt/iTXt chunk parser (great for AI Prompts)
            if (info.url.toLowerCase().endsWith('.png')) {
                const res = await fetch(info.url);
                const buf = await res.arrayBuffer();
                const view = new DataView(buf);
                if (view.getUint32(0) === 0x89504e47) {
                    let offset = 8;
                    const dec = new TextDecoder();
                    while (offset < view.byteLength) {
                        const len = view.getUint32(offset);
                        const type = dec.decode(new Uint8Array(buf, offset + 4, 4));
                        if (type === 'tEXt' || type === 'iTXt') {
                            const data = dec.decode(new Uint8Array(buf, offset + 8, len));
                            const split = data.split('\0');
                            const key = split[0];
                            const val = split[split.length - 1]; // iTXt value is at the end
                            if (key !== 'workflow' && val.length > 2) {
                                output += `<div style="color:#4CAF50; font-weight:bold; margin-top:10px; display:flex; justify-content:space-between; align-items:center;">
                                                <span>${key}:</span>
                                                <button class="copy-exif-btn" data-val="${btoa(encodeURIComponent(val))}" style="background:#333; color:#fff; border:1px solid #555; border-radius:4px; cursor:pointer; font-size:11px; padding:2px 8px;">📋 Copy</button>
                                           </div>
                                           <div style="margin-top:4px;">${val}</div>\n`;
                            }
                        }
                        offset += 8 + len + 4;
                    }
                }
            }

            // Fallback to EXIF library for JPEG/WebP or if PNG had no chunks
            if (!output) {
                if (typeof exifr === 'undefined') {
                    await new Promise(r => {
                        const s = document.createElement('script');
                        s.src = 'https://cdn.jsdelivr.net/npm/exifr/dist/lite.umd.js';
                        s.onload = r;
                        document.head.appendChild(s);
                    });
                }
                const exifData = await exifr.parse(info.url) || {};
                for (const [key, val] of Object.entries(exifData)) {
                    if (typeof val !== 'object') {
                        output += `<div style="display:flex; justify-content:space-between; margin-top:4px;">
                                       <b style="color:#2196F3;">${key}:</b>
                                       <button class="copy-exif-btn" data-val="${btoa(encodeURIComponent(val))}" style="background:#333; color:#fff; border:1px solid #555; border-radius:4px; cursor:pointer; font-size:10px; padding:2px 6px;">Copy</button>
                                   </div>
                                   <div>${val}</div>\n`;
                    }
                }
            }

            panel.innerHTML = '<h4>EXIF / Prompt Data</h4>' + (output || '<i>No metadata found.</i>');
            
            // Attach copy listeners
            panel.querySelectorAll('.copy-exif-btn').forEach(btn => {
                btn.onclick = async () => {
                    try {
                        const text = decodeURIComponent(atob(btn.getAttribute('data-val')));
                        await navigator.clipboard.writeText(text);
                        btn.textContent = '✅ Copied!';
                        setTimeout(() => btn.textContent = '📋 Copy', 2000);
                        app.utils.showToast('Copied to clipboard', 'success');
                    } catch(e) {
                        app.utils.showToast('Failed to copy', 'error');
                    }
                };
            });
        } catch (e) {
            panel.innerHTML = `<h4>EXIF / Prompt Data</h4><i>Error: ${e.message}</i>`;
        }
    },

    // Update the visual status of marked-for-deletion items
    updateMarkStatus() {
        const s = app.state;
        const fileName = s._currentFullscreenFile;
        const overlay = document.getElementById('fullscreenOverlay');
        const btn = document.getElementById('markBtn');
        if (!fileName || !overlay) return;

        const isMarked = s.selectedFiles.has(fileName);
        if (isMarked) {
            overlay.classList.add('marked');
            if (btn) {
                btn.textContent = '☒ Unmark';
                btn.style.background = 'rgba(244,67,54,0.3)';
                btn.style.borderColor = 'rgba(244,67,54,0.5)';
            }
        } else {
            overlay.classList.remove('marked');
            if (btn) {
                btn.textContent = '☑ Mark & Next';
                btn.style.background = 'rgba(76,175,80,0.3)';
                btn.style.borderColor = 'rgba(76,175,80,0.5)';
            }
        }
    },

    // Toggle mark current fullscreen file for deletion and advance on mark
    markForDeletion() {
        const s = app.state;
        const fileName = s._currentFullscreenFile;
        if (!fileName) return;

        if (s.selectedFiles.has(fileName)) {
            // Unmark
            s.selectedFiles.delete(fileName);
            const itemDom = document.querySelector(`.grid-item[data-file-name="${CSS.escape(fileName)}"]`);
            if (itemDom) {
                itemDom.classList.remove('selected');
                const cb = itemDom.querySelector('input[type="checkbox"]');
                if (cb) cb.checked = false;
            }
            app.utils.updateDeleteBtn();
            app.utils.showToast('Unmarked file', 'info');
            this.updateMarkStatus();
        } else {
            // Mark
            if (!s.multiSelectMode) {
                app.utils.toggleMultiSelect();
            }
            s.selectedFiles.add(fileName);
            const itemDom = document.querySelector(`.grid-item[data-file-name="${CSS.escape(fileName)}"]`);
            if (itemDom) {
                itemDom.classList.add('selected');
                const cb = itemDom.querySelector('input[type="checkbox"]');
                if (cb) cb.checked = true;
            }
            app.utils.updateDeleteBtn();
            app.utils.showToast('Marked for deletion', 'info');
            this.updateMarkStatus();
            // Auto advance
            this.navigate(1);
        }
    },

    // Delete current fullscreen file
    async deleteCurrentFile() {
        const s = app.state;
        if (s.isDeleting) return; // Prevent popup spam
        s.isDeleting = true;

        try {
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
        } finally {
            setTimeout(() => { s.isDeleting = false; }, 500);
        }
    }
};
