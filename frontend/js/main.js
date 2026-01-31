/**
 * LLMRI - LLM Research Methodology Inspector
 * Main JavaScript Application with Streaming Progress
 */

document.addEventListener('DOMContentLoaded', () => {
    // ==========================================================================
    // DOM Elements
    // ==========================================================================
    const elements = {
        themeToggle: document.getElementById('theme-toggle'),
        heroSection: document.getElementById('hero-section'),
        uploadSection: document.getElementById('upload-section'),
        resultsSection: document.getElementById('results-section'),
        uploadForm: document.getElementById('upload-form'),
        uploadZone: document.getElementById('upload-zone'),
        uploadContent: document.getElementById('upload-content'),
        fileInput: document.getElementById('paper-file'),
        filePreview: document.getElementById('file-preview'),
        fileName: document.getElementById('file-name'),
        fileSize: document.getElementById('file-size'),
        fileRemove: document.getElementById('file-remove'),
        analyzeButton: document.getElementById('analyze-button'),
        processing: document.getElementById('processing'),
        error: document.getElementById('error'),
        errorMessage: document.getElementById('error-message'),
        errorRetry: document.getElementById('error-retry'),
        backButton: document.getElementById('back-button'),
        downloadCsv: document.getElementById('download-csv'),
        downloadReport: document.getElementById('download-report'),
        scorePercent: document.getElementById('score-percent'),
        scoreRingFill: document.getElementById('score-ring-fill'),
        scoreRaw: document.getElementById('score-raw'),
        scoreDescription: document.getElementById('score-description'),
        sectionBars: document.getElementById('section-bars'),
        resultsAccordion: document.getElementById('results-accordion'),
        countAll: document.getElementById('count-all'),
        countIssues: document.getElementById('count-issues'),
        countNa: document.getElementById('count-na'),
        filterButtons: document.querySelectorAll('.filter-button'),
        paperInfo: document.getElementById('paper-info')
    };

    // ==========================================================================
    // State
    // ==========================================================================
    let state = {
        file: null,
        results: null,
        metadata: null,
        filename: null,
        mode: 'standard',
        currentFilter: 'all'
    };

    // ==========================================================================
    // Constants
    // ==========================================================================
    const STORAGE_KEY = 'llmri-saved-results';
    const USE_STREAMING = true;
    
    const SECTION_COLORS = {
        'Experimental Design Reporting': '#4285F4',
        'Acquisition Reporting': '#34a853',
        'Preprocessing Reporting': '#ea4335',
        'Statistical Modeling & Inference': '#fbbc04',
        'Results Reporting': '#9334e6',
        'Data Sharing & Reproducibility': '#ff6d01' 
    };

    const SECTIONS_ORDER = [
        'Experimental Design Reporting',
        'Acquisition Reporting',
        'Preprocessing Reporting',
        'Statistical Modeling & Inference',
        'Results Reporting',
        'Data Sharing & Reproducibility'  
    ];

    // ==========================================================================
    // Progress Handler Class
    // ==========================================================================
    class ProgressHandler {
        constructor() {
            this.mode = 'standard';
            this.totalPasses = 7;
            this.currentPass = 0;
        }

        init(mode) {
            this.mode = mode;
            this.currentPass = 0;
            
            const modeBadge = document.querySelector('#processing .mode-badge');
            if (modeBadge) {
                modeBadge.className = `mode-badge mode-badge--${mode === 'high-accuracy' ? 'high-accuracy' : 'standard'}`;
                modeBadge.textContent = mode === 'high-accuracy' ? 'High Accuracy Mode' : 'Standard Mode';
            }

            const haPanel = document.getElementById('high-accuracy-panel');
            if (haPanel) haPanel.classList.toggle('hidden', mode !== 'high-accuracy');

            if (mode === 'high-accuracy') this.initPassesGrid();

            const voteStats = document.getElementById('vote-stats');
            if (voteStats) voteStats.classList.add('hidden');
            
            const tbSection = document.getElementById('tiebreaker-section');
            if (tbSection) tbSection.classList.add('hidden');

            const hint = document.getElementById('processing-hint');
            if (hint) {
                hint.textContent = mode === 'high-accuracy' 
                    ? 'High-accuracy mode runs 7 analysis passes. This typically takes 10-15 minutes.'
                    : 'This typically takes 1-3 minutes depending on paper length.';
            }

            this.clearLog();
            this.updateProgress(0, 'Initializing...');
        }

        initPassesGrid() {
            const grid = document.getElementById('passes-grid');
            if (!grid) return;
            const temps = [0.0, 0.05, 0.1, 0.15, 0.1, 0.05, 0.0];
            grid.innerHTML = '';
            for (let i = 0; i < this.totalPasses; i++) {
                const pass = document.createElement('div');
                pass.className = 'pass-item';
                pass.id = `pass-${i + 1}`;
                pass.innerHTML = `<span>${i + 1}</span>`;
                pass.title = `Temperature: ${temps[i]}`;
                grid.appendChild(pass);
            }
        }

        updateProgress(percent, status) {
            const fill = document.getElementById('progress-fill');
            const statusEl = document.getElementById('progress-status');
            const percentEl = document.getElementById('progress-percent');
            if (fill) fill.style.width = `${percent}%`;
            if (statusEl) statusEl.textContent = status;
            if (percentEl) percentEl.textContent = `${Math.round(percent)}%`;
        }

        updateStep(step) {
            const steps = document.querySelectorAll('#standard-steps .step');
            const order = ['uploading', 'processing', 'analyzing', 'complete'];
            const idx = order.indexOf(step);
            steps.forEach((el, i) => {
                el.classList.remove('active', 'complete');
                if (i < idx) el.classList.add('complete');
                else if (i === idx) el.classList.add('active');
            });
        }

        updateActivity(text) {
            const el = document.querySelector('#activity-current .activity-text');
            if (el) el.textContent = text;
        }

        onPassStart(data) {
            this.currentPass = data.pass;
            const passEl = document.getElementById(`pass-${data.pass}`);
            if (passEl) passEl.className = 'pass-item active';
            this.updateActivity(`Running Pass ${data.pass}/${data.total} (temp: ${data.temperature})`);
            this.updateProgress(10 + (data.pass - 1) / data.total * 60, `Pass ${data.pass} of ${data.total}`);
            this.addLog(`Pass ${data.pass}/${data.total} started (temp=${data.temperature})`, 'info');
        }

        onPassComplete(data) {
            const passEl = document.getElementById(`pass-${data.pass}`);
            if (passEl) passEl.className = 'pass-item complete';
            this.addLog(data.failed ? `Pass ${data.pass} FAILED` : `Pass ${data.pass} complete: ${data.questions_scored} questions`, data.failed ? 'error' : 'success');
            this.updateProgress(10 + data.pass / data.total * 60, `Pass ${data.pass} complete`);
        }

        onVotingStart() {
            this.updateActivity('Computing majority vote...');
            this.updateProgress(75, 'Analyzing votes...');
            this.addLog('Computing majority vote...', 'info');
        }

        onVotingResult(data) {
            const voteStats = document.getElementById('vote-stats');
            if (voteStats) voteStats.classList.remove('hidden');
            ['unanimous', 'strong', 'weak', 'unresolved'].forEach(k => {
                const el = document.getElementById(`stat-${k}`);
                if (el) el.textContent = data[k];
            });
            this.updateActivity(`Vote complete: ${data.unresolved} need tie-breaker`);
            this.addLog(`Results: ${data.unanimous} unanimous, ${data.strong} strong, ${data.weak} weak, ${data.unresolved} unresolved`, 'info');
            if (data.unresolved === 0) this.updateProgress(95, 'Building results...');
        }

        onTiebreakerStart(data) {
            const tbSection = document.getElementById('tiebreaker-section');
            if (tbSection) tbSection.classList.remove('hidden');
            const countEl = document.getElementById('tiebreaker-count');
            if (countEl) countEl.textContent = data.questions.length;
            const roundsEl = document.getElementById('tiebreaker-rounds');
            if (roundsEl) {
                roundsEl.innerHTML = '';
                for (let i = 0; i < data.total_rounds; i++) {
                    const r = document.createElement('div');
                    r.className = 'tiebreaker-round';
                    r.id = `tb-round-${i + 1}`;
                    r.textContent = i + 1;
                    roundsEl.appendChild(r);
                }
            }
            this.updateActivity(`Tie-breakers for ${data.questions.length} questions...`);
            this.addLog(`Tie-breakers: ${data.questions.join(', ')}`, 'warning');
        }

        onTiebreakerRound(data) {
            const el = document.getElementById(`tb-round-${data.round}`);
            if (el) el.className = 'tiebreaker-round active';
            this.updateActivity(`Tie-breaker ${data.round}/${data.total}`);
            this.updateProgress(80 + (data.round / data.total) * 10, `Tie-breaker ${data.round}`);
        }

        onTiebreakerComplete(data) {
            const el = document.getElementById(`tb-round-${data.round}`);
            if (el) el.className = 'tiebreaker-round complete';
            this.addLog(`Round ${data.round}: ${data.resolved} resolved, ${data.remaining} left`, data.remaining > 0 ? 'warning' : 'success');
        }

        onForceResolve(data) {
            this.addLog(`Force-resolving: ${data.questions.join(', ')}`, 'warning');
        }

        onFinalScore(data) {
            this.updateProgress(100, 'Complete!');
            this.updateActivity(`Final: ${data.percentage}%`);
            this.addLog(`FINAL: ${data.raw_score}/${data.max_score} = ${data.percentage}%`, 'success');
        }

        onUpload(data) {
            if (data.status === 'uploading') {
                this.updateStep('uploading');
                this.updateProgress(5, 'Uploading...');
            } else {
                this.updateStep('processing');
                this.updateProgress(10, 'Uploaded');
                this.addLog(`PDF uploaded (${data.method})`, 'success');
            }
        }

        onInit(data) {
            this.totalPasses = data.passes || 7;
            this.addLog(`Init: ${data.passes} passes, ${data.questions} questions`, 'info');
        }

        onError(data) {
            this.addLog(`ERROR: ${data.message}`, 'error');
        }

        addLog(msg, level = 'info') {
            const el = document.getElementById('live-log-content');
            if (!el) return;
            const entry = document.createElement('div');
            entry.className = `log-entry ${level}`;
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            el.appendChild(entry);
            el.scrollTop = el.scrollHeight;
        }

        clearLog() {
            const el = document.getElementById('live-log-content');
            if (el) el.innerHTML = '<div class="log-entry">Waiting...</div>';
        }

        handleEvent(event) {
            const handlers = {
                'init': this.onInit,
                'upload': this.onUpload,
                'pass_start': this.onPassStart,
                'pass_complete': this.onPassComplete,
                'voting_start': this.onVotingStart,
                'voting_result': this.onVotingResult,
                'tiebreaker_start': this.onTiebreakerStart,
                'tiebreaker_round': this.onTiebreakerRound,
                'tiebreaker_complete': this.onTiebreakerComplete,
                'force_resolve': this.onForceResolve,
                'final_score': this.onFinalScore,
                'log': (d) => this.addLog(d.message, d.level),
                'error': this.onError
            };
            const handler = handlers[event.event];
            if (handler) handler.call(this, event.data);
        }
    }

    const progressHandler = new ProgressHandler();

    // ==========================================================================
    // LocalStorage
    // ==========================================================================
    function saveResultsToStorage() {
        if (!state.results) return;
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                results: state.results,
                metadata: state.metadata,
                filename: state.filename,
                mode: state.mode,
                savedAt: new Date().toISOString()
            }));
        } catch (e) { console.warn('Save failed:', e); }
    }

    function loadResultsFromStorage() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const data = JSON.parse(saved);
                const hours = (new Date() - new Date(data.savedAt)) / 3600000;
                if (hours < 24 && data.results?.length > 0) return data;
                localStorage.removeItem(STORAGE_KEY);
            }
        } catch (e) { console.warn('Load failed:', e); }
        return null;
    }

    function clearSavedResults() {
        localStorage.removeItem(STORAGE_KEY);
    }

    // ==========================================================================
    // Theme
    // ==========================================================================
    function initTheme() {
        const saved = localStorage.getItem('llmri-theme');
        if (saved) document.documentElement.setAttribute('data-theme', saved);
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const newTheme = current === 'dark' ? 'light' : current === 'light' ? 'dark' : prefersDark ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('llmri-theme', newTheme);
    }

    // ==========================================================================
    // File Upload
    // ==========================================================================
    function handleFileSelect(file) {
        if (!file) return clearFile();
        if (file.type !== 'application/pdf') return showError('Please upload a PDF file.');
        if (file.size > 20 * 1024 * 1024) return showError('File must be under 20MB.');
        state.file = file;
        elements.uploadContent.classList.add('hidden');
        elements.filePreview.classList.remove('hidden');
        elements.fileName.textContent = file.name;
        elements.fileSize.textContent = formatFileSize(file.size);
        elements.uploadZone.classList.add('has-file');
        elements.analyzeButton.disabled = false;
        hideError();
    }

    function clearFile() {
        state.file = null;
        elements.fileInput.value = '';
        elements.uploadContent.classList.remove('hidden');
        elements.filePreview.classList.add('hidden');
        elements.uploadZone.classList.remove('has-file');
        elements.analyzeButton.disabled = true;
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(2) + ' MB';
    }

    // ==========================================================================
    // Drag & Drop
    // ==========================================================================
    function initDragAndDrop() {
        const zone = elements.uploadZone;
        const input = elements.fileInput;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => {
            document.body.addEventListener(e, ev => { ev.preventDefault(); ev.stopPropagation(); }, false);
        });
        
        zone.addEventListener('dragenter', () => zone.classList.add('dragging'), false);
        zone.addEventListener('dragover', () => zone.classList.add('dragging'), false);
        zone.addEventListener('dragleave', e => {
            const r = zone.getBoundingClientRect();
            if (e.clientX < r.left || e.clientX >= r.right || e.clientY < r.top || e.clientY >= r.bottom)
                zone.classList.remove('dragging');
        }, false);
        zone.addEventListener('drop', e => {
            zone.classList.remove('dragging');
            if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
        }, false);
        input.addEventListener('drop', e => {
            zone.classList.remove('dragging');
            if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
        }, false);
    }

    // ==========================================================================
    // API - Streaming
    // ==========================================================================
    function analyzeWithStreaming(file, mode, onComplete, onError) {
        const formData = new FormData();
        formData.append('paper', file);
        formData.append('mode', mode);
        progressHandler.init(mode);

        fetch('/api/score-paper-stream', { method: 'POST', body: formData })
            .then(res => {
                if (!res.ok) {
                    // Parse JSON to get custom error message
                    return res.json().then(err => {
                        throw new Error(err.error || `HTTP ${res.status}`);
                    });
                }
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                function read() {
                    reader.read().then(({ done, value }) => {
                        if (done) return;
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop();
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const event = JSON.parse(line.slice(6));
                                    progressHandler.handleEvent(event);
                                    if (event.event === 'complete') onComplete(event.data);
                                    else if (event.event === 'error') onError(event.data.message);
                                } catch (e) { console.warn('Parse error:', e); }
                            }
                        }
                        read();
                    }).catch(e => onError(e.message));
                }
                read();
            })
            .catch(e => onError(e.message));
    }

    // ==========================================================================
    // API - Non-Streaming Fallback
    // ==========================================================================
    async function analyzeWithFetch(file, mode, onComplete, onError) {
        try {
            progressHandler.init(mode);
            progressHandler.updateProgress(30, 'Processing...');
            const formData = new FormData();
            formData.append('paper', file);
            formData.append('mode', mode);
            const res = await fetch('/api/score-paper', { method: 'POST', body: formData });
            const result = await res.json();
            if (!res.ok) throw new Error(result.error || `Error ${res.status}`);
            if (result.success) {
                progressHandler.updateProgress(100, 'Complete!');
                setTimeout(() => onComplete({ results: result.data, metadata: result.metadata, filename: result.filename, mode: result.mode }), 500);
            } else throw new Error(result.error);
        } catch (e) { onError(e.message); }
    }

    // ==========================================================================
    // Main Analyze
    // ==========================================================================
    function analyzeFile() {
        if (!state.file) return;
        elements.processing.classList.remove('hidden');
        elements.analyzeButton.disabled = true;
        elements.analyzeButton.innerHTML = '<div class="spinner" style="width:18px;height:18px;border-width:2px"></div><span>Analyzing...</span>';
        hideError();

        const mode = document.querySelector('input[name="mode"]:checked')?.value || 'standard';
        state.mode = mode;

        const onSuccess = (result) => {
            state.results = result.results;
            state.metadata = result.metadata;
            state.filename = result.filename || state.file?.name;
            state.mode = result.mode || mode;
            saveResultsToStorage();
            showResults();
            resetButton();
        };

        const onError = (msg) => {
            showError(msg);
            elements.processing.classList.add('hidden');
            resetButton();
        };

        if (USE_STREAMING) analyzeWithStreaming(state.file, mode, onSuccess, onError);
        else analyzeWithFetch(state.file, mode, onSuccess, onError);
    }

    function resetButton() {
        elements.analyzeButton.disabled = false;
        elements.analyzeButton.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 0 1 4 4v1a1 1 0 0 0 1 1h1a4 4 0 0 1 0 8h-1a1 1 0 0 0-1 1v1a4 4 0 0 1-8 0v-1a1 1 0 0 0-1-1H6a4 4 0 0 1 0-8h1a1 1 0 0 0 1-1V6a4 4 0 0 1 4-4z"/><circle cx="12" cy="12" r="2"/></svg><span>Analyze Paper</span>';
    }

    // ==========================================================================
    // Error
    // ==========================================================================
    function showError(msg) {
        elements.errorMessage.textContent = msg;
        elements.error.classList.remove('hidden');
    }
    
    function hideError() { 
        elements.error.classList.add('hidden'); 
    }

    // ==========================================================================
    // Results
    // ==========================================================================
    function showResults() {
        elements.heroSection.classList.add('hidden');
        elements.uploadSection.classList.add('hidden');
        elements.processing.classList.add('hidden');
        elements.resultsSection.classList.remove('hidden');

        const badge = document.getElementById('mode-badge');
        if (badge) {
            if (state.mode === 'high-accuracy') {
                badge.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> High Accuracy';
                badge.classList.remove('hidden');
            } else badge.classList.add('hidden');
        }

        renderPaperInfo();
        renderScoreOverview();
        renderSectionBars();
        renderDetailedResults();
        updateFilterCounts();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function hideResults() {
        elements.resultsSection.classList.add('hidden');
        elements.heroSection.classList.remove('hidden');
        elements.uploadSection.classList.remove('hidden');
        clearFile();
        state.results = state.metadata = state.filename = null;
        state.currentFilter = 'all';
        clearSavedResults();
        elements.filterButtons.forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
        document.getElementById('paper-info')?.remove();
    }

    function renderPaperInfo() {
        document.getElementById('paper-info')?.remove();
        const div = document.createElement('div');
        div.id = 'paper-info';
        div.className = 'paper-info';
        let title = 'Analyzed Paper', subtitle = state.filename || 'Unknown';
        if (state.metadata) {
            if (state.metadata.title) title = state.metadata.title;
            if (state.metadata.authors || state.metadata.year) {
                const p = [];
                if (state.metadata.authors) p.push(state.metadata.authors);
                if (state.metadata.year) p.push(`(${state.metadata.year})`);
                subtitle = p.join(' ');
            }
        }
        div.innerHTML = `<h2 class="paper-title">${escapeHtml(title)}</h2><p class="paper-subtitle">${escapeHtml(subtitle)}</p>`;
        document.querySelector('.results-nav')?.after(div);
    }

    function renderScoreOverview() {
        const { totalScore, maxScore, percentage } = calculateTotalScore();
        elements.scorePercent.textContent = `${percentage}%`;
        elements.scoreRaw.textContent = `${totalScore.toFixed(1)} / ${maxScore} points`;
        const circ = 2 * Math.PI * 70;
        elements.scoreRingFill.style.strokeDashoffset = circ - (percentage / 100) * circ;
        elements.scoreDescription.textContent = percentage >= 80 ? 'Excellent!' : percentage >= 60 ? 'Good with gaps.' : percentage >= 40 ? 'Needs attention.' : 'Missing details.';
    }

    function calculateTotalScore() {
        let total = 0, max = 0;
        state.results.forEach(i => {
            if (i.ai_score === 'N/A') return;
            const s = parseFloat(i.ai_score), m = parseFloat(i.Maximum_Score);
            if (!isNaN(s) && !isNaN(m)) { total += s; max += m; }
        });
        return { totalScore: total, maxScore: max, percentage: max > 0 ? Math.round(total / max * 100) : 0 };
    }

    function renderSectionBars() {
        const scores = {};
        state.results.forEach(i => {
            if (!scores[i.Section]) scores[i.Section] = { earned: 0, possible: 0 };
            if (i.ai_score !== 'N/A') {
                const s = parseFloat(i.ai_score), m = parseFloat(i.Maximum_Score);
                if (!isNaN(s) && !isNaN(m)) { scores[i.Section].earned += s; scores[i.Section].possible += m; }
            }
        });
        elements.sectionBars.innerHTML = SECTIONS_ORDER.filter(s => scores[s]).map(s => {
            const { earned, possible } = scores[s];
            const pct = possible > 0 ? Math.round(earned / possible * 100) : 0;
            return `<div class="section-bar"><div class="section-bar-header"><span class="section-bar-name">${s}</span><span class="section-bar-percent">${pct}%</span></div><div class="section-bar-track"><div class="section-bar-fill" style="width:${pct}%;background:${SECTION_COLORS[s]}"></div></div></div>`;
        }).join('');
    }

    function renderDetailedResults() {
        const filtered = filterResults(state.results, state.currentFilter);
        const grouped = groupResultsBySection(filtered);
        elements.resultsAccordion.innerHTML = SECTIONS_ORDER.filter(s => grouped[s]).map((s, i) => {
            const items = grouped[s], color = SECTION_COLORS[s];
            return `<div class="accordion-section ${i === 0 ? 'open' : ''}"><button class="accordion-header" onclick="this.parentElement.classList.toggle('open')"><div class="accordion-header-left"><span class="accordion-dot" style="background:${color}"></span><span class="accordion-title">${s}</span><span class="accordion-count">(${items.length})</span></div><svg class="accordion-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg></button><div class="accordion-content">${items.map(renderResultItem).join('')}</div></div>`;
        }).join('');
    }

    function filterResults(r, f) {
        if (f === 'issues') return r.filter(x => x.ai_score !== 'N/A' && parseFloat(x.ai_score) < parseFloat(x.Maximum_Score));
        if (f === 'na') return r.filter(x => x.ai_score === 'N/A');
        return r;
    }

    function groupResultsBySection(r) {
        return r.reduce((a, i) => { (a[i.Section] = a[i.Section] || []).push(i); return a; }, {});
    }

    function renderResultItem(item) {
        const cls = item.ai_score === 'N/A' ? 'na' : parseFloat(item.ai_score) === parseFloat(item.Maximum_Score) ? 'full' : parseFloat(item.ai_score) === 0 ? 'zero' : 'partial';
        return `<div class="result-item"><div class="result-item-header"><span class="result-item-number">Q${item.Question_Number}</span><span class="result-item-score result-item-score--${cls}">${item.ai_score === 'N/A' ? 'N/A' : `${item.ai_score}/${item.Maximum_Score}`}</span></div><p class="result-item-question">${escapeHtml(item.Question_Text)}</p><div class="result-item-evidence"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><p>${escapeHtml(item.evidence || 'No evidence.')}</p></div></div>`;
    }

    function updateFilterCounts() {
        const all = state.results.length;
        const issues = state.results.filter(r => r.ai_score !== 'N/A' && parseFloat(r.ai_score) < parseFloat(r.Maximum_Score)).length;
        const na = state.results.filter(r => r.ai_score === 'N/A').length;
        elements.countAll.textContent = `(${all})`;
        elements.countIssues.textContent = `(${issues})`;
        elements.countNa.textContent = `(${na})`;
    }

    function escapeHtml(t) { 
        const d = document.createElement('div'); 
        d.textContent = t; 
        return d.innerHTML; 
    }

    // ==========================================================================
    // Downloads
    // ==========================================================================
    function downloadCSV() {
        if (!state.results) return;
        const h = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence'];
        const csv = [h.join(','), ...state.results.map(r => h.map(k => { 
            const v = String(r[k] || ''); 
            return v.includes(',') || v.includes('\n') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v; 
        }).join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const a = document.createElement('a'); 
        a.href = URL.createObjectURL(blob); 
        a.download = `${(state.filename || 'paper').replace('.pdf', '')}_llmri.csv`; 
        a.click();
    }

    function downloadReport() {
        if (!state.results) return;
        const { totalScore, maxScore, percentage } = calculateTotalScore();
        const fn = state.filename || 'paper.pdf';
        let title = fn, authors = '';
        if (state.metadata) { 
            if (state.metadata.title) title = state.metadata.title; 
            if (state.metadata.authors) authors = state.metadata.authors + (state.metadata.year ? ` (${state.metadata.year})` : ''); 
        }
        
        const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>LLMRI Report - ${escapeHtml(title)}</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;max-width:900px;margin:0 auto;padding:40px 20px;background:#f8f9fa;color:#202124}.header{background:linear-gradient(135deg,#4285F4,#5e9eff);color:#fff;padding:40px;border-radius:12px;margin-bottom:30px}.header h1{font-size:24px;margin-bottom:8px}.score-card{background:#fff;padding:30px;border-radius:12px;margin-bottom:20px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.1)}.score-big{font-size:64px;font-weight:700;color:${percentage >= 60 ? '#34a853' : percentage >= 40 ? '#fbbc04' : '#ea4335'}}.section{background:#fff;padding:20px;border-radius:12px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,.1)}.section-title{font-weight:600;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e8eaed;display:flex;align-items:center;gap:12px}.section-dot{width:12px;height:12px;border-radius:50%}.item{padding:16px 0;border-bottom:1px solid #f1f3f4}.item:last-child{border-bottom:none}.item-header{display:flex;justify-content:space-between;margin-bottom:8px}.item-score{padding:4px 12px;border-radius:4px;font-size:12px;font-weight:600}.score-full{background:#e6f4ea;color:#34a853}.score-partial{background:#fef7e0;color:#f9ab00}.score-zero{background:#fce8e6;color:#ea4335}.score-na{background:#f1f3f4;color:#80868b}.evidence{font-size:13px;color:#5f6368;font-style:italic;margin-top:8px;padding:12px;background:#f8f9fa;border-radius:6px}.footer{text-align:center;margin-top:40px;color:#80868b;font-size:12px}</style></head><body><div class="header"><h1>LLMRI Report</h1>${title !== fn ? `<div style="font-size:18px;opacity:.95">${escapeHtml(title)}</div>` : ''}${authors ? `<div style="font-size:14px;opacity:.85">${escapeHtml(authors)}</div>` : ''}<p style="opacity:.9;margin-top:12px">${escapeHtml(fn)} • ${new Date().toLocaleDateString()}${state.mode === 'high-accuracy' ? ' • High Accuracy' : ''}</p></div><div class="score-card"><div class="score-big">${percentage}%</div><p style="color:#5f6368;margin-top:8px">COBIDAS Compliance</p><p style="color:#5f6368">${totalScore.toFixed(1)} / ${maxScore} points</p></div>${SECTIONS_ORDER.map(s => { 
            const items = state.results.filter(r => r.Section === s); 
            if (!items.length) return ''; 
            return `<div class="section"><div class="section-title"><span class="section-dot" style="background:${SECTION_COLORS[s]}"></span>${s}</div>${items.map(i => { 
                const cls = i.ai_score === 'N/A' ? 'score-na' : parseFloat(i.ai_score) === parseFloat(i.Maximum_Score) ? 'score-full' : parseFloat(i.ai_score) === 0 ? 'score-zero' : 'score-partial'; 
                return `<div class="item"><div class="item-header"><span>Q${i.Question_Number}: ${escapeHtml(i.Question_Text)}</span><span class="item-score ${cls}">${i.ai_score === 'N/A' ? 'N/A' : `${i.ai_score}/${i.Maximum_Score}`}</span></div><div class="evidence">${escapeHtml(i.evidence || 'No evidence.')}</div></div>`; 
            }).join('')}</div>`; 
        }).join('')}<div class="footer">Generated by LLMRI • Gemini 2.5 Pro • COBIDAS</div></body></html>`;
        
        const blob = new Blob([html], { type: 'text/html' });
        const a = document.createElement('a'); 
        a.href = URL.createObjectURL(blob); 
        a.download = `${fn.replace('.pdf', '')}_llmri_report.html`; 
        a.click();
    }

    // ==========================================================================
    // Events
    // ==========================================================================
    function initEventListeners() {
        elements.themeToggle.addEventListener('click', toggleTheme);
        
        // Logo click - reset page
        document.querySelector('.logo')?.addEventListener('click', e => {
            e.preventDefault();
            clearSavedResults();
            state = { file: null, results: null, metadata: null, filename: null, mode: 'standard', currentFilter: 'all' };
            elements.resultsSection.classList.add('hidden');
            elements.heroSection.classList.remove('hidden');
            elements.uploadSection.classList.remove('hidden');
            elements.processing.classList.add('hidden');
            hideError(); 
            clearFile();
            const radio = document.querySelector('input[name="mode"][value="standard"]');
            if (radio) radio.checked = true;
            elements.filterButtons.forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
            document.getElementById('paper-info')?.remove();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        elements.fileInput.addEventListener('change', e => handleFileSelect(e.target.files[0]));
        elements.fileRemove.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); clearFile(); });
        elements.uploadForm.addEventListener('submit', e => { e.preventDefault(); if (!state.file) return showError('Select a PDF.'); analyzeFile(); });
        elements.errorRetry.addEventListener('click', () => { hideError(); analyzeFile(); });
        elements.backButton.addEventListener('click', hideResults);
        elements.downloadCsv.addEventListener('click', downloadCSV);
        elements.downloadReport.addEventListener('click', downloadReport);
        elements.filterButtons.forEach(b => b.addEventListener('click', () => {
            state.currentFilter = b.dataset.filter;
            elements.filterButtons.forEach(x => x.classList.toggle('active', x === b));
            renderDetailedResults();
        }));
    }

    // ==========================================================================
    // Init
    // ==========================================================================
    function init() {
        initTheme();
        initDragAndDrop();
        initEventListeners();
        const saved = loadResultsFromStorage();
        if (saved) {
            state.results = saved.results;
            state.metadata = saved.metadata;
            state.filename = saved.filename;
            state.mode = saved.mode || 'standard';
            showResults();
        }
    }

    init();
});

// ============================================
// ADD THIS TO main.js
// Inside the DOMContentLoaded event listener, 
// add this code at the end (before the closing });
// ============================================

    // ==========================================================================
    // Feedback Modal
    // ==========================================================================
    const feedbackModal = document.getElementById('feedback-modal');
    const feedbackForm = document.getElementById('feedback-form');
    const feedbackSuccess = document.getElementById('feedback-success');
    const helpButton = document.getElementById('help-button');
    const feedbackClose = document.getElementById('feedback-close');

    // Open modal
    helpButton?.addEventListener('click', () => {
        feedbackModal.classList.remove('hidden');
        feedbackForm.classList.remove('hidden');
        feedbackSuccess.classList.add('hidden');
        feedbackForm.reset();
        // Set default date to today
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('feedback-date').value = today;
    });

    // Close modal
    feedbackClose?.addEventListener('click', () => {
        feedbackModal.classList.add('hidden');
    });

    // Close on overlay click
    feedbackModal?.addEventListener('click', (e) => {
        if (e.target === feedbackModal) {
            feedbackModal.classList.add('hidden');
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && feedbackModal && !feedbackModal.classList.contains('hidden')) {
            feedbackModal.classList.add('hidden');
        }
    });

    // Submit feedback
    feedbackForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = document.getElementById('feedback-submit');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Submitting...</span>';
        
        const data = {
            name: document.getElementById('feedback-name').value,
            email: document.getElementById('feedback-email').value,
            issue_date: document.getElementById('feedback-date').value,
            description: document.getElementById('feedback-description').value
        };
        
        try {
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                feedbackForm.classList.add('hidden');
                feedbackSuccess.classList.remove('hidden');
                
                // Auto-close after 3 seconds
                setTimeout(() => {
                    feedbackModal.classList.add('hidden');
                }, 3000);
            } else {
                alert(result.error || 'Failed to submit feedback. Please try again.');
            }
        } catch (error) {
            alert('Failed to submit feedback. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span>Submit Feedback</span>';
        }
    });