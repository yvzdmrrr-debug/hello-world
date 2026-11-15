// AgentOS Supreme — Electron ana süreci.
const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const fs = require('fs');

const AD = 'AgentOS Supreme';
app.setName(AD);
if (process.platform === 'win32') app.setAppUserModelId('com.agentos.supreme');
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

let pencere = null;

function ayarlar() {
  // İsteğe bağlı sohbet modeli ayarı: uygulama klasöründeki ya da kullanıcı verisindeki ayarlar.json
  for (const yol of [path.join(app.getPath('userData'), 'ayarlar.json'), path.join(__dirname, 'ayarlar.json')]) {
    try { return JSON.parse(fs.readFileSync(yol, 'utf8')); } catch (_) { /* yok ya da bozuk: sıradaki */ }
  }
  return {};
}

function pencereAc() {
  pencere = new BrowserWindow({
    title: AD,
    fullscreen: true,
    autoHideMenuBar: true,
    backgroundColor: '#02040a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  pencere.setMenuBarVisibility(false);
  pencere.once('ready-to-show', () => { pencere.show(); pencere.setFullScreen(true); });
  pencere.on('page-title-updated', (e) => e.preventDefault());
  pencere.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  pencere.webContents.on('will-navigate', (e) => e.preventDefault());
  pencere.loadFile(path.join(__dirname, 'index.html'));
}

// ---------------------------------------------------------------- ses tanıma (Whisper, yerel)
let tanima = null;      // yüklenen model (Promise)
let sira = Promise.resolve();

function tanimaYukle() {
  if (tanima) return tanima;
  tanima = (async () => {
    const T = require('@huggingface/transformers');
    T.env.cacheDir = process.env.AGENTOS_MODEL_DIR || path.join(app.getPath('userData'), 'modeller');
    const model = ayarlar().sesModeli || 'Xenova/whisper-base';
    return T.pipeline('automatic-speech-recognition', model, {
      dtype: 'q8',
      progress_callback: (p) => {
        if (pencere && !pencere.isDestroyed() && p.status === 'progress' && /encoder|decoder/.test(p.file || ''))
          pencere.webContents.send('ses:ilerleme', { dosya: p.file, yuzde: Math.round(p.progress || 0) });
      },
    });
  })();
  tanima.catch(() => { tanima = null; });   // hata olursa sonraki denemede yeniden yüklensin
  return tanima;
}

ipcMain.handle('ses:hazirla', async () => {
  try { await tanimaYukle(); return { tamam: true }; }
  catch (e) { return { tamam: false, hata: String(e && e.message || e) }; }
});

ipcMain.handle('ses:cevir', (_olay, tampon) => {
  // Çözümlemeler sırayla yürür; aynı anda iki istek modeli bozmasın.
  const is = sira.then(async () => {
    const asr = await tanimaYukle();
    const ses = new Float32Array(tampon);
    const sonuc = await asr(ses, { language: 'turkish', task: 'transcribe' });
    return { metin: (sonuc.text || '').trim() };
  }).catch((e) => ({ metin: '', hata: String(e && e.message || e) }));
  sira = is;
  return is;
});

// ---------------------------------------------------------------- sohbet modeli (isteğe bağlı)
ipcMain.handle('sohbet:sor', async (_olay, gecmis) => {
  const a = ayarlar().sohbet;
  if (!a || !a.adres || !a.model) return { yok: true };
  const anahtar = a.anahtarDegiskeni ? process.env[a.anahtarDegiskeni] : '';
  try {
    const yanit = await fetch(a.adres.replace(/\/$/, '') + '/chat/completions', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' },
        anahtar ? { Authorization: 'Bearer ' + anahtar } : {}),
      body: JSON.stringify({
        model: a.model,
        messages: [{ role: 'system', content:
          'Sen AgentOS Supreme adlı sesli bir asistansın. Türkçe, doğal ve kısa konuş: en çok iki üç ' +
          'cümle. Yanıtın sesli okunacak; liste, madde imi, emoji ya da biçimlendirme kullanma.' }]
          .concat(Array.isArray(gecmis) ? gecmis.slice(-12) : []),
      }),
      signal: AbortSignal.timeout(30000),
    });
    if (!yanit.ok) return { hata: 'Sohbet modeli ' + yanit.status + ' döndürdü' };
    const veri = await yanit.json();
    return { metin: (veri.choices && veri.choices[0] && veri.choices[0].message.content || '').trim() };
  } catch (e) {
    return { hata: String(e && e.message || e) };
  }
});

ipcMain.handle('uygulama:kapat', () => app.quit());

// ---------------------------------------------------------------- yaşam döngüsü
const tek = app.requestSingleInstanceLock();
if (!tek) app.quit();
else {
  app.on('second-instance', () => { if (pencere) { pencere.show(); pencere.focus(); } });
  app.whenReady().then(() => {
    // Yalnızca kendi sayfamıza ve yalnızca mikrofon için izin ver.
    const bizim = (wc) => !!wc && wc.getURL().startsWith('file://');
    session.defaultSession.setPermissionRequestHandler((wc, izin, karar) => karar(bizim(wc) && izin === 'media'));
    session.defaultSession.setPermissionCheckHandler((wc, izin) => bizim(wc) && izin === 'media');
    pencereAc();
  });
  app.on('window-all-closed', () => app.quit());
}
