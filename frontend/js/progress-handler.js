/**
 * Progress UI Handler for LLMRI
 * Handles Server-Sent Events for real-time progress updates
 */

// Add this to your main.js or include as separate file

class ProgressHandler {
    constructor(elements) {
        this.elements = elements;
        this.mode = 'standard';
        this.totalPasses = 7;
        this.currentPass = 0;
    }

    init(mode) {
        this.mode = mode;
        this.currentPass = 0;
        
        // Update mode badge
        const modeBadge = document.querySelector('.mode-badge');
        if (modeBadge) {
            modeBadge.className = `mode-badge mode-badge--${mode === 'high-accuracy' ? 'high-accuracy' : 'standard'}`;
            modeBadge.textContent = mode === 'high-accuracy' ? 'High Accuracy Mode' : 'Standard Mode';
        }

        // Show/hide high accuracy panel
        const haPanel = document.getElementById('high-accuracy-panel');
        if (haPanel) {
            haPanel.classList.toggle('hidden', mode !== 'high-accuracy');
        }

        // Initialize passes grid for high accuracy
        if (mode === 'high-accuracy') {
            this.initPassesGrid();
        }

        // Update hint text
        const hint = document.getElementById('processing-hint');
        if (hint) {
            hint.textContent = mode === 'high-accuracy' 
                ? 'High-accuracy mode runs 7 analysis passes. This typically takes 10-15 minutes.'
                : 'This typically takes 1-3 minutes depending on paper length.';
        }

        // Clear log
        this.clearLog();
    }

