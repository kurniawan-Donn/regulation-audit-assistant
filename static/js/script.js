(function() {
    // ====== STATE ======
    const state = {
        currentResultId: null,
        currentData: null,
        filter: 'all',
        searchQuery: '',
        theme: localStorage.getItem('rta_theme') || 'light',
        history: JSON.parse(localStorage.getItem('rta_history') || '[]'),
        isAnalyzing: false,
    };

    // ====== DOM REFS ======
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const form = $('#uploadForm');
    const statusEl = $('#status');
    const submitBtn = $('#submitBtn');
    const resultSection = $('#resultSection');
    const resultBody = $('#resultBody');
    const summaryRow = $('#summaryRow');
    const chunkErrorsBox = $('#chunkErrorsBox');
    const exportBtn = $('#exportBtn');
    const copyBtn = $('#copyBtn');
    const clearResultBtn = $('#clearResultBtn');
    const resetBtn = $('#resetBtn');
    const fileInput = $('#fileInput');
    const uploadZone = $('#uploadZone');
    const fileNameDisplay = $('#fileNameDisplay');
    const searchInput = $('#searchInput');
    const filterBtns = $$('.filter-btn');
    const emptyState = $('#emptyState');
    const progressContainer = $('#progressContainer');
    const progressBar = $('#progressBar');
    const progressText = $('#progressText');
    const chartContainer = $('#chartContainer');
    const donutChart = $('#donutChart');
    const donutInner = $('#donutInner');
    const chartLegend = $('#chartLegend');
    const themeToggle = $('#themeToggle');
    const themeLabel = $('#themeLabel');
    const historyToggle = $('#historyToggle');
    const historyPanel = $('#historyPanel');
    const historyOverlay = $('#historyOverlay');
    const historyClose = $('#historyClose');
    const historyList = $('#historyList');
    const historyClearAll = $('#historyClearAll');
    const toastContainer = $('#toastContainer');

    // ====== THEME ======
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        state.theme = theme;
        localStorage.setItem('rta_theme', theme);
        const icon = theme === 'dark' ? 'fa-sun' : 'fa-moon';
        const label = theme === 'dark' ? 'Light' : 'Dark';
        themeToggle.innerHTML = `<i class="fas ${icon}"></i> <span id="themeLabel">${label}</span>`;
        updateDonutChart();
    }
    themeToggle.addEventListener('click', () => {
        applyTheme(state.theme === 'dark' ? 'light' : 'dark');
    });
    applyTheme(state.theme);

    // ====== TOAST ======
    function showToast(message, type = 'info') {
        const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i> ${message}`;
        toastContainer.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    // ====== HISTORY PANEL ======
    function openHistory() {
        historyPanel.classList.add('open');
        historyOverlay.classList.add('visible');
        renderHistory();
    }
    function closeHistory() {
        historyPanel.classList.remove('open');
        historyOverlay.classList.remove('visible');
    }
    historyToggle.addEventListener('click', openHistory);
    historyClose.addEventListener('click', closeHistory);
    historyOverlay.addEventListener('click', closeHistory);

    function saveToHistory(data) {
        const entry = {
            id: data.result_id || Date.now().toString(36),
            nama: data.nama_regulasi || 'Tanpa Nama',
            tanggal: new Date().toISOString(),
            total_ketentuan: data.total_ketentuan || 0,
            total_valid: data.total_valid || 0,
            total_flagged: data.total_flagged || 0,
            results: data.results || [],
            chunk_errors: data.chunk_errors || [],
        };
        state.history = state.history.filter(h => h.id !== entry.id);
        state.history.unshift(entry);
        if (state.history.length > 50) state.history = state.history.slice(0, 50);
        localStorage.setItem('rta_history', JSON.stringify(state.history));
        renderHistory();
    }

    function deleteHistoryItem(id) {
        state.history = state.history.filter(h => h.id !== id);
        localStorage.setItem('rta_history', JSON.stringify(state.history));
        renderHistory();
        showToast('Riwayat dihapus.', 'success');
    }

    function clearAllHistory() {
        if (state.history.length === 0) return;
        if (confirm('Hapus semua riwayat analisis?')) {
            state.history = [];
            localStorage.setItem('rta_history', JSON.stringify(state.history));
            renderHistory();
            showToast('Semua riwayat dihapus.', 'success');
        }
    }
    historyClearAll.addEventListener('click', clearAllHistory);

    function renderHistory() {
        if (state.history.length === 0) {
            historyList.innerHTML = `
                <div class="history-empty">
                    <i class="fas fa-folder-open"></i>
                    <p>Belum ada riwayat analisis.</p>
                </div>`;
            return;
        }
        historyList.innerHTML = state.history.map(h => `
            <div class="history-item" data-id="${h.id}">
                <div class="history-item-info" onclick="window.__loadHistory('${h.id}')">
                    <div class="history-item-name">${h.nama}</div>
                    <div class="history-item-meta">
                        <span><i class="fas fa-list"></i> ${h.total_ketentuan} ketentuan</span>
                        <span><i class="fas fa-check-circle" style="color:var(--done)"></i> ${h.total_valid}</span>
                        <span><i class="fas fa-exclamation-triangle" style="color:var(--warn)"></i> ${h.total_flagged}</span>
                        <span>${new Date(h.tanggal).toLocaleDateString('id-ID')}</span>
                    </div>
                </div>
                <button class="history-item-delete" onclick="window.__deleteHistory('${h.id}')" title="Hapus">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    }

    window.__deleteHistory = (id) => deleteHistoryItem(id);
    window.__loadHistory = (id) => {
        const entry = state.history.find(h => h.id === id);
        if (entry) {
            state.currentResultId = entry.id;
            state.currentData = entry;
            exportBtn.disabled = false;
            copyBtn.disabled = false;
            renderSummary(entry);
            renderChunkErrors(entry.chunk_errors || []);
            renderTable(entry.results || []);
            resultSection.classList.add('visible');
            resultSection.style.display = 'block';
            resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            closeHistory();
            showToast(`Dimuat dari riwayat: ${entry.nama}`, 'info');
            updateDonutChart();
        }
    };

    renderHistory();

    // ====== FILE UPLOAD DRAG & DROP ======
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            updateFileNameDisplay();
            setStatus(`File dipilih: ${e.dataTransfer.files[0].name}`, false);
        }
    });
    fileInput.addEventListener('change', updateFileNameDisplay);

    function updateFileNameDisplay() {
        if (fileInput.files.length) {
            fileNameDisplay.textContent = `📄 ${fileInput.files[0].name} (${formatFileSize(fileInput.files[0].size)})`;
            fileNameDisplay.style.display = 'block';
        } else {
            fileNameDisplay.textContent = '';
            fileNameDisplay.style.display = 'none';
        }
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // ====== SET STATUS ======
    function setStatus(text, isError) {
        statusEl.textContent = text;
        statusEl.className = isError === true ? 'error' : isError === false ? 'success' : '';
        if (isError === false) {
            statusEl.innerHTML = `<i class="fas fa-check-circle" style="color:var(--done)"></i> ${text}`;
        } else if (isError === true) {
            statusEl.innerHTML = `<i class="fas fa-exclamation-circle" style="color:var(--warn)"></i> ${text}`;
        }
    }

    function setProgress(percent, text) {
        progressContainer.style.display = 'block';
        progressBar.style.width = percent + '%';
        progressText.textContent = text || `${Math.round(percent)}%`;
        if (percent >= 100) {
            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressText.textContent = '';
            }, 1500);
        }
    }

    // ====== RENDER SUMMARY ======
    function renderSummary(data) {
        const total = data.total_ketentuan || 0;
        const valid = data.total_valid || 0;
        const flagged = data.total_flagged || 0;
        const chunks = data.total_chunks || 0;
        const batches = data.total_batches || 0;
        summaryRow.innerHTML = `
            <div class="stat"><strong>${total}</strong><span>Ketentuan Relevan</span></div>
            <div class="stat stat-valid"><strong>${valid}</strong><span>Valid</span></div>
            <div class="stat stat-flagged"><strong>${flagged}</strong><span>Perlu Ditinjau</span></div>
            <div class="stat"><strong>${chunks}</strong><span>Potongan Teks</span></div>
            <div class="stat"><strong>${batches}</strong><span>Pemanggilan API</span></div>
        `;
        updateDonutChart();
    }

    function updateDonutChart() {
        if (!state.currentData) return;
        const valid = state.currentData.total_valid || 0;
        const flagged = state.currentData.total_flagged || 0;
        const total = valid + flagged;
        if (total === 0) {
            chartContainer.style.display = 'none';
            return;
        }
        chartContainer.style.display = 'flex';
        const validPercent = Math.round((valid / total) * 100);
        const flaggedPercent = 100 - validPercent;
        donutChart.style.background = `conic-gradient(var(--done) 0% ${validPercent}%, var(--warn) ${validPercent}% 100%)`;
        donutInner.textContent = validPercent + '%';
        donutInner.style.color = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
        chartLegend.innerHTML = `
            <div class="chart-legend-item">
                <div class="chart-legend-dot valid"></div>
                <span>Valid: ${valid} (${validPercent}%)</span>
            </div>
            <div class="chart-legend-item">
                <div class="chart-legend-dot flagged"></div>
                <span>Perlu Ditinjau: ${flagged} (${flaggedPercent}%)</span>
            </div>
        `;
    }

    // ====== RENDER CHUNK ERRORS ======
    function renderChunkErrors(errors) {
        if (!errors || errors.length === 0) {
            chunkErrorsBox.style.display = 'none';
            return;
        }
        chunkErrorsBox.style.display = 'block';
        const lines = errors.map(e => {
            const ref = [e.bab, e.pasal, e.ayat].filter(Boolean).join(' - ') || '(referensi tidak diketahui)';
            const countInfo = e.affected_count > 1 ? ` (${e.affected_count} potongan)` : '';
            return `<li>${ref}${countInfo}: ${e.error}</li>`;
        }).join('');
        chunkErrorsBox.innerHTML = `<strong><i class="fas fa-triangle-exclamation"></i> ${errors.length} batch gagal dianalisis AI</strong> (bagian lain tetap ditampilkan):<ul>${lines}</ul>`;
    }

    // ====== RENDER TABLE ======
    function renderTable(results) {
        const filtered = applyFilter(results || []);
        if (filtered.length === 0) {
            resultBody.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }
        emptyState.style.display = 'none';
        resultBody.innerHTML = filtered.map((item, i) => {
            const isFlagged = !item.is_valid;
            const badge = isFlagged ? '<span class="badge flagged">Ditinjau</span>' : '<span class="badge valid">Valid</span>';
            const notes = (isFlagged && item.validation_notes && item.validation_notes.length) ? `<div class="notes">${item.validation_notes.join('; ')}</div>` : '';
            return `
                <tr class="${isFlagged ? 'flagged' : 'valid-row'}">
                    <td>${i + 1}</td>
                    <td>${escapeHtml(item.referensi_regulasi || '-')}</td>
                    <td>${escapeHtml(item.bab_pasal_ayat || '-')}</td>
                    <td>${escapeHtml(item.point_ketentuan || '')}</td>
                    <td>${escapeHtml(item.pemeriksaan || '')}</td>
                    <td>${badge}${notes}</td>
                    <td>
                        <div class="row-actions">
                            <button class="row-action-btn copy-row" title="Salin baris" data-index="${i}">
                                <i class="fas fa-copy"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        resultBody.querySelectorAll('.copy-row').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.index);
                const item = filtered[idx];
                if (item) {
                    const text = `Referensi: ${item.referensi_regulasi || '-'}\nBAB/Pasal/Ayat: ${item.bab_pasal_ayat || '-'}\nPoint: ${item.point_ketentuan}\nPemeriksaan: ${item.pemeriksaan}\nStatus: ${item.is_valid ? 'Valid' : 'Perlu Ditinjau'}`;
                    navigator.clipboard.writeText(text).then(() => {
                        showToast('Baris disalin ke clipboard.', 'success');
                    }).catch(() => showToast('Gagal menyalin.', 'error'));
                }
            });
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function applyFilter(results) {
        let filtered = [...results];
        if (state.filter === 'valid') {
            filtered = filtered.filter(r => r.is_valid);
        } else if (state.filter === 'flagged') {
            filtered = filtered.filter(r => !r.is_valid);
        }
        if (state.searchQuery) {
            const q = state.searchQuery.toLowerCase();
            filtered = filtered.filter(r =>
                (r.referensi_regulasi || '').toLowerCase().includes(q) ||
                (r.bab_pasal_ayat || '').toLowerCase().includes(q) ||
                (r.point_ketentuan || '').toLowerCase().includes(q) ||
                (r.pemeriksaan || '').toLowerCase().includes(q)
            );
        }
        return filtered;
    }

    // ====== FILTER & SEARCH ======
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.filter = btn.dataset.filter;
            if (state.currentData) renderTable(state.currentData.results || []);
        });
    });
    searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        if (state.currentData) renderTable(state.currentData.results || []);
    });

    // ====== EXPORT & COPY ======
    exportBtn.addEventListener('click', () => {
        if (state.currentResultId) {
            window.location.href = `/api/export/${state.currentResultId}`;
            showToast('Mengekspor ke Excel...', 'info');
        }
    });

    copyBtn.addEventListener('click', () => {
        if (!state.currentData || !state.currentData.results) return;
        const results = state.currentData.results;
        let text = `HASIL ANALISIS REGULASI\n`;
        text += `Nama: ${state.currentData.nama_regulasi || '-'}\n`;
        text += `Total: ${results.length} ketentuan\n`;
        text += `${'='.repeat(60)}\n\n`;
        results.forEach((r, i) => {
            text += `[${i + 1}] ${r.referensi_regulasi || '-'} | ${r.bab_pasal_ayat || '-'}\n`;
            text += `    Point: ${r.point_ketentuan}\n`;
            text += `    Pemeriksaan: ${r.pemeriksaan}\n`;
            text += `    Status: ${r.is_valid ? '✅ Valid' : '⚠️ Perlu Ditinjau'}\n`;
            if (r.validation_notes && r.validation_notes.length) {
                text += `    Catatan: ${r.validation_notes.join('; ')}\n`;
            }
            text += `\n`;
        });
        navigator.clipboard.writeText(text).then(() => {
            showToast('Seluruh hasil disalin ke clipboard.', 'success');
        }).catch(() => showToast('Gagal menyalin.', 'error'));
    });

    clearResultBtn.addEventListener('click', () => {
        resultSection.style.display = 'none';
        resultSection.classList.remove('visible');
        state.currentResultId = null;
        state.currentData = null;
        exportBtn.disabled = true;
        copyBtn.disabled = true;
        setStatus('Hasil ditutup. Silakan upload regulasi baru.', false);
        showToast('Hasil analisis ditutup.', 'info');
    });

    resetBtn.addEventListener('click', () => {
        fileInput.value = '';
        fileNameDisplay.textContent = '';
        fileNameDisplay.style.display = 'none';
        document.getElementById('namaRegulasi').value = '';
        state.currentResultId = null;
        state.currentData = null;
        resultSection.style.display = 'none';
        resultSection.classList.remove('visible');
        exportBtn.disabled = true;
        copyBtn.disabled = true;
        setStatus('Menunggu file...', false);
        showToast('Form dibersihkan.', 'info');
    });

    // ====== FORM SUBMIT ======
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!fileInput.files.length) {
            setStatus('Silakan pilih file terlebih dahulu.', true);
            showToast('Pilih file terlebih dahulu!', 'error');
            return;
        }

        const file = fileInput.files[0];
        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) {
            setStatus('File terlalu besar. Maksimal 10MB.', true);
            showToast('File terlalu besar! Maksimal 10MB.', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        const nama = document.getElementById('namaRegulasi').value.trim();
        if (nama) formData.append('nama_regulasi', nama);
        else formData.append('nama_regulasi', file.name.replace(/\.[^.]+$/, ''));

        state.isAnalyzing = true;
        submitBtn.disabled = true;
        resultSection.style.display = 'none';
        resultSection.classList.remove('visible');
        statusEl.innerHTML = '<span class="spinner"></span> Menganalisis regulasi...';
        setProgress(5, 'Mengunggah file...');

        try {
            let progressInterval = setInterval(() => {
                const currentWidth = parseFloat(progressBar.style.width || '5');
                if (currentWidth < 90) {
                    const increment = Math.random() * 8 + 2;
                    const newWidth = Math.min(currentWidth + increment, 90);
                    progressBar.style.width = newWidth + '%';
                    if (newWidth < 30) progressText.textContent = 'Mengunggah & memproses dokumen...';
                    else if (newWidth < 60) progressText.textContent = 'Menganalisis chunk dengan AI...';
                    else if (newWidth < 80) progressText.textContent = 'Menggabungkan hasil analisis...';
                    else progressText.textContent = 'Menyelesaikan...';
                }
            }, 800);

            const res = await fetch('/api/analyze', { method: 'POST', body: formData });
            const data = await res.json();

            clearInterval(progressInterval);
            setProgress(100, 'Selesai!');

            if (!res.ok) {
                setStatus(`Gagal: ${data.detail || 'Terjadi kesalahan pada server.'}`, true);
                showToast('Analisis gagal: ' + (data.detail || 'Server error'), 'error');
                submitBtn.disabled = false;
                state.isAnalyzing = false;
                return;
            }

            setStatus(`Selesai. ${data.total_ketentuan} ketentuan relevan ditemukan dari ${data.total_chunks} potongan teks (${data.total_batches} pemanggilan API).`, false);
            state.currentResultId = data.result_id;
            state.currentData = data;
            exportBtn.disabled = false;
            copyBtn.disabled = false;
            renderSummary(data);
            renderChunkErrors(data.chunk_errors);
            renderTable(data.results);
            resultSection.classList.add('visible');
            resultSection.style.display = 'block';
            resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            saveToHistory(data);
            showToast('Analisis selesai! 🎉', 'success');

        } catch (err) {
            clearInterval(progressInterval);
            setStatus(`Gagal terhubung ke server: ${err.message}`, true);
            showToast('Gagal terhubung ke server.', 'error');
        } finally {
            submitBtn.disabled = false;
            state.isAnalyzing = false;
            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressText.textContent = '';
                progressBar.style.width = '0%';
            }, 2000);
        }
    });

    // ====== KEYBOARD SHORTCUTS ======
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeHistory();
        }
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            searchInput.focus();
        }
    });

    // ====== INITIAL STATE ======
    setStatus('Menunggu file...', false);
    updateFileNameDisplay();

    console.log('🚀 Regulation to IT Audit Assistant - Enhanced UI loaded');
    console.log('💡 Tips: Gunakan Ctrl+K untuk fokus ke pencarian, Esc untuk tutup panel');
})();