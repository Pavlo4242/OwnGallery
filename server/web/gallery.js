app.gallery = {
    // Primary Filter Logic
    filterByFolder(recordHistory = true) {
        const s = app.state;
        const folder = document.getElementById('folderFilter').value;
        const grid = document.querySelector('.grid');
        
        document.getElementById('galleryDir').textContent = folder === 'all' ? 'Root' : folder;
        if (s.masonry) { s.masonry.destroy(); s.masonry = null; }
        grid.innerHTML = '';

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

        // Apply Shuffle if active (optional restoration of feature)
        // if (s.isShuffled) app.utils.shuffleArray(displayList);

        s.allMediaFiles = displayList;
        s.loadedMediaCount = 0;
        
        app.media.appendBatch(s.allMediaFiles.slice(0, s.filesPerLoad));
        s.loadedMediaCount += s.filesPerLoad;
        this.updateCounter();
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
    }
};
