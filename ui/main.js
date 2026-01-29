const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let logsWindow = null;
let settingsWindow = null;
let botProcess = null;
const configPath = path.join(app.getPath('userData'), 'bot_config.json');

function loadConfig() {
    try {
        if (fs.existsSync(configPath)) {
            return JSON.parse(fs.readFileSync(configPath));
        }
    } catch (e) { console.error("Erro config:", e); }
    return { precision: 0.65, delay: 0.5, fps: 0 };
}

function saveConfig(data) {
    fs.writeFileSync(configPath, JSON.stringify(data));

    if (botProcess && botProcess.stdin) {
        const command = JSON.stringify({ cmd: "update_config", data: data });
        botProcess.stdin.write(command + "\n");
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 400, height: 70,
        frame: false, transparent: true, resizable: false, alwaysOnTop: true, hasShadow: false,
        webPreferences: { preload: path.join(__dirname, 'preload.js'), nodeIntegration: false, contextIsolation: true }
    });

    mainWindow.loadFile('index.html');

    ipcMain.on('resize-window', (event, height) => {
        mainWindow.setSize(400, height);
    });
}

function createLogsWindow() {
    if (logsWindow) { logsWindow.focus(); return; }
    logsWindow = new BrowserWindow({
        width: 600, height: 400, backgroundColor: '#0f0f0f',
        webPreferences: { preload: path.join(__dirname, 'preload.js') },
        autoHideMenuBar: true, title: "Logs"
    });
    logsWindow.loadFile('logs.html');
    logsWindow.on('closed', () => { logsWindow = null; });
}

function createSettingsWindow() {
    if (settingsWindow) { settingsWindow.focus(); return; }
    settingsWindow = new BrowserWindow({
        width: 350, height: 450, backgroundColor: '#1a1a1a',
        parent: mainWindow,
        webPreferences: { preload: path.join(__dirname, 'preload.js') },
        autoHideMenuBar: true, title: "Configurações", resizable: false
    });
    settingsWindow.loadFile('settings.html');
    settingsWindow.on('closed', () => { settingsWindow = null; });
}

function getBotPath() {
    const isDev = !app.isPackaged;
    const exeName = 'bpsr-fishingbot.exe';
    return isDev
        ? path.join(__dirname, 'resources', 'executables', exeName)
        : path.join(process.resourcesPath, 'executables', exeName);
}

function broadcastLog(message) {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('bot-log', message);
    if (logsWindow && !logsWindow.isDestroyed()) logsWindow.webContents.send('bot-log', message);
}

ipcMain.handle('get-config', () => loadConfig());
ipcMain.handle('save-config', (event, data) => saveConfig(data));
ipcMain.on('open-logs-window', () => createLogsWindow());
ipcMain.on('open-settings-window', () => createSettingsWindow());
ipcMain.on('resize-window', (event, height) => { if(mainWindow) mainWindow.setSize(400, height); });

ipcMain.on('start-bot', (event, config) => {
    if (botProcess) return;
    const botPath = getBotPath();
    const args = ['--autostart', '--precision', config.precision.toString(), '--casting_delay', config.delay.toString(), '--fps', config.fps.toString()];

    try {
        botProcess = spawn(botPath, args);
        if (mainWindow) mainWindow.webContents.send('bot-status', 'running');

        botProcess.stdout.on('data', (data) => broadcastLog(data.toString()));
        botProcess.stderr.on('data', (data) => broadcastLog(`[ERRO] ${data.toString()}`));

        botProcess.on('close', (code) => {
            broadcastLog(`[SISTEMA] Processo terminado.`);
            if (mainWindow) mainWindow.webContents.send('bot-status', 'stopped');
            botProcess = null;
        });
    } catch (error) { broadcastLog(`[CRITICO] ${error.message}`); }
});

ipcMain.on('send-command', (event, command) => {
    if (botProcess && botProcess.stdin) botProcess.stdin.write(command + "\n");
});

ipcMain.on('stop-bot', () => { if (botProcess) botProcess.kill(); });

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
    if (botProcess) botProcess.kill();
    if (process.platform !== 'darwin') app.quit();
});