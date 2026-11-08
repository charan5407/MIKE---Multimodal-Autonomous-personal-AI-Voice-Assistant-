const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, nativeImage } = require('electron');
const path = require('path');
const http = require('http');

let mainWindow = null;
let tray = null;
let isQuitting = false;
let wakeWordEnabled = true;

// Generate SVG Data URI for the "C" brand icon
function createCIcon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="15" fill="#050b14" stroke="#00f0ff" stroke-width="2"/>
      <path d="M 23 10 A 9 9 0 1 0 23 22" fill="none" stroke="#00f0ff" stroke-width="3.5" stroke-linecap="round"/>
      <circle cx="16" cy="16" r="3" fill="#00f0ff"/>
    </svg>
  `;
  return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`);
}

function sendCoreAction(actionPath) {
  const req = http.request({
    hostname: '127.0.0.1',
    port: 8765,
    path: actionPath,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  req.on('error', (err) => console.log('Action request error:', err.message));
  req.end();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 760,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    icon: createCIcon(),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  });

  const devUrl = 'http://localhost:5173';
  mainWindow.loadURL(devUrl).catch(() => {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  });

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
  });
}

function createTray() {
  const icon = createCIcon();
  tray = new Tray(icon);
  tray.setToolTip('MIKE - Autonomous Agentic Voice Assistant (Charan)');

  const updateContextMenu = () => {
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Show / Hide MIKE HUD',
        click: () => {
          if (mainWindow.isVisible()) {
            mainWindow.hide();
          } else {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      {
        label: 'Push to Talk (Ctrl+Space)',
        click: () => sendCoreAction('/api/action/push-to-talk'),
      },
      {
        label: `Wake Word: ${wakeWordEnabled ? 'Enabled [ON]' : 'Disabled [OFF]'}`,
        type: 'checkbox',
        checked: wakeWordEnabled,
        click: (item) => {
          wakeWordEnabled = item.checked;
          const req = http.request({
            hostname: '127.0.0.1',
            port: 8765,
            path: '/api/settings',
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          });
          req.write(JSON.stringify({ wake_word_enabled: wakeWordEnabled }));
          req.end();
          updateContextMenu();
        },
      },
      { type: 'separator' },
      {
        label: 'Emergency Stop (Ctrl+Alt+Shift+S)',
        click: () => sendCoreAction('/api/action/stop'),
      },
      { type: 'separator' },
      {
        label: 'Quit MIKE',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);
    tray.setContextMenu(contextMenu);
  };

  updateContextMenu();

  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  // Register Global Stop Hotkey
  globalShortcut.register('CommandOrControl+Alt+Shift+S', () => {
    console.log('Global Emergency Stop Hotkey triggered!');
    sendCoreAction('/api/action/stop');
  });

  // Register Global Push-to-Talk Hotkey
  globalShortcut.register('CommandOrControl+Space', () => {
    console.log('Global Push-to-Talk Hotkey triggered!');
    sendCoreAction('/api/action/push-to-talk');
  });
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

// IPC Listeners
ipcMain.handle('window-minimize', () => {
  if (mainWindow) mainWindow.hide();
});

ipcMain.handle('window-close', () => {
  if (mainWindow) mainWindow.hide();
});

ipcMain.handle('toggle-always-on-top', (event, flag) => {
  if (mainWindow) {
    mainWindow.setAlwaysOnTop(flag);
    return mainWindow.isAlwaysOnTop();
  }
  return false;
});

ipcMain.handle('set-start-on-boot', (event, flag) => {
  app.setLoginItemSettings({
    openAtLogin: flag,
    openAsHidden: true,
  });
  return app.getLoginItemSettings().openAtLogin;
});

