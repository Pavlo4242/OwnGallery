// ============ MODE MANAGEMENT ============

/**
 * Switch between the three main modes: Sorting, Comparing, Browsing
 * @param {string} mode - The mode to switch to
 Logic for Sorting, Comparing, and Browsing modes.*
 */



app.modes = {
    set(mode) {
        app.state.currentMode = mode;
        
        // Toggle UI Buttons
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        document.querySelector(`.mode-${mode}`).classList.add('active');
        
        // Toggle Content Areas
        document.querySelectorAll('.content-area').forEach(d => d.style.display = 'none');
        document.getElementById(`${mode}Content`).style.display = 'block';
        
        // Toggle Control Groups
        document.querySelectorAll('.controls-group').forEach(g => g.style.display = 'none');
        document.querySelectorAll(`.${mode}-controls`).forEach(g => g.style.display = 'flex');

        if (mode === 'comparing') this.initComparing();
        if (mode === 'browsing') this.initBrowsing();
    },

    // --- Comparing Mode ---
    initComparing() {
        // Mock comparison generation based on name similarity or clustering (simplified)
        app.state.comparisonPairs = [];
        const files = [...app.state.allMediaFiles];
        // Create random pairs for demo
        for(let i=0; i<files.length-1; i+=2) {
            app.state.comparisonPairs.push([files[i], files[i+1]]);
        }
        this.loadNewComparison();
    },

    loadNewComparison() {
        const s = app.state;
        if (s.comparisonPairs.length === 0) {
            document.getElementById('comparisonPair').innerHTML = 'Done!';
            return;
        }
        const [p1, p2] = s.comparisonPairs.pop();
        
        const renderItem = (path) => `
            <div class="compare-item" onclick="app.modes.selectWinner('${path}')">
                ${app.media.createElement(path).outerHTML}
                <div class="compare-info">${app.state.MEDIA_DATA[path].name}</div>
            </div>`;

        document.getElementById('comparisonPair').innerHTML = 
            renderItem(p1) + '<div style="align-self:center">VS</div>' + renderItem(p2);
            
        document.getElementById('comparisonCount').textContent = s.comparisonResults.length;
    },

    selectWinner(path) {
        // Logic to store winner
        this.loadNewComparison();
    },

    // --- Browsing Mode ---
    initBrowsing() {
        const grid = document.getElementById('browsingGrid');
        grid.innerHTML = '';
        // Simple render of all items
        app.state.allMediaFiles.forEach(path => {
            const el = document.createElement('div');
            el.className = 'grid-item';
            el.style.width = '200px';
            el.appendChild(app.media.createElement(path));
            el.onclick = () => app.fullscreen.open(path);
            grid.appendChild(el);
        });
        // Init masonry specifically for browsing if needed
    },

    toggleInfo() {
        const panel = document.getElementById('browsingInfoPanel');
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
};
