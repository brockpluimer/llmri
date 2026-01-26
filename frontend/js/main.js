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
        filterButtons: document.querySelectorAll('.filter-button')
    };

    // ==========================================================================
    // State
    // ==========================================================================
    let state = {
        file: null,
        results: null,
        currentFilter: 'all'
    };

    // ==========================================================================
    // Constants
    // ==========================================================================
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
    // Drag and Drop
    // ==========================================================================
    function initDragAndDrop() {
        const zone = elements.uploadZone;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
            zone.addEventListener(event, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        ['dragenter', 'dragover'].forEach(event => {
            zone.addEventListener(event, () => {
                zone.classList.add('dragging');
            });
        });

        ['dragleave', 'drop'].forEach(event => {
            zone.addEventListener(event, () => {
                zone.classList.remove('dragging');
            });
        });

        zone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
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

        try {
            updateProcessingStep('uploading');

            const formData = new FormData();
            formData.append('paper', state.file);

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
        state.currentFilter = 'all';
        
        // Reset filter buttons
        elements.filterButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === 'all');
        });
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
            const aiScore = item.ai_score;
            if (aiScore !== 'N/A') {
                const score = parseFloat(aiScore);
                const max = parseFloat(item.Maximum_Score);
                if (!isNaN(score)) totalScore += score;
                if (!isNaN(max)) maxScore += max;
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
                if (!isNaN(score)) sectionScores[section].earned += score;
                if (!isNaN(max)) sectionScores[section].possible += max;
            }
        });

        // Render bars
        elements.sectionBars.innerHTML = SECTIONS_ORDER
            .filter(section => sectionScores[section]?.possible > 0)
            .map(section => {
                const data = sectionScores[section];
                const percentage = Math.round((data.earned / data.possible) * 100);
                const color = SECTION_COLORS[section] || '#4285F4';

                return `
                    <div class="section-bar">
                        <div class="section-bar-header">
                            <span class="section-bar-name">${section}</span>
                            <span class="section-bar-percent">${percentage}%</span>
                        </div>
                        <div class="section-bar-track">
                            <div class="section-bar-fill" style="width: ${percentage}%; background-color: ${color};"></div>
                        </div>
                    </div>
                `;
            }).join('');
    }

    function renderDetailedResults() {
        const filteredResults = filterResults(state.results, state.currentFilter);
        const grouped = groupBySection(filteredResults);

        elements.resultsAccordion.innerHTML = SECTIONS_ORDER
            .filter(section => grouped[section]?.length > 0)
            .map(section => {
                const items = grouped[section];
                const color = SECTION_COLORS[section] || '#4285F4';

                return `
                    <div class="accordion-section">
                        <button class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
                            <div class="accordion-header-left">
                                <div class="accordion-dot" style="background-color: ${color};"></div>
                                <span class="accordion-title">${section}</span>
                                <span class="accordion-count">(${items.length} items)</span>
                            </div>
                            <svg class="accordion-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </button>
                        <div class="accordion-content">
                            ${items.map((item, index) => renderResultItem(item, index)).join('')}
                        </div>
                    </div>
                `;
            }).join('');
    }

    function renderResultItem(item, index) {
        const scoreClass = getScoreClass(item.ai_score, item.Maximum_Score);
        const scoreDisplay = item.ai_score === 'N/A' ? 'N/A' : `${item.ai_score}/${item.Maximum_Score}`;

        return `
            <div class="result-item" style="animation-delay: ${index * 30}ms;">
                <div class="result-item-header">
                    <span class="result-item-number">Q${item.Question_Number}</span>
                    <span class="result-item-score ${scoreClass}">${scoreDisplay}</span>
                </div>
                <p class="result-item-question">${item.Question_Text}</p>
                <div class="result-item-evidence">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="16" x2="12" y2="12"/>
                        <line x1="12" y1="8" x2="12.01" y2="8"/>
                    </svg>
                    <p>${escapeHtml(item.evidence || 'No evidence provided.')}</p>
                </div>
            </div>
        `;
    }

    function getScoreClass(aiScore, maxScore) {
        if (aiScore === 'N/A') return 'result-item-score--na';
        const score = parseFloat(aiScore);
        const max = parseFloat(maxScore);
        if (score === max) return 'result-item-score--full';
        if (score === 0) return 'result-item-score--zero';
        return 'result-item-score--partial';
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

    function groupBySection(results) {
        const grouped = {};
        results.forEach(item => {
            const section = item.Section;
            if (!grouped[section]) grouped[section] = [];
            grouped[section].push(item);
        });
        return grouped;
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
        link.download = `${state.file?.name.replace('.pdf', '') || 'paper'}_llmri_assessment.csv`;
        link.click();
    }

    function downloadReport() {
        if (!state.results) return;

        const { totalScore, maxScore, percentage } = calculateTotalScore();
        const fileName = state.file?.name || 'paper.pdf';

        const reportHTML = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LLMRI Assessment Report - ${fileName}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 40px 20px; background: #f8f9fa; color: #202124; }
        .header { background: linear-gradient(135deg, #4285F4 0%, #5e9eff 100%); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; }
        .header h1 { font-size: 24px; margin-bottom: 8px; }
        .header p { opacity: 0.9; font-size: 14px; }
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
    </style>
</head>
<body>
    <div class="header">
        <h1>LLMRI Assessment Report</h1>
        <p>${fileName} • Generated ${new Date().toLocaleDateString()}</p>
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

        // Form submit
        elements.uploadForm.addEventListener('submit', (e) => {
            e.preventDefault();
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
    }

    init();
});
