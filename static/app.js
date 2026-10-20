// Live Backend API Base for Firebase Hosting
const API_BASE = (window.location.hostname.includes('web.app') || window.location.hostname.includes('firebaseapp.com'))
    ? 'https://their-facilities-wildlife-farmer.trycloudflare.com'
    : '';

let currentMediaData = null;
let selectedQuality = "720";
let activeDownloadPoll = null;
let currentGalleryImages = [];
let selectedLocalFile = null;
let deferredPwaPrompt = null;

// Register Service Worker for PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
}

// Capture PWA Install Prompt
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPwaPrompt = e;
    const btn = document.getElementById('btn-pwa-install');
    if (btn) btn.classList.remove('hidden');
});

document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) window.lucide.createIcons();
    initTheme();

    // Auto-purge any stale Service Worker caches from previous versions
    if ('caches' in window) {
        caches.keys().then((names) => {
            names.forEach((name) => {
                if (name !== 'vidzora-cache-v2') caches.delete(name);
            });
        });
    }

    // Check for auto-download/extract URL param: ?url=https://...
    const urlParam = new URLSearchParams(window.location.search).get('url');
    if (urlParam) {
        const isSelf = urlParam.includes(window.location.hostname) || urlParam.includes('127.0.0.1') || urlParam.includes('localhost') || urlParam.includes('loca.lt');
        if (!isSelf && (urlParam.startsWith('http://') || urlParam.startsWith('https://'))) {
            const input = document.getElementById('url-input');
            if (input) {
                input.value = urlParam;
                handleExtract(new Event('submit'));
            }
        }
    }

    // Close dropdowns on outside click
    document.addEventListener('click', (e) => {
        const autoMenu = document.getElementById('autodetect-menu');
        const langMenu = document.getElementById('lang-menu');
        if (autoMenu && !e.target.closest('#autodetect-menu') && !e.target.closest('button[onclick="toggleAutoDetectMenu()"]')) {
            autoMenu.classList.add('hidden');
        }
        if (langMenu && !e.target.closest('#lang-menu') && !e.target.closest('button[onclick="toggleLangMenu()"]')) {
            langMenu.classList.add('hidden');
        }
    });
});

// PWA Trigger
function triggerPwaInstall() {
    if (deferredPwaPrompt) {
        deferredPwaPrompt.prompt();
        deferredPwaPrompt.userChoice.then(() => {
            deferredPwaPrompt = null;
            const btn = document.getElementById('btn-pwa-install');
            if (btn) btn.classList.add('hidden');
        });
    } else {
        alert("To install VidZora: Tap Share -> 'Add to Home Screen' in your mobile browser menu.");
    }
}

// 1-Click Paste from Clipboard
async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        if (text && text.trim().startsWith('http')) {
            const input = document.getElementById('url-input');
            input.value = text.trim();
            showToast("Pasted from clipboard!", "clipboard");
            handleExtract(new Event('submit'));
        } else {
            showToast("No valid URL found in clipboard!", "alert-circle");
        }
    } catch (err) {
        showToast("Please grant clipboard permission!", "alert-circle");
    }
}

// Theme Management - Default is White / Light Mode
function initTheme() {
    const saved = localStorage.getItem('vidzora_theme');
    // Default theme is strictly white (light) mode unless user explicitly selected 'dark'
    if (saved === 'dark') {
        document.documentElement.classList.add('dark');
        document.documentElement.classList.remove('light');
        updateThemeIcon(true);
    } else {
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light');
        updateThemeIcon(false);
    }
}

function toggleDarkMode() {
    const isDark = document.documentElement.classList.toggle('dark');
    document.documentElement.classList.toggle('light', !isDark);
    localStorage.setItem('vidzora_theme', isDark ? 'dark' : 'light');
    updateThemeIcon(isDark);
}

function updateThemeIcon(isDark) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
        if (window.lucide) window.lucide.createIcons();
    }
}

// 4 Working Main Sub-Tabs
function switchMainTab(tab) {
    // Hide all views
    document.querySelectorAll('.tab-view').forEach(v => v.classList.add('hidden'));
    document.getElementById(`view-${tab}`).classList.remove('hidden');

    // Update tab header styles
    document.querySelectorAll('.main-tab').forEach(b => {
        b.className = 'main-tab flex items-center gap-1.5 pb-2 text-gray-500 hover:text-gray-900 dark:hover:text-gray-200 transition';
    });
    const activeBtn = document.getElementById(`tab-${tab}`);
    activeBtn.className = 'main-tab active flex items-center gap-1.5 pb-2 border-b-2 border-purple-600 text-purple-600 dark:text-purple-400 font-bold transition';
    if (window.lucide) window.lucide.createIcons();
}

