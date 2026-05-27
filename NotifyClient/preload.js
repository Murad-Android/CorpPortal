const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('portal', {
    closeGreeting: () => ipcRenderer.send('close-greeting'),
    getUserName: () => ipcRenderer.invoke('get-user-name')
});
