const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
let currentUrl = null;
let isPaused = false;
let activeSlot = 'a';
const displayId = document.body.dataset.displayId;
const displayQuery = displayId ? '?display=' + encodeURIComponent(displayId) : '';

const imgA = document.getElementById('slide-a');
const pauseButton = document.getElementById('pause-btn');
const imgB = document.getElementById('slide-b');
const controls = document.querySelector('.controls');

function setPaused(paused) {
    isPaused = paused;
    pauseButton.textContent = paused ? '▶ Play' : '⏸ Pause';
    pauseButton.setAttribute('aria-label', paused ? 'Play slideshow' : 'Pause slideshow');
}

async function pollState() {
    try {
        const state = await fetch('/api/display/state' + displayQuery).then(r => r.json());
        setPaused(state.paused);
        if (state.mat_color) {
            document.body.style.setProperty('--mat-color', state.mat_color);
            document.body.style.background = state.mat_color;
        }
        if (state.transition_duration != null) {
            document.body.style.setProperty('--transition-duration', state.transition_duration + 's');
        }
        if (state.snapshot_url && state.snapshot_url !== currentUrl) {
            currentUrl = state.snapshot_url;
            crossfadeTo(state.snapshot_url);
        }
    } catch (e) {
        // network hiccup — retry on next interval
    }
}

function crossfadeTo(url) {
    const next = activeSlot === 'a' ? imgB : imgA;
    const prev = activeSlot === 'a' ? imgA : imgB;
    next.onload = () => {
        next.classList.add('active');
        prev.classList.remove('active');
        activeSlot = activeSlot === 'a' ? 'b' : 'a';
    };
    next.onerror = () => { /* snapshot not ready yet; keep current slide */ };
    next.src = url;
}

async function sendControl(action) {
    try {
        const resp = await fetch('/api/display/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ action, display: displayId || undefined }),
        });
        if (!resp.ok) return;
        const state = await resp.json();
        setPaused(state.paused);
        if (state.snapshot_url && state.snapshot_url !== currentUrl) {
            currentUrl = state.snapshot_url;
            crossfadeTo(state.snapshot_url);
        }
    } catch (e) { /* ignore */ }
}

function nextSlide()     { sendControl('next'); }
function previousSlide() { sendControl('prev'); }
function togglePause()   { sendControl(isPaused ? 'play' : 'pause'); }

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
    } else {
        document.exitFullscreen();
    }
}

document.addEventListener('fullscreenchange', () => {
    const btn = document.getElementById('fullscreen-btn');
    if (btn) btn.textContent = document.fullscreenElement ? '⛶ Exit Full' : '⛶ Full';
});

// Show controls on mouse move, hide cursor + controls after 3 s
(function() {
    let hideTimer = null;
    document.body.style.cursor = 'none';
    document.addEventListener('mousemove', () => {
        controls.classList.add('visible');
        document.body.style.cursor = 'default';
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => {
            controls.classList.remove('visible');
            document.body.style.cursor = 'none';
        }, 3000);
    });
})();

// Keyboard controls
document.addEventListener('keydown', e => {
    switch (e.key) {
        case 'ArrowLeft':  previousSlide(); break;
        case 'ArrowRight':
        case ' ':          nextSlide(); break;
        case 'p':          togglePause(); break;
        case 'f':
        case 'F':          toggleFullscreen(); break;
    }
});

pollState();
setInterval(pollState, 3000);
