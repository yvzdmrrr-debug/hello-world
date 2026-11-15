// AgentOS Supreme — arayüz ile ana süreç arasındaki dar köprü.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('agentos', {
  sesHazirla: () => ipcRenderer.invoke('ses:hazirla'),
  sesCevir: (float32) => ipcRenderer.invoke('ses:cevir', float32.buffer),
  sesIlerleme: (fn) => ipcRenderer.on('ses:ilerleme', (_o, veri) => fn(veri)),
  sohbet: (gecmis) => ipcRenderer.invoke('sohbet:sor', gecmis),
  kapat: () => ipcRenderer.invoke('uygulama:kapat'),
});
