const btnStart = document.getElementById('btnStart');
const btnStop = document.getElementById('btnStop');
const btnPause = document.getElementById('btnPause');
const btnStats = document.getElementById('btnStats');
const btnSettings = document.getElementById('btnSettings');
const btnOpenLogs = document.getElementById('btnOpenLogs');
const statusDot = document.getElementById('statusDot');
const statsPanel = document.getElementById('statsPanel');
const miniStats = document.getElementById('miniStats');

const statFish = document.getElementById('statFish');
const statEscaped = document.getElementById('statEscaped');
const statRods = document.getElementById('statRods');

let isRunning = false;
let isPaused = false;
let statsOpen = false;

btnStart.addEventListener('click', async () => {
    const config = await window.api.getConfig();
    updateStats({fish_caught: 0, fish_escaped: 0, rod_breaks: 0});
    miniStats.innerText = "0 🐟";
    window.api.startBot(config);
});

btnStop.addEventListener('click', () => window.api.stopBot());

btnPause.addEventListener('click', () => {
    const cmd = isPaused ? 'resume' : 'pause';
    window.api.sendCommand(cmd);
});

btnStats.addEventListener('click', () => {
    statsOpen = !statsOpen;
    if (statsOpen) {
        statsPanel.classList.add('visible');
        window.api.resizeWindow(160);
        btnStats.style.color = "white";
        btnStats.style.background = "rgba(255,255,255,0.15)";
    } else {
        statsPanel.classList.remove('visible');
        window.api.resizeWindow(70);
        btnStats.style.color = "";
        btnStats.style.background = "";
    }
});

btnOpenLogs.addEventListener('click', () => window.api.openLogsWindow());
btnSettings.addEventListener('click', () => window.api.openSettingsWindow());

window.api.onStatusChange((status) => {
    isRunning = (status === 'running');
    updateControls();
});

window.api.onLog((message) => {
    const clean = message.trim();
    if (!clean) return;

    if (clean.startsWith('__JSON__')) {
        try {
            const data = JSON.parse(clean.substring(8)).data;
            updateStats(data);
        } catch(e){}
        return;
    }

    if (clean.includes('Bot PAUSADO')) { isPaused = true; updateControls(); }
    else if (clean.includes('Bot A EXECUTAR')) { isPaused = false; updateControls(); }
});

function updateControls() {
    if (isRunning) {
        btnStart.classList.add('hidden');
        btnPause.classList.remove('hidden');
        btnStop.classList.remove('hidden');

        if (isPaused) {
            statusDot.className = 'status-dot paused';
            btnPause.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
            btnPause.title = "Retomar";
        } else {
            statusDot.className = 'status-dot running';
            btnPause.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
            btnPause.title = "Pausar";
        }
    } else {
        btnStart.classList.remove('hidden');
        btnPause.classList.add('hidden');
        btnStop.classList.add('hidden');
        statusDot.className = 'status-dot stopped';
    }
}

function updateStats(data) {
    if(data.fish_caught !== undefined) {
        statFish.innerText = data.fish_caught;
        miniStats.innerText = `${data.fish_caught} 🐟`;
    }
    if(data.fish_escaped !== undefined) statEscaped.innerText = data.fish_escaped;
    if(data.rod_breaks !== undefined) statRods.innerText = data.rod_breaks;
}