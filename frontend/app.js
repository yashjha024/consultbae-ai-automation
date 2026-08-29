document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navSubmit = document.getElementById('nav-submit');
    const navList = document.getElementById('nav-list');
    const viewSubmit = document.getElementById('view-submit');
    const viewList = document.getElementById('view-list');

    navSubmit.addEventListener('click', () => {
        navSubmit.classList.add('active');
        navList.classList.remove('active');
        viewSubmit.classList.add('active-view');
        viewList.classList.remove('active-view');
        viewList.classList.add('hidden');
        viewSubmit.classList.remove('hidden');
    });

    navList.addEventListener('click', () => {
        navList.classList.add('active');
        navSubmit.classList.remove('active');
        viewList.classList.add('active-view');
        viewSubmit.classList.remove('active-view');
        viewSubmit.classList.add('hidden');
        viewList.classList.remove('hidden');
        loadSubmissions();
    });

    // Audio Source Toggling
    const radioUpload = document.getElementById('mode-upload');
    const radioRecord = document.getElementById('mode-record');
    const secUpload = document.getElementById('section-upload');
    const secRecord = document.getElementById('section-record');

    radioUpload.addEventListener('change', () => {
        secUpload.classList.add('active-section');
        secRecord.classList.remove('active-section');
    });

    radioRecord.addEventListener('change', () => {
        secRecord.classList.add('active-section');
        secUpload.classList.remove('active-section');
    });

    // Recording Logic
    let mediaRecorder;
    let audioChunks = [];
    let recordedBlob = null;
    
    const btnRecord = document.getElementById('btn-record');
    const btnStop = document.getElementById('btn-stop');
    const recordPreview = document.getElementById('record-preview');

    btnRecord.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = () => {
                recordedBlob = new Blob(audioChunks, { type: 'audio/webm' }); // Browsers usually record webm/ogg
                const url = URL.createObjectURL(recordedBlob);
                recordPreview.src = url;
                recordPreview.classList.remove('hidden');
                
                // Stop all tracks to release mic
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            btnRecord.disabled = true;
            btnRecord.textContent = 'Recording...';
            btnStop.disabled = false;
            recordedBlob = null;
            recordPreview.classList.add('hidden');

        } catch (err) {
            showError('Microphone access denied or not available.');
            console.error(err);
        }
    });

    btnStop.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            btnRecord.disabled = false;
            btnRecord.textContent = 'Start Recording';
            btnStop.disabled = true;
        }
    });

    // Form Submission
    const form = document.getElementById('audio-form');
    const fileInput = document.getElementById('audio-file');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();
        hideSuccess();

        const name = document.getElementById('name').value.trim();
        const phone = document.getElementById('phone').value.trim();

        if (!name || !phone) {
            showError('Name and phone are required.');
            return;
        }

        const formData = new FormData();
        formData.append('name', name);
        formData.append('phone', phone);

        if (radioUpload.checked) {
            if (!fileInput.files[0]) {
                showError('Please select an audio file to upload.');
                return;
            }
            formData.append('audio', fileInput.files[0]);
        } else {
            if (!recordedBlob) {
                showError('Please record audio first.');
                return;
            }
            // Append as webm file
            formData.append('audio', recordedBlob, `recording_${Date.now()}.webm`);
        }

        const btnSubmit = document.getElementById('btn-submit');
        const originalText = btnSubmit.textContent;
        btnSubmit.textContent = 'Submitting...';
        btnSubmit.disabled = true;

        try {
            const res = await fetch('/audio', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.error || 'Submission failed');
            }

            if (data.analysis_error) {
                showSuccess('Audio submitted, but analysis failed: ' + data.analysis_error);
            } else {
                showSuccess('Audio submitted successfully!');
            }
            
            // Reset form
            form.reset();
            recordedBlob = null;
            recordPreview.classList.add('hidden');
            recordPreview.src = '';
            
        } catch (err) {
            showError(err.message);
        } finally {
            btnSubmit.textContent = originalText;
            btnSubmit.disabled = false;
        }
    });

    function showError(msg) {
        const el = document.getElementById('form-error');
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    function hideError() {
        document.getElementById('form-error').classList.add('hidden');
    }

    function showSuccess(msg) {
        const el = document.getElementById('form-success');
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    function hideSuccess() {
        document.getElementById('form-success').classList.add('hidden');
    }

    // Load Submissions
    async function loadSubmissions() {
        const tbody = document.getElementById('submissions-body');
        const emptyMsg = document.getElementById('list-empty');
        
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Loading...</td></tr>';
        
        try {
            const res = await fetch('/submissions');
            if (!res.ok) throw new Error('Failed to fetch');
            const data = await res.json();
            
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                emptyMsg.classList.remove('hidden');
                document.getElementById('submissions-table').classList.add('hidden');
                return;
            }
            
            emptyMsg.classList.add('hidden');
            document.getElementById('submissions-table').classList.remove('hidden');
            
            data.forEach(sub => {
                const tr = document.createElement('tr');
                
                // Format values
                const dur = sub.duration_seconds ? sub.duration_seconds.toFixed(1) + 's' : 'N/A';
                const sr = sub.sample_rate_khz ? sub.sample_rate_khz.toFixed(1) : 'N/A';
                const br = sub.bitrate_kbps ? sub.bitrate_kbps.toFixed(0) : 'N/A';
                const loud = sub.loudness_dbfs ? sub.loudness_dbfs.toFixed(1) : 'N/A';
                
                // Get filename from stored_path
                let filename = sub.stored_path.split(/[\/\\]/).pop();
                
                let playbackCell = `<audio controls src="/uploads/${filename}"></audio>`;
                if (sub.analysis_error && sub.analysis_error.includes('unsupported format')) {
                    playbackCell = `<em>Unsupported format</em>`;
                }

                tr.innerHTML = `
                    <td><strong>${escapeHtml(sub.canonical_name)}</strong></td>
                    <td>${dur}</td>
                    <td>${sr}</td>
                    <td>${br}</td>
                    <td>${loud}</td>
                    <td>${playbackCell}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (err) {
            console.error(err);
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: #ef4444;">Error loading submissions</td></tr>';
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
