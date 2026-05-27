const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Add any APIs needed for renderer-main communication
});