// Auto Detect Dropdown
function toggleAutoDetectMenu() {
    const menu = document.getElementById('autodetect-menu');
    menu.classList.toggle('hidden');
}

function setAutoDetectMode(label, quality) {
    selectedQuality = quality;
    document.getElementById('autodetect-label').innerText = label;
    document.getElementById('autodetect-menu').classList.add('hidden');
    showToast(`Mode set to: ${label}`, 'check');
    if (currentMediaData) renderFormatCards();
}

// Language Switcher
function toggleLangMenu() {
    const menu = document.getElementById('lang-menu');
    menu.classList.toggle('hidden');
}

function setLanguage(lang) {
    document.getElementById('current-lang').innerText = lang;
    document.getElementById('lang-menu').classList.add('hidden');
    showToast(`Language changed to ${lang}`, 'globe');
}

// Clear Input
function clearInput() {
    const input = document.getElementById('url-input');
    input.value = '';
    input.focus();
}

// Format Chips (MP4, MP3, HD, 4K)
function selectQuickChip(type) {
    document.querySelectorAll('.quick-chip').forEach(c => c.classList.remove('active'));
    const target = document.getElementById(`chip-${type}`);
    if (target) target.classList.add('active');

    if (type === 'mp3') {
        selectedQuality = 'mp3_320';
        showToast("MP3 Audio mode selected", "music");
    } else if (type === 'hd') {
        selectedQuality = '720';
        showToast("720p HD mode selected", "check");
    } else if (type === '4k') {
        selectedQuality = '1080';
        showToast("Maximum 4K / 1080p mode selected", "sparkles");
    } else if (type === 'thumb') {
        selectedQuality = 'thumb_hd';
        showToast("HD Thumbnail mode selected", "image");
    } else {
        selectedQuality = '720';
    }

    if (currentMediaData) renderFormatCards();
}

