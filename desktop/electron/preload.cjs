const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('mikeAPI', {
  minimizeToTray: () => ipcRenderer.invoke('window-minimize'),
  closeWindow: () => ipcRenderer.invoke('window-close'),
  toggleAlwaysOnTop: (flag) => ipcRenderer.invoke('toggle-always-on-top', flag),
  setStartOnBoot: (flag) => ipcRenderer.invoke('set-start-on-boot', flag),
});
