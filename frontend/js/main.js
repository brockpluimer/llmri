/**
 * LLMRI - LLM Research Methodology Inspector
 * Main JavaScript Application
 */

document.addEventListener('DOMContentLoaded', () => {
    // ==========================================================================
    // DOM Elements
    // ==========================================================================
    const elements = {
        // Theme
        themeToggle: document.getElementById('theme-toggle'),
        
        // Sections
        heroSection: document.getElementById('hero-section'),
        uploadSection: document.getElementById('upload-section'),
        resultsSection: document.getElementById('results-section'),
        
        // Upload
        uploadForm: document.getElementById('upload-form'),
        uploadZone: document.getElementById('upload-zone'),
        uploadContent: document.getElementById('upload-content'),
        fileInput: document.getElementById('paper-file'),
        filePreview: document.getElementById('file-preview'),
        fileName: document.getElementById('file-name'),
        fileSize: document.getElementById('file-size'),
        fileRemove: document.getElementById('file-remove'),
        analyzeButton: document.getElementById('analyze-button'),
        
        // Processing
        processing: document.getElementById('processing'),
        
        // Error
        error: document.getElementById('error'),
        errorMessage: document.getElementById('error-message'),
        errorRetry: document.getElementById('error-retry'),
        
        // Results
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
        
        // Paper info (will be created dynamically)
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
    
    const SECTION_COLORS = {
        'Experimental Design Reporting': '#4285F4',
        'Acquisition Reporting': '#34a853',
        'Preprocessing Reporting': '#ea4335',
        'Statistical Modeling & Inference': '#fbbc04',
        'Results Reporting': '#9334e6',
        'Data Sharing': '#ff6d01',
        'Reproducibility': '#00acc1'
    };

    const SECTIONS_ORDER = [
        'Experimental Design Reporting',
        'Acquisition Reporting',
        'Preprocessing Reporting',
        'Statistical Modeling & Inference',
        'Results Reporting',
        'Data Sharing',
        'Reproducibility'
    ];

    // ==========================================================================
    // LocalStorage Persistence
    // ==========================================================================
    function saveResultsToStorage() {
        if (state.results) {
            const dataToSave = {
                results: state.results,
                metadata: state.metadata,
                filename: state.filename,
                mode: state.mode,
                savedAt: new Date().toISOString()
            };
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(dataToSave));
                console.log('Results saved to localStorage');
            } catch (e) {
                console.warn('Could not save to localStorage:', e);
            }
        }
    }

    function loadResultsFromStorage() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const data = JSON.parse(saved);
                // Check if data is less than 24 hours old
                const savedAt = new Date(data.savedAt);
                const now = new Date();
                const hoursSinceSave = (now - savedAt) / (1000 * 60 * 60);
                
                if (hoursSinceSave < 24 && data.results && data.results.length > 0) {
                    return data;
                } else {
                    // Clear stale data
                    localStorage.removeItem(STORAGE_KEY);
                }
            }
        } catch (e) {
            console.warn('Could not load from localStorage:', e);
        }
        return null;
    }

    function clearSavedResults() {
        localStorage.removeItem(STORAGE_KEY);
        console.log('Cleared saved results');
    }

    // ==========================================================================
    // Theme Management
    // ==========================================================================
    function initTheme() {
        const savedTheme = localStorage.getItem('llmri-theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
        }
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        let newTheme;
        if (currentTheme === 'dark') {
            newTheme = 'light';
        } else if (currentTheme === 'light') {
            newTheme = 'dark';
        } else {
            // No explicit theme set, toggle from system preference
            newTheme = prefersDark ? 'light' : 'dark';
        }
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('llmri-theme', newTheme);
    }

    // ==========================================================================
    // File Upload
    // ==========================================================================
    function handleFileSelect(file) {
        if (!file) {
            clearFile();
            return;
        }

        if (file.type !== 'application/pdf') {
            showError('Please upload a PDF file.');
            return;
        }

        if (file.size > 20 * 1024 * 1024) {
            showError('File size must be less than 20MB.');
            return;
        }

        state.file = file;
        
        // Update UI
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
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // ==========================================================================
    // Drag and Drop (FIXED)
    // ==========================================================================
    function initDragAndDrop() {
        const zone = elements.uploadZone;
        const input = elements.fileInput;
        
        // Prevent default drag behaviors on the whole document
        // This stops the browser from opening the file
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.body.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        // Handle drag enter/over on zone for visual feedback
        zone.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.add('dragging');
        }, false);
        
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.add('dragging');
        }, false);

        // Handle drag leave - check if actually leaving the zone
        zone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const rect = zone.getBoundingClientRect();
            const x = e.clientX;
            const y = e.clientY;
            if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom) {
                zone.classList.remove('dragging');
            }
        }, false);

        // Handle drop on zone
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('dragging');
            
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleFileSelect(files[0]);
            }
        }, false);
        
        // Also handle drop on the file input itself
        input.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('dragging');
            
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleFileSelect(files[0]);
            }
        }, false);
        
        // Handle dragover/dragenter on input
        input.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
        
        input.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.add('dragging');
        }, false);
    }

    // ==========================================================================
    // Processing Status
    // ==========================================================================
    function updateProcessingStep(step) {
        const steps = ['uploading', 'processing', 'analyzing', 'complete'];
        const currentIndex = steps.indexOf(step);

        document.querySelectorAll('.step').forEach((el, index) => {
            el.classList.remove('active', 'complete');
            if (index < currentIndex) {
                el.classList.add('complete');
            } else if (index === currentIndex) {
                el.classList.add('active');
            }
        });
    }

    // ==========================================================================
    // API Call
    // ==========================================================================
    async function analyzeFile() {
        if (!state.file) return;

        // Show processing state
        elements.processing.classList.remove('hidden');
        elements.analyzeButton.disabled = true;
        elements.analyzeButton.innerHTML = `
            <div class="spinner" style="width: 18px; height: 18px; border-width: 2px;"></div>
            <span>Analyzing...</span>
        `;
        hideError();

        // Get selected mode
        const selectedMode = document.querySelector('input[name="mode"]:checked')?.value || 'standard';
        state.mode = selectedMode;
        
        // Update processing hint based on mode
        const processingHint = document.getElementById('processing-hint');
        if (processingHint) {
            if (selectedMode === 'high-accuracy') {
                processingHint.textContent = 'This typically takes 5-8 minutes with multiple analysis passes';
            } else {
                processingHint.textContent = 'This typically takes 1-3 minutes depending on paper length';
            }
        }

        try {
            updateProcessingStep('uploading');

            const formData = new FormData();
            formData.append('paper', state.file);
            formData.append('mode', selectedMode);

            updateProcessingStep('processing');

            const response = await fetch('/api/score-paper', {
                method: 'POST',
                body: formData
            });

            updateProcessingStep('analyzing');

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `Server error: ${response.status}`);
            }

            if (result.success && result.data) {
                updateProcessingStep('complete');
                
                // Brief delay to show complete state
                await new Promise(resolve => setTimeout(resolve, 500));
                
                state.results = result.data;
                state.metadata = result.metadata || null;
                state.filename = result.filename || state.file?.name;
                state.mode = result.mode || selectedMode;
                
                // Save to localStorage
                saveResultsToStorage();
                
                showResults();
            } else {
                throw new Error(result.error || 'Unknown error occurred');
            }

        } catch (error) {
            console.error('Analysis error:', error);
            showError(error.message);
            elements.processing.classList.add('hidden');
        } finally {
            elements.analyzeButton.disabled = false;
            elements.analyzeButton.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2a4 4 0 0 1 4 4v1a1 1 0 0 0 1 1h1a4 4 0 0 1 0 8h-1a1 1 0 0 0-1 1v1a4 4 0 0 1-8 0v-1a1 1 0 0 0-1-1H6a4 4 0 0 1 0-8h1a1 1 0 0 0 1-1V6a4 4 0 0 1 4-4z"/>
                    <circle cx="12" cy="12" r="2"/>
                </svg>
                <span>Analyze Paper</span>
            `;
        }
    }

    // ==========================================================================
    // Error Handling
    // ==========================================================================
    function showError(message) {
        elements.errorMessage.textContent = message;
        elements.error.classList.remove('hidden');
    }

    function hideError() {
        elements.error.classList.add('hidden');
    }

    // ==========================================================================
    // Results Display
    // ==========================================================================
    function showResults() {
        elements.heroSection.classList.add('hidden');
        elements.uploadSection.classList.add('hidden');
        elements.processing.classList.add('hidden');
        elements.resultsSection.classList.remove('hidden');

        // Show mode badge
        const modeBadge = document.getElementById('mode-badge');
        if (modeBadge && state.mode) {
            if (state.mode === 'high-accuracy') {
                modeBadge.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                    High Accuracy Mode
                `;
                modeBadge.classList.remove('hidden');
            } else {
                modeBadge.classList.add('hidden');
            }
        }

        renderPaperInfo();
        renderScoreOverview();
        renderSectionBars();
        renderDetailedResults();
        updateFilterCounts();

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function hideResults() {
        elements.resultsSection.classList.add('hidden');
        elements.heroSection.classList.remove('hidden');
        elements.uploadSection.classList.remove('hidden');
        
        // Reset state
        clearFile();
        state.results = null;
        state.metadata = null;
        state.filename = null;
        state.currentFilter = 'all';
        
        // Clear saved results
        clearSavedResults();
        
        // Reset filter buttons
        elements.filterButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === 'all');
        });
        
        // Remove paper info if it exists
        const existingPaperInfo = document.getElementById('paper-info');
        if (existingPaperInfo) {
            existingPaperInfo.remove();
        }
    }

    function renderPaperInfo() {
        // Remove existing paper info
        const existingPaperInfo = document.getElementById('paper-info');
        if (existingPaperInfo) {
            existingPaperInfo.remove();
        }
        
        // Create paper info section
        const paperInfoDiv = document.createElement('div');
        paperInfoDiv.id = 'paper-info';
        paperInfoDiv.className = 'paper-info';
        
        let title = 'Analyzed Paper';
        let subtitle = state.filename || 'Unknown file';
        
        if (state.metadata) {
            if (state.metadata.title) {
                title = state.metadata.title;
            }
            if (state.metadata.authors || state.metadata.year) {
                const parts = [];
                if (state.metadata.authors) parts.push(state.metadata.authors);
                if (state.metadata.year) parts.push(`(${state.metadata.year})`);
                subtitle = parts.join(' ');
            }
        }
        
        paperInfoDiv.innerHTML = `
            <h2 class="paper-title">${escapeHtml(title)}</h2>
            <p class="paper-subtitle">${escapeHtml(subtitle)}</p>
        `;
        
        // Insert after results-nav
        const resultsNav = document.querySelector('.results-nav');
        if (resultsNav) {
            resultsNav.after(paperInfoDiv);
        }
    }

    function renderScoreOverview() {
        const { totalScore, maxScore, percentage } = calculateTotalScore();

        // Update percentage display
        elements.scorePercent.textContent = `${percentage}%`;
        elements.scoreRaw.textContent = `${totalScore.toFixed(1)} / ${maxScore} points`;

        // Update ring
        const circumference = 2 * Math.PI * 70; // r = 70
        const offset = circumference - (percentage / 100) * circumference;
        elements.scoreRingFill.style.strokeDashoffset = offset;

        // Update description
        let description;
        if (percentage >= 80) {
            description = 'Excellent reporting completeness!';
        } else if (percentage >= 60) {
            description = 'Good reporting with some gaps.';
        } else if (percentage >= 40) {
            description = 'Several reporting items need attention.';
        } else {
            description = 'Significant methodological details are missing.';
        }
        elements.scoreDescription.textContent = description;
    }

    function calculateTotalScore() {
        let totalScore = 0;
        let maxScore = 0;

        state.results.forEach(item => {
            if (item.ai_score === 'N/A') return;

            const score = parseFloat(item.ai_score);
            const max = parseFloat(item.Maximum_Score);

            if (!isNaN(score) && !isNaN(max)) {
                totalScore += score;
                maxScore += max;
            }
        });

        const percentage = maxScore > 0 ? Math.round((totalScore / maxScore) * 100) : 0;

        return { totalScore, maxScore, percentage };
    }

    function renderSectionBars() {
        const sectionScores = {};

        // Calculate scores per section
        state.results.forEach(item => {
            const section = item.Section;
            if (!sectionScores[section]) {
                sectionScores[section] = { earned: 0, possible: 0 };
            }

            if (item.ai_score !== 'N/A') {
                const score = parseFloat(item.ai_score);
                const max = parseFloat(item.Maximum_Score);
                if (!isNaN(score) && !isNaN(max)) {
                    sectionScores[section].earned += score;
                    sectionScores[section].possible += max;
                }
            }
        });

        // Render bars
        elements.sectionBars.innerHTML = SECTIONS_ORDER
            .filter(section => sectionScores[section])
            .map(section => {
                const { earned, possible } = sectionScores[section];
                const percent = possible > 0 ? Math.round((earned / possible) * 100) : 0;
                const color = SECTION_COLORS[section] || '#4285F4';

                return `
                    <div class="section-bar">
                        <div class="section-bar-header">
                            <span class="section-bar-name">${section}</span>
                            <span class="section-bar-percent">${percent}%</span>
                        </div>
                        <div class="section-bar-track">
                            <div class="section-bar-fill" style="width: ${percent}%; background-color: ${color};"></div>
                        </div>
                    </div>
                `;
            }).join('');
    }

    function renderDetailedResults() {
        const filteredResults = filterResults(state.results, state.currentFilter);
        const groupedResults = groupResultsBySection(filteredResults);

        elements.resultsAccordion.innerHTML = SECTIONS_ORDER
            .filter(section => groupedResults[section])
            .map((section, index) => {
                const items = groupedResults[section];
                const color = SECTION_COLORS[section] || '#4285F4';
                const isOpen = index === 0;

                return `
                    <div class="accordion-section ${isOpen ? 'open' : ''}">
                        <button class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
                            <div class="accordion-header-left">
                                <span class="accordion-dot" style="background-color: ${color};"></span>
                                <span class="accordion-title">${section}</span>
                                <span class="accordion-count">(${items.length} items)</span>
                            </div>
                            <svg class="accordion-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </button>
                        <div class="accordion-content">
                            ${items.map(item => renderResultItem(item)).join('')}
                        </div>
                    </div>
                `;
            }).join('');
    }

    function filterResults(results, filter) {
        switch (filter) {
            case 'issues':
                return results.filter(r => {
                    if (r.ai_score === 'N/A') return false;
                    return parseFloat(r.ai_score) < parseFloat(r.Maximum_Score);
                });
            case 'na':
                return results.filter(r => r.ai_score === 'N/A');
            default:
                return results;
        }
    }

    function groupResultsBySection(results) {
        return results.reduce((acc, item) => {
            const section = item.Section;
            if (!acc[section]) acc[section] = [];
            acc[section].push(item);
            return acc;
        }, {});
    }

    function renderResultItem(item) {
        const scoreClass = getScoreClass(item);
        const scoreDisplay = item.ai_score === 'N/A' 
            ? 'N/A' 
            : `${item.ai_score}/${item.Maximum_Score}`;

        return `
            <div class="result-item">
                <div class="result-item-header">
                    <span class="result-item-number">Q${item.Question_Number}</span>
                    <span class="result-item-score ${scoreClass}">${scoreDisplay}</span>
                </div>
                <p class="result-item-question">${escapeHtml(item.Question_Text)}</p>
                <div class="result-item-evidence">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                    <p>${escapeHtml(item.evidence || 'No evidence provided.')}</p>
                </div>
            </div>
        `;
    }

    function getScoreClass(item) {
        if (item.ai_score === 'N/A') return 'result-item-score--na';
        
        const score = parseFloat(item.ai_score);
        const max = parseFloat(item.Maximum_Score);
        
        if (score === max) return 'result-item-score--full';
        if (score === 0) return 'result-item-score--zero';
        return 'result-item-score--partial';
    }

    function updateFilterCounts() {
        const all = state.results.length;
        const issues = state.results.filter(r => {
            if (r.ai_score === 'N/A') return false;
            return parseFloat(r.ai_score) < parseFloat(r.Maximum_Score);
        }).length;
        const na = state.results.filter(r => r.ai_score === 'N/A').length;

        elements.countAll.textContent = `(${all})`;
        elements.countIssues.textContent = `(${issues})`;
        elements.countNa.textContent = `(${na})`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==========================================================================
    // Download Functions
    // ==========================================================================
    function downloadCSV() {
        if (!state.results) return;

        const headers = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence'];
        const csvContent = [
            headers.join(','),
            ...state.results.map(row =>
                headers.map(h => {
                    const value = row[h] || '';
                    const str = String(value);
                    if (str.includes(',') || str.includes('\n') || str.includes('"')) {
                        return `"${str.replace(/"/g, '""')}"`;
                    }
                    return str;
                }).join(',')
            )
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${state.filename?.replace('.pdf', '') || 'paper'}_llmri_assessment.csv`;
        link.click();
    }

    function downloadReport() {
        if (!state.results) return;

        const { totalScore, maxScore, percentage } = calculateTotalScore();
        const fileName = state.filename || 'paper.pdf';
        
        // Get paper title/authors for report
        let paperTitle = fileName;
        let paperAuthors = '';
        if (state.metadata) {
            if (state.metadata.title) paperTitle = state.metadata.title;
            if (state.metadata.authors) {
                paperAuthors = state.metadata.authors;
                if (state.metadata.year) paperAuthors += ` (${state.metadata.year})`;
            }
        }

        const reportHTML = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LLMRI Assessment Report - ${escapeHtml(paperTitle)}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 40px 20px; background: #f8f9fa; color: #202124; }
        .header { background: linear-gradient(135deg, #4285F4 0%, #5e9eff 100%); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; }
        .header h1 { font-size: 24px; margin-bottom: 8px; }
        .header .paper-title { font-size: 18px; opacity: 0.95; margin-bottom: 4px; }
        .header .paper-authors { font-size: 14px; opacity: 0.85; }
        .header p { opacity: 0.9; font-size: 14px; margin-top: 12px; }
        .score-card { background: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }
        .score-big { font-size: 64px; font-weight: bold; color: ${percentage >= 60 ? '#34a853' : percentage >= 40 ? '#fbbc04' : '#ea4335'}; }
        .score-detail { color: #5f6368; margin-top: 8px; }
        .section { background: white; padding: 20px; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .section-title { font-weight: 600; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e8eaed; display: flex; align-items: center; gap: 12px; }
        .section-dot { width: 12px; height: 12px; border-radius: 50%; }
        .item { padding: 16px 0; border-bottom: 1px solid #f1f3f4; }
        .item:last-child { border-bottom: none; padding-bottom: 0; }
        .item-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .item-question { font-size: 14px; font-weight: 500; flex: 1; }
        .item-score { padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .score-full { background: #e6f4ea; color: #34a853; }
        .score-partial { background: #fef7e0; color: #f9ab00; }
        .score-zero { background: #fce8e6; color: #ea4335; }
        .score-na { background: #f1f3f4; color: #80868b; }
        .evidence { font-size: 13px; color: #5f6368; font-style: italic; margin-top: 8px; padding: 12px; background: #f8f9fa; border-radius: 6px; }
        .footer { text-align: center; margin-top: 40px; color: #80868b; font-size: 12px; }
        .disclaimer { background: #fff3cd; border: 1px solid #ffc107; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 13px; color: #856404; }
    </style>
</head>
<body>
    <div class="header">
        <h1>LLMRI Assessment Report</h1>
        ${paperTitle !== fileName ? `<div class="paper-title">${escapeHtml(paperTitle)}</div>` : ''}
        ${paperAuthors ? `<div class="paper-authors">${escapeHtml(paperAuthors)}</div>` : ''}
        <p>${escapeHtml(fileName)} • Generated ${new Date().toLocaleDateString()}</p>
    </div>
    
    <div class="disclaimer">
        ⚠️ Note: AI-generated assessments may vary slightly between analyses. This report should be used as a guide, not a definitive evaluation.
    </div>
    
    <div class="score-card">
        <div class="score-big">${percentage}%</div>
        <p class="score-detail">Overall COBIDAS Compliance Score</p>
        <p class="score-detail">${totalScore.toFixed(1)} out of ${maxScore} applicable points</p>
    </div>

    ${SECTIONS_ORDER.map(section => {
        const items = state.results.filter(r => r.Section === section);
        if (items.length === 0) return '';
        const color = SECTION_COLORS[section] || '#4285F4';
        return `
            <div class="section">
                <div class="section-title">
                    <span class="section-dot" style="background-color: ${color};"></span>
                    ${section}
                </div>
                ${items.map(item => {
                    const scoreClass = item.ai_score === 'N/A' ? 'score-na' :
                        parseFloat(item.ai_score) === parseFloat(item.Maximum_Score) ? 'score-full' :
                        parseFloat(item.ai_score) === 0 ? 'score-zero' : 'score-partial';
                    return `
                        <div class="item">
                            <div class="item-header">
                                <span class="item-question">Q${item.Question_Number}: ${escapeHtml(item.Question_Text)}</span>
                                <span class="item-score ${scoreClass}">${item.ai_score === 'N/A' ? 'N/A' : `${item.ai_score}/${item.Maximum_Score}`}</span>
                            </div>
                            <div class="evidence">${escapeHtml(item.evidence || 'No evidence provided.')}</div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }).join('')}

    <div class="footer">
        Generated by LLMRI • Powered by Gemini 2.5 • Based on COBIDAS Guidelines
    </div>
</body>
</html>
        `;

        const blob = new Blob([reportHTML], { type: 'text/html;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${fileName.replace('.pdf', '')}_llmri_report.html`;
        link.click();
    }

    // ==========================================================================
    // Event Listeners
    // ==========================================================================
    function initEventListeners() {
        // Theme toggle
        elements.themeToggle.addEventListener('click', toggleTheme);

        // File input
        elements.fileInput.addEventListener('change', (e) => {
            handleFileSelect(e.target.files[0]);
        });

        // File remove
        elements.fileRemove.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            clearFile();
        });

        // Form submit - prevent default and use our own validation
        elements.uploadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Check if we have a file in state (works for both click and drag-drop)
            if (!state.file) {
                showError('Please select a PDF file to analyze.');
                return;
            }
            
            analyzeFile();
        });

        // Error retry
        elements.errorRetry.addEventListener('click', () => {
            hideError();
            analyzeFile();
        });

        // Back button
        elements.backButton.addEventListener('click', hideResults);

        // Download buttons
        elements.downloadCsv.addEventListener('click', downloadCSV);
        elements.downloadReport.addEventListener('click', downloadReport);

        // Filter buttons
        elements.filterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                state.currentFilter = btn.dataset.filter;
                elements.filterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderDetailedResults();
            });
        });
    }

    // ==========================================================================
    // Initialize
    // ==========================================================================
    function init() {
        initTheme();
        initDragAndDrop();
        initEventListeners();
        
        // Check for saved results
        const savedData = loadResultsFromStorage();
        if (savedData) {
            state.results = savedData.results;
            state.metadata = savedData.metadata;
            state.filename = savedData.filename;
            state.mode = savedData.mode || 'standard';
            showResults();
        }
    }

    init();
});