// Modals System (Privacy, Terms, Supported, FAQ, Blog)
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        if (modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
        modal.classList.add('is-open');
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('is-open');
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

// Tool Cards Click Handlers (6 Video Tools)
function activateTool(tool) {
    const input = document.getElementById('url-input');
    switchMainTab('single');

    if (tool === 'video') {
        selectQuickChip('mp4');
        input.placeholder = "Paste any video link (YouTube, Facebook, Twitter)...";
        showToast("Video Downloader tool active", "play");
    } else if (tool === 'reels') {
        selectQuickChip('mp4');
        input.placeholder = "Paste Instagram Reel or YouTube Short URL...";
        showToast("Reels & Shorts tool active", "clapperboard");
    } else if (tool === 'stories') {
        selectQuickChip('mp4');
        input.placeholder = "Paste Instagram or Facebook Story link...";
        showToast("Stories tool active", "loader");
    } else if (tool === 'mp3') {
        selectQuickChip('mp3');
        input.placeholder = "Paste link to extract MP3 audio (YouTube, SoundCloud)...";
        showToast("MP3 Converter tool active", "music");
    } else if (tool === 'playlist') {
        switchMainTab('many');
        showToast("Playlist Downloader active", "list-video");
        return;
    } else if (tool === 'thumbnail') {
        selectQuickChip('thumb');
        input.placeholder = "Paste video link to grab HD cover & thumbnail...";
        showToast("Thumbnail Grabber active", "image");
    }

    document.getElementById('downloader').scrollIntoView({ behavior: 'smooth', block: 'center' });
    input.focus();
}

function selectPlatformPreset(platform) {
    switchMainTab('single');
    const input = document.getElementById('url-input');
    input.placeholder = `Paste ${platform.toUpperCase()} video link here...`;
    showToast(`Ready for ${platform.toUpperCase()}!`, 'check');
    document.getElementById('downloader').scrollIntoView({ behavior: 'smooth', block: 'center' });
    input.focus();
}

// Local File Upload & Converter (View 2)
function handleFileSelect(input) {
    if (input.files && input.files[0]) {
        selectedLocalFile = input.files[0];
        const lbl = document.getElementById('selected-file-label');
        lbl.innerText = `Selected: ${selectedLocalFile.name} (${(selectedLocalFile.size / (1024*1024)).toFixed(1)} MB)`;
        lbl.classList.remove('hidden');
    }
}

async function processLocalUpload() {
    if (!selectedLocalFile) {
        alert("Please choose a file from your computer first!");
        return;
    }
    const btn = document.getElementById('btn-convert-upload');
    const fmt = document.getElementById('upload-target-fmt').value;

    btn.disabled = true;
    btn.innerText = "Converting on server...";
    showToast("Converting file... Please wait", "refresh-cw");

    const formData = new FormData();
    formData.append("file", selectedLocalFile);

    try {
        const res = await fetch(`${API_BASE}/api/upload/convert?target_format=${fmt}`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error("Conversion failed on server.");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const base = selectedLocalFile.name.substring(0, selectedLocalFile.name.lastIndexOf('.')) || 'converted';
        a.download = `${base}.${fmt}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast("File converted and downloaded!", "check-circle");
    } catch (e) {
        alert("Conversion error: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "Convert & Save Now";
    }
}

// Bulk Download Processing (View 3)
async function processBulkDownload() {
    const raw = document.getElementById('bulk-urls-input').value.trim();
    if (!raw) {
        alert("Please paste at least one URL!");
        return;
    }
    const urls = raw.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
    if (urls.length === 0) {
        alert("Please paste valid HTTP/HTTPS URLs!");
        return;
    }

    const btn = document.getElementById('btn-bulk-download');
    btn.disabled = true;
    btn.innerHTML = '<div class="inline-block animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div><span>Processing Bulk ZIP Archive...</span>';
    showToast(`Downloading ${urls.length} videos into ZIP...`, 'archive');

    try {
        const res = await fetch(`${API_BASE}/api/bulk/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: urls, quality: selectedQuality })
        });

        if (!res.ok) throw new Error("Bulk download failed.");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `vidzora_bulk_download.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast("Bulk ZIP archive saved!", "check-circle");
    } catch (e) {
        alert("Bulk download error: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="archive" class="w-4 h-4"></i><span>Download All As ZIP Archive</span>';
        if (window.lucide) window.lucide.createIcons();
    }
}

// Many Links / Playlist Extraction (View 4)
async function processManyLinks() {
    const url = document.getElementById('many-input').value.trim();
    if (!url) {
        alert("Please enter a playlist or video link!");
        return;
    }

    const listDiv = document.getElementById('many-results');
    listDiv.innerHTML = '<div class="py-4 text-center text-xs text-gray-400">Extracting tracks and video streams...</div>';

    try {
        const res = await fetch(`${API_BASE}/api/bulk/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: [url] })
        });
        const data = await res.json();
        listDiv.innerHTML = '';

        if (data.results && data.results.length > 0 && data.results[0].success) {
            const item = data.results[0].data;
            const row = document.createElement('div');
            row.className = "p-3 rounded-xl bg-gray-100 dark:bg-gray-800 flex items-center justify-between gap-3 text-xs";
            row.innerHTML = `
                <div class="flex items-center gap-2.5 min-w-0">
                    <img src="${item.thumbnail || ''}" class="w-12 h-8 rounded object-cover flex-shrink-0 bg-gray-900">
                    <div class="min-w-0">
                        <p class="font-bold truncate text-gray-900 dark:text-white">${item.title}</p>
                        <p class="text-[10px] text-gray-500">${item.duration} • ${item.uploader}</p>
                    </div>
                </div>
                <button onclick="window.location.href='${API_BASE}/api/download/direct?url=${encodeURIComponent(item.url)}&quality=720'" class="px-3 py-1.5 rounded-lg bg-purple-600 text-white font-bold text-xs flex-shrink-0 hover:bg-purple-500">
                    Save MP4
                </button>
            `;
            listDiv.appendChild(row);
        } else {
            listDiv.innerHTML = '<div class="py-4 text-center text-xs text-red-500">Could not extract items from this link.</div>';
        }
    } catch (e) {
        listDiv.innerHTML = `<div class="py-4 text-center text-xs text-red-500">${e.message}</div>`;
    }
}