    initPassesGrid() {
        const grid = document.getElementById('passes-grid');
        if (!grid) return;

        const temperatures = [0.0, 0.05, 0.1, 0.15, 0.1, 0.05, 0.0];
        grid.innerHTML = '';

        for (let i = 0; i < this.totalPasses; i++) {
            const pass = document.createElement('div');
            pass.className = 'pass-item';
            pass.id = `pass-${i + 1}`;
            pass.innerHTML = `<span>${i + 1}</span>`;
            pass.title = `Temperature: ${temperatures[i]}`;
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
        const steps = document.querySelectorAll('.step');
        const stepOrder = ['uploading', 'processing', 'analyzing', 'complete'];
        const currentIndex = stepOrder.indexOf(step);

        steps.forEach((el, index) => {
            el.classList.remove('active', 'complete');
            if (index < currentIndex) {
                el.classList.add('complete');
            } else if (index === currentIndex) {
                el.classList.add('active');
            }
        });
    }

    updateActivity(text) {
        const activity = document.querySelector('#activity-current .activity-text');
        if (activity) {
            activity.textContent = text;
        }
    }

    // High Accuracy specific updates
    onPassStart(data) {
        this.currentPass = data.pass;
        
        // Update pass item
        const passEl = document.getElementById(`pass-${data.pass}`);
        if (passEl) {
            passEl.className = 'pass-item active';
        }

        // Update activity
        this.updateActivity(`Running Pass ${data.pass}/${data.total} (temp: ${data.temperature})`);

        // Update progress
        const baseProgress = 10; // Upload takes ~10%
        const passProgress = (data.pass - 1) / data.total * 60; // Passes take 60%
        this.updateProgress(baseProgress + passProgress, `Pass ${data.pass} of ${data.total}`);

        this.addLog(`Pass ${data.pass}/${data.total} started (temperature=${data.temperature})`, 'info');
    }

    onPassComplete(data) {
        const passEl = document.getElementById(`pass-${data.pass}`);
        if (passEl) {
            passEl.className = 'pass-item complete';
        }

        if (data.failed) {
            this.addLog(`Pass ${data.pass} FAILED`, 'error');
        } else {
            this.addLog(`Pass ${data.pass} complete: ${data.questions_scored} questions scored`, 'success');
        }

        // Update progress
        const baseProgress = 10;
        const passProgress = data.pass / data.total * 60;
        this.updateProgress(baseProgress + passProgress, `Pass ${data.pass} of ${data.total} complete`);
    }

    onVotingStart() {
        this.updateActivity('Computing majority vote...');
        this.updateProgress(75, 'Analyzing votes...');
        this.addLog('Computing majority vote across all passes...', 'info');
    }

    onVotingResult(data) {
        // Show vote stats panel
        const voteStats = document.getElementById('vote-stats');
        if (voteStats) {
            voteStats.classList.remove('hidden');
        }

        // Update stat values
        document.getElementById('stat-unanimous').textContent = data.unanimous;
        document.getElementById('stat-strong').textContent = data.strong;
        document.getElementById('stat-weak').textContent = data.weak;
        document.getElementById('stat-unresolved').textContent = data.unresolved;

        this.updateActivity(`Vote complete: ${data.unresolved} questions need tie-breaker`);
        this.addLog(`Vote results: ${data.unanimous} unanimous, ${data.strong} strong, ${data.weak} weak, ${data.unresolved} unresolved`, 'info');

        if (data.unresolved === 0) {
            this.updateProgress(95, 'Building final results...');
        }
    }

    onTiebreakerStart(data) {
        // Show tiebreaker section
        const tbSection = document.getElementById('tiebreaker-section');
        if (tbSection) {
            tbSection.classList.remove('hidden');
        }

        // Update count
        const countEl = document.getElementById('tiebreaker-count');
        if (countEl) {
            countEl.textContent = data.questions.length;
        }

        // Initialize rounds
        const roundsEl = document.getElementById('tiebreaker-rounds');
        if (roundsEl) {
            roundsEl.innerHTML = '';
            for (let i = 0; i < data.total_rounds; i++) {
                const round = document.createElement('div');
                round.className = 'tiebreaker-round';
                round.id = `tb-round-${i + 1}`;
                round.textContent = i + 1;
                roundsEl.appendChild(round);
            }
        }

        this.updateActivity(`Running tie-breakers for ${data.questions.length} questions...`);
        this.addLog(`Starting tie-breakers for questions: ${data.questions.join(', ')}`, 'warning');
    }

    onTiebreakerRound(data) {
        const roundEl = document.getElementById(`tb-round-${data.round}`);
        if (roundEl) {
            roundEl.className = 'tiebreaker-round active';
        }

        this.updateActivity(`Tie-breaker round ${data.round}/${data.total} (${data.questions} questions)`);
        this.updateProgress(80 + (data.round / data.total) * 10, `Tie-breaker round ${data.round}`);
    }

    onTiebreakerComplete(data) {
        const roundEl = document.getElementById(`tb-round-${data.round}`);
        if (roundEl) {
            roundEl.className = 'tiebreaker-round complete';
        }

        this.addLog(`Tie-breaker round ${data.round}: resolved ${data.resolved}, remaining ${data.remaining}`, 
            data.remaining > 0 ? 'warning' : 'success');
    }

    onForceResolve(data) {
        this.addLog(`Force-resolving ${data.questions.length} questions: ${data.questions.join(', ')}`, 'warning');
        this.updateActivity(`Force-resolving ${data.questions.length} ambiguous questions...`);
    }

    onFinalScore(data) {
        this.updateProgress(100, 'Analysis complete!');
        this.updateActivity(`Final score: ${data.percentage}%`);
        this.addLog(`FINAL SCORE: ${data.raw_score}/${data.max_score} = ${data.percentage}%`, 'success');
        this.addLog(`Questions marked N/A: ${data.na_count}`, 'info');
    }

    onUpload(data) {
        if (data.status === 'uploading') {
            this.updateStep('uploading');
            this.updateProgress(5, 'Uploading PDF...');
            this.updateActivity('Uploading PDF to Gemini...');
        } else if (data.status === 'complete') {
            this.updateStep('processing');
            this.updateProgress(10, 'PDF uploaded');
            this.addLog(`PDF uploaded successfully (method: ${data.method})`, 'success');
        }
    }

    onInit(data) {
        this.totalPasses = data.passes || 7;
        this.addLog(`Initialized: ${data.passes} passes, ${data.questions} questions`, 'info');
    }

    onError(data) {
        this.addLog(`ERROR: ${data.message}`, 'error');
        this.updateActivity(`Error: ${data.message}`);
    }

    // Logging
    addLog(message, level = 'info') {
        const logContent = document.getElementById('live-log-content');
        if (!logContent) return;

        const entry = document.createElement('div');
        entry.className = `log-entry ${level}`;
        
        const time = new Date().toLocaleTimeString();
        entry.textContent = `[${time}] ${message}`;
        
        logContent.appendChild(entry);
        logContent.scrollTop = logContent.scrollHeight;
    }

    clearLog() {
        const logContent = document.getElementById('live-log-content');
        if (logContent) {
            logContent.innerHTML = '<div class="log-entry">Waiting for analysis to start...</div>';
        }
    }

    // Main event handler
    handleEvent(event) {
        const { event: eventType, data } = event;

        switch (eventType) {
            case 'init':
                this.onInit(data);
                break;
            case 'upload':
                this.onUpload(data);
                break;
            case 'pass_start':
                this.onPassStart(data);
                break;
            case 'pass_complete':
                this.onPassComplete(data);
                break;
            case 'voting_start':
                this.onVotingStart();
                break;
            case 'voting_result':
                this.onVotingResult(data);
                break;
            case 'tiebreaker_start':
                this.onTiebreakerStart(data);
                break;
            case 'tiebreaker_round':
                this.onTiebreakerRound(data);
                break;
            case 'tiebreaker_complete':
                this.onTiebreakerComplete(data);
                break;
            case 'force_resolve':
                this.onForceResolve(data);
                break;
            case 'final_score':
                this.onFinalScore(data);
                break;
            case 'log':
                this.addLog(data.message, data.level);
                break;
            case 'error':
                this.onError(data);
                break;
        }
    }
}

// SSE Connection handler
function analyzeWithStreaming(file, mode, progressHandler, onComplete, onError) {
    const formData = new FormData();
    formData.append('paper', file);
    formData.append('mode', mode);

    // Initialize progress UI
    progressHandler.init(mode);

    // For SSE, we need to use fetch with ReadableStream or EventSource
    // Since we're POSTing, we'll use fetch
    fetch('/api/score-paper-stream', {
        method: 'POST',
        body: formData
    }).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                
                // Process complete events
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            progressHandler.handleEvent(event);

                            if (event.event === 'complete') {
                                onComplete(event.data);
                            } else if (event.event === 'error') {
                                onError(event.data.message);
                            }
                        } catch (e) {
                            console.warn('Failed to parse SSE event:', line, e);
                        }
                    }
                }

                read();
            }).catch(error => {
                onError(error.message);
            });
        }

        read();
    }).catch(error => {
        onError(error.message);
    });
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ProgressHandler, analyzeWithStreaming };
}