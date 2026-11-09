/**
 * Clean Electron Launcher.
 * Strips ELECTRON_RUN_AS_NODE environment variable that IDEs and editor terminals
 * inject, ensuring Electron always launches the native desktop window.
 */

delete process.env.ELECTRON_RUN_AS_NODE;

const { spawn } = require('child_process');
const electronPath = require('electron');

const child = spawn(electronPath, ['.'], {
  stdio: 'inherit',
  env: process.env,
  windowsHide: false,
});

child.on('close', (code) => {
  process.exit(code || 0);
});

child.on('error', (err) => {
  console.error('Failed to launch Electron process:', err);
  process.exit(1);
});