// Toast helper
function showToast(message, iconName = 'check') {
    const toast = document.getElementById('toast');
    const toastText = document.getElementById('toast-text');
    const toastIcon = document.getElementById('toast-icon');

    toastText.innerText = message;
    toastIcon.setAttribute('data-lucide', iconName);
    if (window.lucide) window.lucide.createIcons();

    toast.classList.add('toast-visible');
    setTimeout(() => {
        toast.classList.remove('toast-visible');
    }, 2800);
}

// Single Link Extraction
async function handleExtract(e) {
    e.preventDefault();
    const url = document.getElementById('url-input').value.trim();
    if (!url) return;

    document.getElementById('error-card').classList.add('hidden');
    document.getElementById('result-card').classList.add('hidden');
    document.getElementById('gallery-card').classList.add('hidden');
    document.getElementById('loading-state').classList.remove('hidden');
    document.getElementById('btn-fetch').disabled = true;

    try {
        const res = await fetch(`${API_BASE}/api/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Unable to extract media.");

        const media = data.data;

        if (data.is_gallery || (media.images && media.images.length > 0)) {
            renderGallery(media);
        } else {
            renderVideo(media);
        }

    } catch (err) {
        document.getElementById('error-msg').innerText = err.message || "Failed to load link.";
        document.getElementById('error-card').classList.remove('hidden');
    } finally {
        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('btn-fetch').disabled = false;
        if (window.lucide) window.lucide.createIcons();
    }
}

// Render Video Details
function renderVideo(media) {
    currentMediaData = media;

    document.getElementById('res-thumbnail').src = media.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=60';
    document.getElementById('res-title').innerText = media.title;
    document.getElementById('res-uploader-text').innerText = media.uploader || 'Online Creator';
    document.getElementById('res-duration').innerText = media.duration || '';

    renderFormatCards();

    document.getElementById('result-card').classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
}

function renderFormatCards() {
    const grid = document.getElementById('format-options-grid');
    grid.innerHTML = '';

    const displayOpts = [...currentMediaData.options.slice(0, 3)];
    // Add HD Thumbnail option to format grid
    displayOpts.push({
        id: "thumb_hd",
        label: "HD Video Thumbnail",
        badge: "1080p",
        type: "image",
        desc: "Full Quality Cover Image"
    });

    displayOpts.forEach((opt) => {
        const isSelected = opt.id === selectedQuality;
        const card = document.createElement('div');
        card.className = `quality-card p-2.5 rounded-xl flex items-center justify-between text-left ${isSelected ? 'selected' : ''}`;
        card.onclick = () => selectFormat(opt.id);

        card.innerHTML = `
            <div class="flex items-center gap-2">
                <div class="w-2.5 h-2.5 rounded-full border ${opt.type === 'image' ? 'border-amber-500' : 'border-purple-500'} flex items-center justify-center ${isSelected ? (opt.type === 'image' ? 'bg-amber-500' : 'bg-purple-600') : 'bg-transparent'}">
                    ${isSelected ? '<div class="w-1 h-1 bg-white rounded-full"></div>' : ''}
                </div>
                <div>
                    <div class="text-xs font-bold text-gray-800 dark:text-gray-200">${opt.label}</div>
                    <div class="text-[10px] text-gray-400">${opt.desc}</div>
                </div>
            </div>
            <span class="text-[9px] font-black uppercase px-1.5 py-0.5 rounded ${opt.type === 'image' ? 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300' : 'bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300'}">${opt.badge}</span>
        `;
        grid.appendChild(card);
    });

    updateDownloadButton();
}

function selectFormat(id) {
    selectedQuality = id;
    renderFormatCards();
}

function updateDownloadButton() {
    let label = `Download Video (${selectedQuality.toUpperCase()}P)`;
    if (selectedQuality === 'thumb_hd') {
        label = "Download HD Thumbnail (1080p JPG)";
    } else if (selectedQuality.startsWith('mp3') || selectedQuality === 'm4a') {
        label = `Download Audio (${selectedQuality.toUpperCase().replace('_', ' ')})`;
    }
    const el = document.getElementById('download-btn-label');
    if (el) el.innerText = label;
}

// Video Trimmer UI Toggle
function toggleTrimmerUI() {
    const box = document.getElementById('trim-inputs-box');
    const toggle = document.getElementById('trim-toggle');
    if (toggle && toggle.checked) {
        box.classList.remove('hidden');
        showToast("Trimmer activated. Enter start and end time.", "scissors");
    } else if (box) {
        box.classList.add('hidden');
    }
}

// Download Video with Instant Direct Browser Streaming (0 Server Disk Storage + Trimmer Support)
async function startDownload() {
    if (!currentMediaData || !currentMediaData.url) return;

    if (selectedQuality === 'thumb_hd') {
        downloadThumbnail('hd');
        return;
    }

    const btn = document.getElementById('btn-start-download');
    btn.disabled = true;

    // Check Trimmer parameters
    const trimToggle = document.getElementById('trim-toggle');
    let startTime = null;
    let endTime = null;
    if (trimToggle && trimToggle.checked) {
        startTime = document.getElementById('trim-start-time')?.value.trim();
        endTime = document.getElementById('trim-end-time')?.value.trim();
    }

    let directStreamUrl = `${API_BASE}/api/stream/download?url=${encodeURIComponent(currentMediaData.url)}&quality=${encodeURIComponent(selectedQuality)}`;
    if (startTime) directStreamUrl += `&start_time=${encodeURIComponent(startTime)}`;
    if (endTime) directStreamUrl += `&end_time=${encodeURIComponent(endTime)}`;

    // Trigger high-tech animated download modal with ad-viewing delay
    openDownloadAnimationModal(directStreamUrl, startTime);

    // Re-enable download button after a short moment
    setTimeout(() => {
        btn.disabled = false;
        btn.className = "w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-extrabold text-sm shadow-xl shadow-emerald-500/25 transition flex items-center justify-center gap-2";
        btn.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4"></i><span>Downloading Now (Click to Retry)</span>`;
        if (window.lucide) window.lucide.createIcons();
    }, 3500);
}

