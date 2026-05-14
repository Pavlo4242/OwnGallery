app.gallery = {
    // Primary Filter Logic
    filterByFolder(recordHistory = true) {
        const s = app.state;
        const folder = document.getElementById('folderFilter').value;
        const grid = document.querySelector('.grid');
        
        document.getElementById('galleryDir').textContent = folder === 'all' ? 'Root' : folder;
        if (s.masonry) { s.masonry.destroy(); s.masonry = null; }
        grid.innerHTML = '';
        s.focusedIndex = -1;

        // History Management
        if (recordHistory) {
            if (s.historyIndex === -1 || s.navigationHistory[s.historyIndex] !== folder) {
                s.navigationHistory = s.navigationHistory.slice(0, s.historyIndex + 1);
                s.navigationHistory.push(folder);
                s.historyIndex++;
            }
        }
        this.updateNavButtons();

        // Render Subfolders
        this.renderSubfolders(folder);

        // Filter Files
        let displayList = folder === 'all' 
            ? [...s.FOLDER_MAP['all']] 
            : s.FOLDER_MAP['all'].filter(f => f.startsWith(folder + '/'));

        s.allMediaFiles = this.sortFiles(displayList);
        s.loadedMediaCount = 0;
        
        app.media.appendBatch(s.allMediaFiles.slice(0, s.filesPerLoad));
        s.loadedMediaCount += s.filesPerLoad;
        this.updateCounter();
        app.utils.saveSettings(); // #10: Persist folder
    },

    renderSubfolders(currentFolder) {
        const s = app.state;
        const width = document.getElementById('thumbnailWidth').value;
        const prefix = currentFolder === 'all' ? '' : currentFolder + '/';
        
        const subfolders = s.allDirectories.filter(dir => {
            if (currentFolder === 'all') return !dir.includes('/');
            return dir.startsWith(prefix) && dir.slice(prefix.length).indexOf('/') === -1 && dir !== currentFolder;
        });

        const grid = document.querySelector('.grid');
        subfolders.forEach(dir => {
            const card = document.createElement('div');
            card.className = 'grid-item folder-card';
            card.style.width = `${width}px`;
            card.innerHTML = `<div class="folder-icon">📁</div><div>${dir.split('/').pop()}</div>`;
            card.onclick = () => {
                document.getElementById('folderFilter').value = dir;
                this.filterByFolder(true);
            };

            // #11: Drop target for drag-and-drop file moving
            card.ondragover = (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; card.classList.add('drag-over'); };
            card.ondragleave = () => { card.classList.remove('drag-over'); };
            card.ondrop = async (e) => {
                e.preventDefault();
                card.classList.remove('drag-over');
                try {
                    const paths = JSON.parse(e.dataTransfer.getData('text/plain'));
                    if (!paths || paths.length === 0) return;
                    const res = await fetch('/api/move', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ paths, target: dir })
                    });
                    const data = await res.json().catch(() => null);
                    if (data) {
                        const ok = (data.success || []).length;
                        if (ok > 0) app.utils.showToast(`Moved ${ok} file(s) to ${dir.split('/').pop()}`, 'success');
                        if ((data.failed || []).length > 0) app.utils.showToast('Some files failed to move', 'error');
                    }
                    app.state.selectedFiles.clear();
                    app.main.init();
                } catch (err) { console.error('Drop error:', err); }
            };

            grid.appendChild(card);
        });
    },

    updateCounter() {
        const total = app.state.allMediaFiles.length;
        const loaded = Math.min(app.state.loadedMediaCount, total);
        document.getElementById('fileCounter').textContent = `${total} files`;
        document.getElementById('loadedCount').textContent = loaded;
        document.getElementById('totalCount').textContent = total;
    },

    loadMore() {
        const s = app.state;
        if (s.loadedMediaCount >= s.allMediaFiles.length) {
            // End of files reached? Check if we should show Next Folder Card
            const current = document.getElementById('folderFilter').value;
            if (current !== 'all' && !document.querySelector('.next-folder-card')) {
                app.media.appendNextFolderCard(current);
            }
            return;
        }
        
        const nextBatch = s.allMediaFiles.slice(s.loadedMediaCount, s.loadedMediaCount + s.filesPerLoad);
        app.media.appendBatch(nextBatch);
        s.loadedMediaCount += nextBatch.length;
    },

    // History Navigation
    navigateHistory(direction) {
        const s = app.state;
        if (direction === -1 && s.historyIndex > 0) {
            s.historyIndex--;
        } else if (direction === 1 && s.historyIndex < s.navigationHistory.length - 1) {
            s.historyIndex++;
        } else {
            return;
        }
        
        const folder = s.navigationHistory[s.historyIndex];
        document.getElementById('folderFilter').value = folder;
        this.filterByFolder(false); // Don't record this step
    },

    updateNavButtons() {
        const s = app.state;
        const backBtn = document.getElementById('navBackBtn');
        const fwdBtn = document.getElementById('navForwardBtn');
        
        if (backBtn) backBtn.disabled = s.historyIndex <= 0;
        if (fwdBtn) fwdBtn.disabled = s.historyIndex >= s.navigationHistory.length - 1;
    },
    
    populateDropdowns() {
        const select = document.getElementById('folderFilter');
        const fsSelect = document.getElementById('fullscreenFolderSelect');
        const current = select.value || 'all';
        
        const opts = ['<option value="all">All Files</option>'];
        const fsOpts = ['<option value="">Jump to Folder...</option>'];
        
        Object.keys(app.state.FOLDER_MAP).sort().forEach(folder => {
            if (folder === 'all') return;
            const depth = (folder.match(/\//g) || []).length;
            const indent = '&nbsp;'.repeat(depth * 2);
            opts.push(`<option value="${folder}">${indent}${folder}</option>`);
            fsOpts.push(`<option value="${folder}">${indent}${folder}</option>`);
        });
        
        select.innerHTML = opts.join('');
        select.value = current;
        fsSelect.innerHTML = fsOpts.join('');
    },

    handleSortChange() {
        app.state.sortBy = document.getElementById('sortFilter').value;
        app.utils.saveSettings();
        this.filterByFolder(false);
    },

    sortFiles(files) {
        const s = app.state;
        const sortMode = s.sortBy || 'name_asc';
        
        return files.sort((a, b) => {
            const dataA = s.MEDIA_DATA[a];
            const dataB = s.MEDIA_DATA[b];
            if (!dataA || !dataB) return 0;
            
            switch (sortMode) {
                case 'name_desc':
                    return dataB.name.localeCompare(dataA.name, undefined, {numeric: true});
                case 'date_desc':
                    return new Date(dataB.modified) - new Date(dataA.modified);
                case 'date_asc':
                    return new Date(dataA.modified) - new Date(dataB.modified);
                case 'size_desc':
                    return (dataB.size || 0) - (dataA.size || 0);
                case 'size_asc':
                    return (dataA.size || 0) - (dataB.size || 0);
                case 'name_asc':
                default:
                    return dataA.name.localeCompare(dataB.name, undefined, {numeric: true});
            }
        });
    },

    shuffle() {
        app.utils.shuffleArray(app.state.allMediaFiles);
        const grid = document.querySelector('.grid');
        if (app.state.masonry) { app.state.masonry.destroy(); app.state.masonry = null; }
        grid.innerHTML = '';
        app.state.loadedMediaCount = 0;
        app.media.appendBatch(app.state.allMediaFiles.slice(0, app.state.filesPerLoad));
    },

    jumpToFolder(folderName) {
        if (!folderName) return;
        document.getElementById('folderFilter').value = folderName;
        app.fullscreen.close();
        this.filterByFolder(true);
        window.scrollTo({top: 0, behavior: 'smooth'});
    },

    setFocus(index) {
        const s = app.state;
        const items = document.querySelectorAll('.grid-item');
        if (items.length === 0) return;

        // Remove old focus
        items.forEach(el => el.classList.remove('focused'));

        // Clamp index
        if (index < 0) index = 0;
        if (index >= items.length) index = items.length - 1;

        s.focusedIndex = index;
        const target = items[index];
        if (target) {
            target.classList.add('focused');
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Trigger hover behavior for video playback
            app.state.hoveredMedia = target;
            app.media.managePlayback();
        }
    },

    moveFocus(dir) {
        const s = app.state;
        const items = document.querySelectorAll('.grid-item');
        if (items.length === 0) return;

        let newIndex = s.focusedIndex;
        if (newIndex === -1) {
            this.setFocus(0);
            return;
        }

        const currentRect = items[newIndex].getBoundingClientRect();

        if (dir === 'left') {
            newIndex--;
        } else if (dir === 'right') {
            newIndex++;
        } else {
            // Spatial search for Up/Down
            let closest = -1;
            let minDist = Infinity;

            for (let i = 0; i < items.length; i++) {
                if (i === newIndex) continue;
                const rect = items[i].getBoundingClientRect();
                
                if (dir === 'up' && rect.top >= currentRect.top - 5) continue;
                if (dir === 'down' && rect.top <= currentRect.top + 5) continue;

                // Distance calculation heavily penalizes X difference to enforce columns
                const dx = Math.abs(rect.left - currentRect.left);
                const dy = Math.abs(rect.top - currentRect.top);
                const distance = (dx * 10) + dy;

                if (distance < minDist) {
                    minDist = distance;
                    closest = i;
                }
            }
            if (closest !== -1) newIndex = closest;
        }

        this.setFocus(newIndex);
    }
};
