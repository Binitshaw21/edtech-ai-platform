// =============================
// --- UI Elements ---
// =============================
const tabMic = document.getElementById('tabMic');
const tabFile = document.getElementById('tabFile');
const tabLink = document.getElementById('tabLink');

const sectionMic = document.getElementById('sectionMic');
const sectionFile = document.getElementById('sectionFile');
const sectionLink = document.getElementById('sectionLink');

const recordingStatus = document.getElementById('recordingStatus');
const processingStatus = document.getElementById('processingStatus');
const loadingText = document.getElementById('loadingText');

// =============================
// --- Tab Switching Logic ---
// =============================
function switchTab(activeTab, activeSection) {
    [tabMic, tabFile, tabLink].forEach(tab => {
        tab.classList.remove('bg-indigo-600', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
        tab.classList.add('bg-gray-800', 'text-gray-300');
    });

    [sectionMic, sectionFile, sectionLink].forEach(sec =>
        sec.classList.add('hidden')
    );

    activeTab.classList.remove('bg-gray-800', 'text-gray-300');
    activeTab.classList.add('bg-indigo-600', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
    activeSection.classList.remove('hidden');
}

tabMic?.addEventListener('click', () => switchTab(tabMic, sectionMic));
tabFile?.addEventListener('click', () => switchTab(tabFile, sectionFile));
tabLink?.addEventListener('click', () => switchTab(tabLink, sectionLink));

// =============================
// --- 1. Microphone Recording ---
// =============================
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let audioContext;
let analyser;
let animationId;

const recordBtn = document.getElementById('recordBtn');
const visualizer = document.getElementById('audioVisualizer');
const canvasCtx = visualizer?.getContext('2d');

recordBtn?.addEventListener('click', () => {
    if (!isRecording) startRecording();
    else stopRecording();
});

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        // Setup Audio Visualizer
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        analyser.fftSize = 128;
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        function draw() {
            animationId = requestAnimationFrame(draw);
            analyser.getByteFrequencyData(dataArray);
            canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height);

            const barWidth = (visualizer.width / bufferLength) * 2;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const barHeight = dataArray[i] / 1.5;

                const gradient = canvasCtx.createLinearGradient(0, 0, 0, visualizer.height);
                gradient.addColorStop(0, '#818cf8');
                gradient.addColorStop(1, '#c084fc');

                canvasCtx.fillStyle = gradient;
                canvasCtx.fillRect(
                    x,
                    (visualizer.height - barHeight) / 2,
                    barWidth,
                    barHeight
                );
                x += barWidth + 2;
            }
        }

        if (canvasCtx) draw();

        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = sendAudioToServer;
        mediaRecorder.start();
        isRecording = true;

        recordBtn.className =
            "bg-gray-700 hover:bg-gray-600 text-white font-bold py-4 px-8 rounded-full shadow-lg transition-all flex items-center gap-2 text-lg";

        recordBtn.innerHTML =
            `<i class="fa-solid fa-stop text-red-500"></i> Stop Recording`;

        recordingStatus?.classList.remove('hidden');

    } catch (err) {
        showToast("Microphone access denied. Please allow it in browser settings.");
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }

    isRecording = false;
    cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close();

    recordBtn.className =
        "bg-red-600 hover:bg-red-700 text-white font-bold py-4 px-8 rounded-full shadow-lg transition-all flex items-center gap-2 text-lg";

    recordBtn.innerHTML =
        `<i class="fa-solid fa-microphone"></i> Start Recording`;

    recordingStatus?.classList.add('hidden');
    showProcessing("Whisper AI is transcribing your voice...");
}

async function sendAudioToServer() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    await uploadMedia('/upload-audio', formData);
}

// =============================
// --- 2. File Upload ---
// =============================
const uploadFileBtn = document.getElementById('uploadFileBtn');
const fileInput = document.getElementById('fileInput');

uploadFileBtn?.addEventListener('click', async () => {
    if (!fileInput.files.length)
        return showToast("Please select a file first!");

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('audio', file, file.name);

    showProcessing("Whisper AI is processing your file...");
    await uploadMedia('/upload-audio', formData);
});

// =============================
// --- 3. URL Link Processing ---
// =============================
const processLinkBtn = document.getElementById('processLinkBtn');
const linkInput = document.getElementById('linkInput');

processLinkBtn?.addEventListener('click', async () => {
    const url = linkInput.value.trim();
    if (!url)
        return showToast("Please paste a valid video link first!");

    showProcessing("Downloading and transcribing audio...");

    try {
        const response = await fetch('/process-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const result = await response.json();
        if (result.success) window.location.reload();
        else throw new Error(result.error);

    } catch (error) {
        showToast("Error: " + error.message);
        hideProcessing();
    }
});

// =============================
// --- 4. Generate Study Pack ---
// =============================
async function generateStudyPack(noteId, buttonElement) {
    const originalText = buttonElement.innerHTML;

    buttonElement.innerHTML =
        `<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzing...`;

    buttonElement.disabled = true;
    buttonElement.classList.add('opacity-75', 'cursor-not-allowed');

    showToast("Gemini AI is generating your Study Pack...", "success");

    try {
        const response = await fetch(`/generate-study-pack/${noteId}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showToast("Study Pack Ready! Reloading...", "success");
            setTimeout(() => window.location.reload(), 1500);
        } else {
            throw new Error(result.error);
        }

    } catch (error) {
        showToast(error.message);
        buttonElement.innerHTML = originalText;
        buttonElement.disabled = false;
        buttonElement.classList.remove('opacity-75', 'cursor-not-allowed');
    }
}

// =============================
// --- Helper Functions ---
// =============================
function showProcessing(message) {
    loadingText.innerText = message;
    processingStatus?.classList.remove('hidden');
}

function hideProcessing() {
    processingStatus?.classList.add('hidden');
}

async function uploadMedia(endpoint, formData) {
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (result.success) window.location.reload();
        else throw new Error(result.error);

    } catch (error) {
        showToast("Upload Error: " + error.message);
        hideProcessing();
    }
}

// =============================
// --- Toast Notification System ---
// =============================
function showToast(message, type = 'error') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');

    const styleClass = type === 'error'
        ? 'bg-red-900/80 border-red-500/50 text-red-200 shadow-red-900/50'
        : 'bg-emerald-900/80 border-emerald-500/50 text-emerald-200 shadow-emerald-900/50';

    const icon = type === 'error'
        ? 'fa-circle-exclamation'
        : 'fa-wand-magic-sparkles';

    toast.className = `
        glass-card border px-5 py-4 rounded-xl flex items-center gap-3
        shadow-2xl transform transition-all duration-500
        translate-x-[120%] opacity-0 backdrop-blur-md
        pointer-events-auto max-w-sm ${styleClass}
    `;

    toast.innerHTML = `
        <i class="fa-solid ${icon} text-xl"></i>
        <p class="font-medium text-sm leading-tight">${message}</p>
    `;

    container.appendChild(toast);

    setTimeout(() =>
        toast.classList.remove('translate-x-[120%]', 'opacity-0'), 10);

    setTimeout(() => {
        toast.classList.add('translate-x-[120%]', 'opacity-0');
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}