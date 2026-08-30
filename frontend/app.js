document.addEventListener('DOMContentLoaded', () => {
    // --- Navigation & Routing ---
    const navSubmit = document.getElementById('nav-submit');
    const navList = document.getElementById('nav-list');
    const viewSubmit = document.getElementById('view-submit');
    const viewList = document.getElementById('view-list');

    function switchView(view) {
        if (view === 'submit') {
            navSubmit.classList.add('active');
            navList.classList.remove('active');
            viewList.classList.add('hidden');
            viewSubmit.classList.remove('hidden');
        } else {
            navList.classList.add('active');
            navSubmit.classList.remove('active');
            viewSubmit.classList.add('hidden');
            viewList.classList.remove('hidden');
            loadSubmissions();
        }
    }

    navSubmit.addEventListener('click', () => switchView('submit'));
    navList.addEventListener('click', () => switchView('list'));

    // --- Audio Source Toggling ---
    const modeRadios = document.querySelectorAll('.mode-radio');
    const labels = [document.getElementById('label-record'), document.getElementById('label-upload')];
    const secUpload = document.getElementById('section-upload');
    const secRecord = document.getElementById('section-record');

    modeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            labels.forEach(l => l.classList.remove('active'));
            e.target.parentElement.classList.add('active');

            if (e.target.value === 'upload') {
                secUpload.classList.remove('hidden');
                secRecord.classList.add('hidden');
            } else {
                secRecord.classList.remove('hidden');
                secUpload.classList.add('hidden');
            }
        });
    });

    // --- Upload UX ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('audio-file');
    const fileSelectedState = document.getElementById('file-selected-state');
    const selectedFilename = document.getElementById('selected-filename');
    const btnRemoveFile = document.getElementById('btn-remove-file');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--c-primary)';
        dropZone.style.backgroundColor = '#FAFAFA';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = '';
        dropZone.style.backgroundColor = '';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '';
        dropZone.style.backgroundColor = '';
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            updateFileState();
        }
    });

    fileInput.addEventListener('change', updateFileState);

    function updateFileState() {
        if (fileInput.files.length > 0) {
            dropZone.classList.add('hidden');
            fileSelectedState.classList.remove('hidden');
            selectedFilename.textContent = fileInput.files[0].name;
        } else {
            dropZone.classList.remove('hidden');
            fileSelectedState.classList.add('hidden');
        }
    }

    btnRemoveFile.addEventListener('click', () => {
        fileInput.value = '';
        updateFileState();
    });

    // --- Record UX ---
    let audioChunks = [];
    let recordedBlob = null;
    let timerInterval;
    let secondsElapsed = 0;
    let recordingStream;
    let audioContext;
    let audioSource;
    let audioProcessor;

    const stateReady = document.getElementById('record-ready');
    const stateActive = document.getElementById('record-active');
    const statePreview = document.getElementById('record-preview-state');

    const btnRecord = document.getElementById('btn-record');
    const btnStop = document.getElementById('btn-stop');
    const btnReRecord = document.getElementById('btn-re-record');
    const recordTimer = document.getElementById('record-timer');
    const recordPreviewAudio = document.getElementById('record-preview-audio');

    function formatTime(sec) {
        const m = Math.floor(sec / 60).toString().padStart(2, '0');
        const s = (sec % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }

    btnRecord.addEventListener('click', async () => {
        try {
            recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            audioSource = audioContext.createMediaStreamSource(recordingStream);
            // ScriptProcessor has broad browser support and lets this small static app
            // emit PCM WAV, which the local backend can analyze without ffmpeg.
            audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);
            audioProcessor.onaudioprocess = event => {
                audioChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
            };
            audioSource.connect(audioProcessor);
            audioProcessor.connect(audioContext.destination);

            // UI transitions
            stateReady.classList.add('hidden');
            stateActive.classList.remove('hidden');

            // Timer logic
            secondsElapsed = 0;
            recordTimer.textContent = '00:00';
            clearInterval(timerInterval);
            timerInterval = setInterval(() => {
                secondsElapsed++;
                recordTimer.textContent = formatTime(secondsElapsed);
            }, 1000);

        } catch (err) {
            showError('Microphone access denied or not available.');
            console.error(err);
        }
    });

    btnStop.addEventListener('click', async () => {
        if (audioProcessor) {
            clearInterval(timerInterval);
            audioProcessor.disconnect();
            audioSource.disconnect();
            recordingStream.getTracks().forEach(track => track.stop());
            const sampleRate = audioContext.sampleRate;
            await audioContext.close();
            audioProcessor = null;
            audioSource = null;
            recordingStream = null;
            recordedBlob = encodeWav(audioChunks, sampleRate);
            recordPreviewAudio.src = URL.createObjectURL(recordedBlob);
            stateActive.classList.add('hidden');
            statePreview.classList.remove('hidden');
        }
    });

    function encodeWav(chunks, sampleRate) {
        const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
        const data = new ArrayBuffer(44 + length * 2);
        const view = new DataView(data);
        const write = (offset, value) => view.setUint32(offset, value, true);
        view.setUint32(0, 0x46464952, false); // RIFF
        write(4, 36 + length * 2);
        view.setUint32(8, 0x45564157, false); // WAVE
        view.setUint32(12, 0x20746d66, false); // fmt
        write(16, 16); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
        write(24, sampleRate); write(28, sampleRate * 2);
        view.setUint16(32, 2, true); view.setUint16(34, 16, true);
        view.setUint32(36, 0x64617461, false); // data
        write(40, length * 2);
        let offset = 44;
        chunks.forEach(chunk => chunk.forEach(sample => {
            const clamped = Math.max(-1, Math.min(1, sample));
            view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
            offset += 2;
        }));
        return new Blob([data], { type: 'audio/wav' });
    }

    btnReRecord.addEventListener('click', () => {
        recordedBlob = null;
        recordPreviewAudio.src = '';
        statePreview.classList.add('hidden');
        stateReady.classList.remove('hidden');
    });

    // --- Form Submission ---
    const form = document.getElementById('audio-form');
    const btnSubmit = document.getElementById('btn-submit');
    const successState = document.getElementById('success-state');
    const formError = document.getElementById('form-error');
    const formErrorMsg = document.getElementById('form-error-msg');

    document.getElementById('btn-submit-another').addEventListener('click', () => {
        successState.classList.add('hidden');
        form.classList.remove('hidden');
        form.reset();

        // Reset file upload
        fileInput.value = '';
        updateFileState();

        // Reset recording
        recordedBlob = null;
        recordPreviewAudio.src = '';
        statePreview.classList.add('hidden');
        stateActive.classList.add('hidden');
        stateReady.classList.remove('hidden');
    });

    document.getElementById('btn-view-subs').addEventListener('click', () => {
        switchView('list');
    });

    function showError(msg) {
        formErrorMsg.textContent = msg;
        formError.classList.remove('hidden');
        // Scroll to error
        formError.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function hideError() {
        formError.classList.add('hidden');
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const name = document.getElementById('name').value.trim();
        const phone = document.getElementById('phone').value.trim();

        if (!name || !phone) {
            showError('Full name and phone number are required.');
            return;
        }

        const formData = new FormData();
        formData.append('name', name);
        formData.append('phone', phone);

        const mode = document.querySelector('.mode-radio:checked').value;
        if (mode === 'upload') {
            if (!fileInput.files[0]) {
                showError('Please select an audio file to upload.');
                return;
            }
            formData.append('audio', fileInput.files[0]);
        } else {
            if (!recordedBlob) {
                showError('Please record audio before submitting.');
                return;
            }
            formData.append('audio', recordedBlob, `recording_${Date.now()}.wav`);
        }

        const originalText = btnSubmit.innerHTML;
        btnSubmit.innerHTML = `<div class="spinner" style="width: 1.25rem; height: 1.25rem; border-width: 2px; border-top-color: white; margin: 0; display: inline-block;"></div> Submitting...`;
        btnSubmit.disabled = true;

        try {
            const res = await fetch('/audio', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || 'Submission failed on server');
            }

            // Success Transition
            form.classList.add('hidden');
            successState.classList.remove('hidden');

            if (data.analysis_error) {
                document.getElementById('success-msg').textContent = 'Saved securely, but analysis failed: ' + data.analysis_error;
            } else {
                document.getElementById('success-msg').textContent = 'Your audio response has been saved securely.';
            }

        } catch (err) {
            showError(err.message);
        } finally {
            btnSubmit.innerHTML = originalText;
            btnSubmit.disabled = false;
        }
    });

    // --- Load Submissions Dashboard ---
    const btnRefresh = document.getElementById('btn-refresh-list');
    btnRefresh.addEventListener('click', loadSubmissions);

    function getInitials(name) {
        if (!name) return '?';
        return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    }

    async function loadSubmissions() {
        const grid = document.getElementById('submissions-grid');
        const emptyState = document.getElementById('submissions-empty');
        const loadingState = document.getElementById('submissions-loading');

        loadingState.classList.remove('hidden');
        grid.classList.add('hidden');
        emptyState.classList.add('hidden');

        try {
            const res = await fetch('/submissions');
            if (!res.ok) throw new Error('Failed to fetch data');
            const data = await res.json();

            grid.innerHTML = '';

            if (data.length === 0) {
                loadingState.classList.add('hidden');
                emptyState.classList.remove('hidden');
                return;
            }

            loadingState.classList.add('hidden');
            grid.classList.remove('hidden');

            data.forEach(sub => {
                const card = document.createElement('div');
                card.className = 'review-card';

                const dur = Number.isFinite(sub.duration_seconds) ? sub.duration_seconds.toFixed(1) + 's' : '--';
                const sr = Number.isFinite(sub.sample_rate_khz) ? sub.sample_rate_khz.toFixed(1) + ' kHz' : '--';
                const br = Number.isFinite(sub.bitrate_kbps) ? sub.bitrate_kbps.toFixed(0) + ' kbps' : '--';
                const loud = Number.isFinite(sub.loudness_dbfs) ? sub.loudness_dbfs.toFixed(1) + ' dBFS' : '--';

                let filename = sub.stored_path.split(/[\/\\]/).pop();

                let playerHTML = `<audio controls class="native-audio-player" src="/uploads/${filename}" preload="metadata"></audio>`;
                if (sub.analysis_error && sub.analysis_error.includes('unsupported format')) {
                    playerHTML = `<div class="error-badge">Unsupported Format</div>`;
                }

                card.innerHTML = `
                    <div class="review-card-identity">
                        <div class="avatar">${getInitials(sub.canonical_name)}</div>
                        <div>
                            <div class="identity-name">${escapeHtml(sub.canonical_name)}</div>
                            <div class="identity-meta">ID: ${sub.person_id}</div>
                        </div>
                    </div>

                    <div class="review-card-stats">
                        <div class="stat-item">
                            <span class="stat-label">Duration</span>
                            <span class="stat-value">${dur}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Sample Rate</span>
                            <span class="stat-value">${sr}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Bitrate</span>
                            <span class="stat-value">${br}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Loudness</span>
                            <span class="stat-value">${loud}</span>
                        </div>
                    </div>

                    <div class="review-card-player">
                        ${playerHTML}
                    </div>
                `;
                grid.appendChild(card);
            });
        } catch (err) {
            console.error(err);
            loadingState.innerHTML = `<p class="text-red-500">Failed to load submissions. Please try again.</p>`;
        }
    }

    function escapeHtml(unsafe) {
        return (unsafe || '').toString()
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
});