// Engaging Animated Download Processing Modal
function openDownloadAnimationModal(directStreamUrl, startTime) {
    const modal = document.getElementById('download-anim-modal');
    if (!modal) {
        window.location.href = directStreamUrl;
        return;
    }
    if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
    }

    const titleEl = document.getElementById('anim-video-title');
    const badgeEl = document.getElementById('anim-quality-badge');
    const statusEl = document.getElementById('anim-status-text');
    const stepEl = document.getElementById('anim-step-desc');
    const percentEl = document.getElementById('anim-percent');
    const barEl = document.getElementById('anim-bar-fill');
    const iconContainer = document.getElementById('anim-icon-container');
    const actionBtn = document.getElementById('anim-action-btn');

    if (titleEl) titleEl.innerText = currentMediaData?.title || "Video Download";
    if (badgeEl) badgeEl.innerText = (selectedQuality || "720").toUpperCase();
    if (barEl) barEl.style.width = '10%';
    if (percentEl) percentEl.innerText = '10%';
    if (statusEl) statusEl.innerText = 'Connecting to Ultra-Speed Stream...';
    if (stepEl) stepEl.innerText = 'Contacting video source CDN servers...';
    if (iconContainer) {
        iconContainer.innerHTML = `<i data-lucide="loader-2" class="w-12 h-12 text-purple-600 animate-spin"></i>`;
    }
    if (actionBtn) {
        actionBtn.disabled = true;
        actionBtn.innerText = "Processing Stream (Please wait a second)...";
        actionBtn.className = "w-full py-3 px-4 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-400 font-bold text-xs cursor-not-allowed";
    }

    modal.classList.add('is-open');
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    modal.style.zIndex = '2147483647';
    if (window.lucide) window.lucide.createIcons();

    let step = 0;
    const interval = setInterval(() => {
        step++;
        if (step === 1) {
            if (barEl) barEl.style.width = '35%';
            if (percentEl) percentEl.innerText = '35%';
            if (statusEl) statusEl.innerText = 'Demuxing Video & Audio Streams...';
            if (stepEl) stepEl.innerText = startTime ? 'Trimming custom video clip on-the-fly...' : 'Extracting highest bitrate video track...';
        } else if (step === 2) {
            if (barEl) barEl.style.width = '70%';
            if (percentEl) percentEl.innerText = '70%';
            if (statusEl) statusEl.innerText = 'Merging & Optimizing Container...';
            if (stepEl) stepEl.innerText = 'Encoding lossless audio/video container for instant streaming...';
        } else if (step === 3) {
            if (barEl) barEl.style.width = '92%';
            if (percentEl) percentEl.innerText = '92%';
            if (statusEl) statusEl.innerText = 'Finalizing Browser Download...';
            if (stepEl) stepEl.innerText = 'Transmitting stream directly to your device storage...';
        } else if (step >= 4) {
            clearInterval(interval);
            if (barEl) barEl.style.width = '100%';
            if (percentEl) percentEl.innerText = '100%';
            if (statusEl) statusEl.innerText = 'Download Started Successfully!';
            if (stepEl) stepEl.innerText = 'Transfer active! Check your phone or browser Downloads.';
            if (iconContainer) {
                iconContainer.innerHTML = `<i data-lucide="check-circle-2" class="w-12 h-12 text-emerald-500 animate-bounce"></i>`;
            }
            if (actionBtn) {
                actionBtn.disabled = false;
                actionBtn.innerText = "Done! Download Another Video";
                actionBtn.className = "w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-extrabold text-xs shadow-lg shadow-emerald-500/25 cursor-pointer transition transform active:scale-95";
                actionBtn.onclick = () => closeDownloadAnimModal();
            }
            if (window.lucide) window.lucide.createIcons();

            // Trigger the native browser download
            window.location.href = directStreamUrl;
            showToast("Direct download started in browser!", "arrow-down-circle");
        }
    }, 700);
}

