const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('mikeAPI', {
  minimizeToTray: () => ipcRenderer.invoke('window-minimize'),
  toggleMaximize: () => ipcRenderer.invoke('window-maximize'),
  toggleFullScreen: () => ipcRenderer.invoke('window-fullscreen'),
  closeWindow: () => ipcRenderer.invoke('window-close'),
  toggleAlwaysOnTop: (flag) => ipcRenderer.invoke('toggle-always-on-top', flag),
  setStartOnBoot: (flag) => ipcRenderer.invoke('set-start-on-boot', flag),
});

