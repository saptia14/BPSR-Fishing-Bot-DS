const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    startBot: (config) => ipcRenderer.send('start-bot', config),
    stopBot: () => ipcRenderer.send('stop-bot'),
    sendCommand: (cmd) => ipcRenderer.send('send-command', cmd),

    openLogsWindow: () => ipcRenderer.send('open-logs-window'),
    openSettingsWindow: () => ipcRenderer.send('open-settings-window'),

    getConfig: () => ipcRenderer.invoke('get-config'),
    saveConfig: (data) => ipcRenderer.invoke('save-config', data),
    applyConfigLive: (config) => ipcRenderer.send('apply-config-live', config),

    resizeWindow: (height) => ipcRenderer.send('resize-window', height),

    onLog: (cb) => ipcRenderer.on('bot-log', (_, msg) => cb(msg)),
    onStatusChange: (cb) => ipcRenderer.on('bot-status', (_, s) => cb(s))
});