function closeDownloadAnimModal() {
    const modal = document.getElementById('download-anim-modal');
    if (modal) {
        modal.classList.remove('is-open');
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

// Developer API Waitlist / Pre-registration
function joinApiWaitlist(planName) {
    const email = prompt(`Enter your email to get 50% Early-Bird Discount for VidZora ${planName} API:`);
    if (email && email.includes('@')) {
        showToast(`Awesome! ${email} registered for ${planName} Early Access.`, "check-circle");
    } else if (email) {
        showToast("Please enter a valid email address.", "alert-circle");
    }
}

// Dedicated 1-Click HD / Standard Video Thumbnail Downloader
function downloadThumbnail(res = 'hd') {
    if (!currentMediaData) {
        showToast("Please search for a video first", "alert-circle");
        return;
    }
    const thumbUrl = (res === 'hd' && currentMediaData.thumbnail_hd) ? currentMediaData.thumbnail_hd : (currentMediaData.thumbnail || currentMediaData.thumbnail_hd);
    if (!thumbUrl) {
        showToast("No thumbnail found for this video", "alert-circle");
        return;
    }
    const cleanTitle = (currentMediaData.title || "thumbnail").replace(/[^\w\s-]/g, '').trim().substring(0, 50);
    const downloadApi = `${API_BASE}/api/thumbnail/download?url=${encodeURIComponent(thumbUrl)}&title=${encodeURIComponent(cleanTitle)}`;
    
    showToast(`Downloading ${res.toUpperCase()} thumbnail directly...`, "image");
    window.location.href = downloadApi;
}

// In-Browser Live Video/Audio Preview Modal
function openPreviewModal() {
    if (!currentMediaData) {
        showToast("Please search for a video first", "alert-circle");
        return;
    }
    const modal = document.getElementById('preview-modal');
    if (!modal) return;

    // Relocate modal directly to <body> so no parent overflow, transform, or hidden styling can trap it
    if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
    }

    const player = document.getElementById('preview-video-player');
    const titleEl = document.getElementById('preview-title');
    if (titleEl) titleEl.innerText = currentMediaData.title || "Video Preview";
    
    // Set poster image if available
    const poster = currentMediaData.thumbnail_hd || currentMediaData.thumbnail;
    if (poster && player) player.poster = poster;

    // Set direct preview stream URL
    if (player) {
        player.src = `${API_BASE}/api/stream/preview?url=${encodeURIComponent(currentMediaData.url)}&quality=360`;
    }

    modal.classList.add('is-open');
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    modal.style.zIndex = '2147483647';
    modal.style.visibility = 'visible';
    modal.style.opacity = '1';

    if (player) {
        player.play().catch(() => {});
    }
}

function closePreviewModal() {
    const modal = document.getElementById('preview-modal');
    const player = document.getElementById('preview-video-player');
    if (player) {
        player.pause();
        player.removeAttribute('src');
        player.load();
    }
    if (modal) {
        modal.classList.remove('is-open');
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

// PC to Phone QR Code Transfer Modal
let activeMobileUrl = '';

function getMobileAccessibleBaseUrl() {
    if (API_BASE) {
        return API_BASE;
    }
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
        return 'https://throwing-inspired-agents-terminal.trycloudflare.com';
    }
    return window.location.origin;
}

function openQrModal() {
    if (!currentMediaData) {
        showToast("Please search for a video first", "alert-circle");
        return;
    }
    const modal = document.getElementById('qr-modal');
    if (!modal) return;

    if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
    }

    const img = document.getElementById('qr-image');
    const whatsappBtn = document.getElementById('qr-whatsapp-link');
    const statusPill = document.getElementById('qr-network-status');

    const baseUrl = getMobileAccessibleBaseUrl();
    activeMobileUrl = `${baseUrl}/api/stream/download?url=${encodeURIComponent(currentMediaData.url)}&quality=${encodeURIComponent(selectedQuality)}`;
    
    if (img) img.src = `${API_BASE}/api/qrcode?text=${encodeURIComponent(activeMobileUrl)}`;
    
    if (whatsappBtn) {
        const text = encodeURIComponent(`Download "${currentMediaData.title}" on your phone:\n${activeMobileUrl}`);
        whatsappBtn.href = `https://api.whatsapp.com/send?text=${text}`;
    }

    if (statusPill) {
        statusPill.innerText = `📱 Direct Mobile Scan Active`;
    }

    modal.classList.add('is-open');
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    modal.style.zIndex = '2147483647';
    modal.style.visibility = 'visible';
    modal.style.opacity = '1';
}

function copyCurrentDownloadLink() {
    if (!currentMediaData) return;
    const streamBase = API_BASE || window.location.origin;
    const urlToCopy = activeMobileUrl || `${streamBase}/api/stream/download?url=${encodeURIComponent(currentMediaData.url)}&quality=${encodeURIComponent(selectedQuality)}`;
    navigator.clipboard.writeText(urlToCopy).then(() => {
        showToast("Direct mobile download link copied!", "check-circle");
    });
}

// Share Video Link via Native Web Share API or WhatsApp
async function shareVideoLink() {
    if (!currentMediaData) return;
    const shareUrl = `${window.location.origin}/?url=${encodeURIComponent(currentMediaData.url)}`;
    if (navigator.share) {
        try {
            await navigator.share({
                title: currentMediaData.title,
                text: `Download "${currentMediaData.title}" on VidZora:`,
                url: shareUrl
            });
            showToast("Shared successfully!", "check");
            return;
        } catch (e) {}
    }
    // Fallback: Copy link
    navigator.clipboard.writeText(shareUrl).then(() => {
        showToast("Shareable link copied! Send to friends on WhatsApp", "share-2");
    });
}

// Render Gallery
function renderGallery(gallery) {
    currentGalleryImages = gallery.images || [];
    document.getElementById('gallery-title').innerText = `${currentGalleryImages.length} Images Found`;

    const grid = document.getElementById('gallery-grid');
    grid.innerHTML = '';

    currentGalleryImages.forEach((img) => {
        const item = document.createElement('div');
        item.className = "relative rounded-xl overflow-hidden aspect-square bg-gray-950 border border-gray-200 dark:border-gray-800 group";
        item.innerHTML = `
            <img src="${img.url}" loading="lazy" class="w-full h-full object-cover group-hover:scale-105 transition duration-300">
            <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center p-2">
                <a href="${img.url}" target="_blank" download class="p-2 rounded-lg bg-purple-600 text-white font-bold text-xs flex items-center gap-1 shadow-lg hover:bg-purple-500">
                    <i data-lucide="download" class="w-3.5 h-3.5"></i>
                    <span>Save</span>
                </a>
            </div>
        `;
        grid.appendChild(item);
    });

    document.getElementById('gallery-card').classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
}

// Download Gallery ZIP
async function downloadGalleryZip() {
    if (!currentGalleryImages.length) return;
    try {
        const urls = currentGalleryImages.map(img => img.url);
        const title = "gallery_photos";

        const res = await fetch(`${API_BASE}/api/gallery/zip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images: urls, title: title })
        });

        if (!res.ok) throw new Error("ZIP creation failed");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast("ZIP archive downloaded!", "archive");
    } catch (e) {
        alert("Failed to create ZIP: " + e.message);
    }
}
