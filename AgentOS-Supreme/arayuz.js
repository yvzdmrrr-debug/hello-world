// AgentOS Supreme — arayüz: parçacık çekirdeği, ses, konuşma, üretilen paneller, onaylar.
(() => {
  'use strict';
  const M = window.Mantik;
  const kopru = window.agentos || null;         // Electron köprüsü (tarayıcıda yok)
  const $ = (id) => document.getElementById(id);
  const durum = { uyanik: false, onayAcik: false, panelAcik: false, konusuyor: false };
  const gunluk = [];                            // söylenenler (test ve hata ayıklama için)

  // ============================================================ parçacık çekirdeği
  const tuval = $('sahne'), c = tuval.getContext('2d');
  const N = 6500, BANT = 32;
  const ev = new Float32Array(N * 3), dagin = new Float32Array(N * 3);
  const gecikme = new Float32Array(N), faz = new Float32Array(N), bant = new Uint8Array(N), tur = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    const r = Math.random();
    let x, y, z;
    if (r < 0.68) {                                           // dış küre (Fibonacci dağılımı)
      const k = i + 0.5, phi = Math.acos(1 - 2 * k / N), th = Math.PI * (1 + Math.sqrt(5)) * k;
      x = Math.sin(phi) * Math.cos(th); y = Math.cos(phi); z = Math.sin(phi) * Math.sin(th); tur[i] = 0;
    } else if (r < 0.86) {                                    // halkalar
      const a = Math.random() * Math.PI * 2, rr = 1.32 + (Math.random() < 0.5 ? 0 : 0.22) + (Math.random() - 0.5) * 0.03;
      x = Math.cos(a) * rr; z = Math.sin(a) * rr; y = (Math.random() - 0.5) * 0.03; tur[i] = 1;
    } else {                                                  // iç çekirdek
      const a = Math.random() * Math.PI * 2, b = Math.acos(2 * Math.random() - 1), rr = 0.38 * Math.cbrt(Math.random());
      x = Math.sin(b) * Math.cos(a) * rr; y = Math.cos(b) * rr; z = Math.sin(b) * Math.sin(a) * rr; tur[i] = 2;
    }
    ev.set([x, y, z], i * 3);
    dagin.set([(Math.random() - 0.5) * 7, (Math.random() - 0.5) * 4.4, (Math.random() - 0.5) * 5], i * 3);
    gecikme[i] = Math.random(); faz[i] = Math.random() * Math.PI * 2;
    bant[i] = Math.min(BANT - 1, Math.floor((Math.acos(Math.max(-1, Math.min(1, y))) / Math.PI) * BANT));
  }
  const RENK = ['90,215,255', '157,123,255', '230,250,255'];
  const seviye = new Float32Array(BANT);
  let W = 0, H = 0, olusum = 0, hedefOlusum = 0, genel = 0, analizor = null, frekans = null;

  function boyut() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = tuval.width = Math.floor(innerWidth * dpr); H = tuval.height = Math.floor(innerHeight * dpr);
  }
  addEventListener('resize', boyut); boyut();

  function ciz(simdi) {
    const t = simdi / 1000;
    olusum += (hedefOlusum - olusum) * 0.018;
    // ses tayfı → bant seviyeleri (asistan konuşurken yapay bir zarf eklenir)
    let toplam = 0;
    if (analizor) analizor.getByteFrequencyData(frekans);
    for (let b = 0; b < BANT; b++) {
      let v = analizor ? frekans[2 + b * 2] / 255 : 0;
      if (durum.konusuyor) v = Math.max(v, 0.28 + 0.26 * Math.sin(t * 11 + b * 0.55) * Math.sin(t * 3.1 + b));
      seviye[b] += (v - seviye[b]) * (v > seviye[b] ? 0.5 : 0.12);
      toplam += seviye[b];
    }
    genel += (toplam / BANT - genel) * 0.2;

    c.globalCompositeOperation = 'source-over';
    c.fillStyle = 'rgba(2,4,10,0.34)'; c.fillRect(0, 0, W, H);       // hafif iz bırakır
    c.globalCompositeOperation = 'lighter';
    const R = Math.min(W, H) * 0.2 * (durum.panelAcik ? 0.86 : 1);
    const mx = W * (durum.panelAcik && innerWidth > 900 ? 0.36 : 0.5), my = H * 0.47, odak = R * 4.2;
    const ay = t * 0.22, ax = 0.38 + Math.sin(t * 0.17) * 0.08;
    const ca = Math.cos(ay), sa = Math.sin(ay), cb = Math.cos(ax), sb = Math.sin(ax);
    for (let i = 0; i < N; i++) {
      const j = i * 3;
      let f = (olusum * 1.6 - gecikme[i] * 0.6);                     // parçacıklar sırayla yerine oturur
      f = f <= 0 ? 0 : f >= 1 ? 1 : f * f * (3 - 2 * f);
      const s = seviye[bant[i]];
      const nab = tur[i] === 0 ? 1 + s * 0.42 + genel * 0.1 : tur[i] === 1 ? 1 + genel * 0.25 : 1 + genel * 1.3;
      const dal = Math.sin(t * 0.6 + faz[i]) * 0.06;
      let x = dagin[j] + Math.sin(t * 0.21 + faz[i]) * 0.12, y = dagin[j + 1] + dal, z = dagin[j + 2];
      let hx = ev[j] * nab, hy = ev[j + 1] * nab, hz = ev[j + 2] * nab;
      if (tur[i] === 1) {                                            // halkalar ayrı eksende döner
        const q = t * 0.5 + (ev[j] * ev[j] + ev[j + 2] * ev[j + 2] > 2 ? 1.2 : 0);
        const cq = Math.cos(q), sq = Math.sin(q), tx = hx * cq - hz * sq; hz = hx * sq + hz * cq; hx = tx;
      }
      const rx = hx * ca - hz * sa, rz = hx * sa + hz * ca, ry = hy * cb - rz * sb, rz2 = hy * sb + rz * cb;
      x += (rx - x) * f; y += (ry - y) * f; z += (rz2 - z) * f;
      const olcek = odak / (odak + z * R);
      const px = mx + x * R * olcek, py = my + y * R * olcek;
      if (px < 0 || px > W || py < 0 || py > H) continue;
      const pir = 0.5 + 0.5 * Math.sin(t * 1.7 + faz[i] * 3);
      const alfa = (0.16 + 0.2 * pir) * (1 - f) + f * (0.34 + 0.5 * (1 - (z + 1.6) / 3.2)) * (0.55 + s * 0.9 + genel * 0.6);
      const boy = Math.max(1, (tur[i] === 2 ? 2.2 : 1.6) * olcek * (W / 1920) * (1 + s * 0.8));
      c.fillStyle = 'rgba(' + RENK[tur[i]] + ',' + Math.min(1, alfa).toFixed(3) + ')';
      c.fillRect(px, py, boy, boy);
    }
    requestAnimationFrame(ciz);
  }
  requestAnimationFrame(ciz);

  // ============================================================ durum göstergeleri
  const DURUM = { hazir: 'Hazır', dinliyor: 'Dinliyor', dusunuyor: 'Çözümlüyor', konusuyor: 'Konuşuyor' };
  function durumYaz(d) { $('durum').dataset.d = d; $('durum').textContent = DURUM[d] || d; }
  setInterval(() => {
    $('saat').textContent = new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) + ' · AgentOS Supreme';
  }, 1000);

  // ============================================================ konuşma (TTS) ve söz kesme
  let sesler = [], sahteZaman = null;
  const sesleriAl = () => { sesler = window.speechSynthesis ? speechSynthesis.getVoices() : []; };
  if (window.speechSynthesis) { sesleriAl(); speechSynthesis.onvoiceschanged = sesleriAl; }

  function sesSec() {
    const tr = sesler.filter((s) => /^tr/i.test(s.lang));
    return tr.find((s) => /natural|online|neural/i.test(s.name)) || tr[0] || null;
  }

  function sustur() {
    // Kullanıcı konuşmaya başladı: asistan o anda susar.
    if (window.speechSynthesis) speechSynthesis.cancel();
    clearTimeout(sahteZaman);
    const kesildi = durum.konusuyor;
    durum.konusuyor = false;
    if (kesildi) { $('oMetin').style.opacity = 0.35; gunluk.push({ olay: 'kesildi', zaman: performance.now() }); }
    return kesildi;
  }

  function soyle(metin) {
    sustur();
    gunluk.push({ olay: 'soyle', metin, zaman: performance.now() });
    $('oMetin').textContent = metin; $('oMetin').style.opacity = 1;
    durum.konusuyor = true; durumYaz('konusuyor');
    const bitti = () => { if (durum.konusuyor) { durum.konusuyor = false; durumYaz(durum.uyanik ? 'dinliyor' : 'hazir'); } };
    const ses = sesSec();
    if (window.speechSynthesis && ses) {
      const u = new SpeechSynthesisUtterance(metin);
      u.voice = ses; u.lang = ses.lang; u.rate = 1.04; u.pitch = 1;
      u.onend = bitti; u.onerror = bitti;
      speechSynthesis.speak(u);
    } else {
      // Türkçe ses yüklü değil: yalnızca altyazı gösterilir, süre metin uzunluğuna göre ayarlanır.
      sahteZaman = setTimeout(bitti, Math.min(9000, 900 + metin.length * 55));
    }
  }

  // ============================================================ mikrofon, konuşma algılama, tanıma
  const algilayici = M.Algilayici();
  let ornekHizi = 48000, onKayit = [], kayit = null, cozumSayisi = 0;

  function kare(veri, hiz) {
    let k = 0;
    for (let i = 0; i < veri.length; i++) k += veri[i] * veri[i];
    const rms = Math.sqrt(k / veri.length), ms = veri.length / hiz * 1000;
    const olay = algilayici.besle(rms, ms, durum.konusuyor);
    const kopya = new Float32Array(veri);
    if (olay === 'basladi') {
      sustur();                                              // SÖZ KESME: aynı ses karesinde
      kayit = onKayit.slice(); onKayit = [];
      if (durum.uyanik) durumYaz('dinliyor');
    }
    if (kayit) kayit.push(kopya);
    else { onKayit.push(kopya); if (onKayit.length * ms > 400) onKayit.shift(); }
    if (olay === 'bitti' && kayit) {
      const parcalar = kayit; kayit = null;
      const boy = parcalar.reduce((a, p) => a + p.length, 0);
      if (boy / hiz < 0.3) return;                           // çok kısa: tık, öksürük
      const tam = new Float32Array(boy);
      let o = 0; for (const p of parcalar) { tam.set(p, o); o += p.length; }
      cozumle(M.ornekle16k(tam, hiz));
    }
  }

  const BOS = /^\W*$|altyaz|abone ol|izlediğiniz için|betimleme|\bTRT\b|\[[^\]]*\]|\([^)]*\)/i;   // sessizlikte uydurulan metinler
  async function cozumle(ses16k) {
    if (!kopru) return;
    const sira = ++cozumSayisi;
    if (durum.uyanik) durumYaz('dusunuyor');
    const r = await kopru.sesCevir(ses16k);
    gunluk.push({ olay: 'duydu', metin: r.metin, hata: r.hata, sure: +(ses16k.length / 16000).toFixed(2) });
    if (sira !== cozumSayisi && !r.metin) return;
    if (durum.uyanik && !durum.konusuyor) durumYaz('dinliyor');
    if (r.hata) { $('hazirlik').textContent = 'Ses tanıma hatası: ' + r.hata; return; }
    if (!r.metin || BOS.test(r.metin)) return;
    isle(r.metin);
  }

  async function sesBaslat() {
    try {
      const akis = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
      const actx = new (window.AudioContext || window.webkitAudioContext)();
      ornekHizi = actx.sampleRate;
      const kaynak = actx.createMediaStreamSource(akis);
      analizor = actx.createAnalyser(); analizor.fftSize = 256; analizor.smoothingTimeConstant = 0.6;
      frekans = new Uint8Array(analizor.frequencyBinCount);
      kaynak.connect(analizor);
      const islemci = actx.createScriptProcessor(1024, 1, 1);       // ~21 ms'lik kareler
      const sessiz = actx.createGain(); sessiz.gain.value = 0;
      kaynak.connect(islemci); islemci.connect(sessiz); sessiz.connect(actx.destination);
      islemci.onaudioprocess = (e) => kare(e.inputBuffer.getChannelData(0), ornekHizi);
      const surdur = () => { if (actx.state === 'suspended') actx.resume(); };
      addEventListener('pointerdown', surdur); surdur();
      return true;
    } catch (e) {
      $('hazirlik').textContent = 'Mikrofona erişilemedi; tıklayarak ve yazarak kullanabilirsiniz.';
      return false;
    }
  }

  // ============================================================ uyanış / uyku
  function uyan() {
    if (durum.uyanik) return;
    durum.uyanik = true; hedefOlusum = 1;
    document.body.classList.add('uyanik');
    const s = new Date().getHours();
    soyle((s < 6 ? 'İyi geceler' : s < 12 ? 'Günaydın' : s < 18 ? 'İyi günler' : 'İyi akşamlar') +
      '. AgentOS Supreme hazır. Sizi dinliyorum.');
  }
  function uyu() {
    panelKapat(true);
    durum.uyanik = false; hedefOlusum = 0;
    document.body.classList.remove('uyanik');
    $('senMetin').textContent = ''; durumYaz('hazir');
  }

  // ============================================================ üretilen Binance paneli
  const UCLAR = ['wss://stream.binance.com:443/stream?streams=', 'wss://data-stream.binance.vision/stream?streams='];
  let panel = null;

  function panelKapat(sessizce) {
    if (!panel) return false;
    const p = panel; panel = null; durum.panelAcik = false;
    p.acik = false; clearTimeout(p.zaman);
    if (p.ws) { p.ws.onclose = null; try { p.ws.close(); } catch (_) { /* zaten kapalı */ } }
    p.kok.classList.add('kapaniyor');
    setTimeout(() => p.kok.remove(), 450);
    if (!sessizce) soyle('Paneli kapattım.');
    return true;
  }

  function el(etiket, sinif, metin) {
    const e = document.createElement(etiket);
    if (sinif) e.className = sinif;
    if (metin !== undefined) e.textContent = metin;
    return e;
  }

  function panelOlustur(semboller) {
    panelKapat(true);
    const kok = el('section', 'panel');
    const bas = el('header'); const baslik = el('b', '', 'Binance · Canlı analiz'); const rozet = el('span', 'canli kopuk', 'Bağlanıyor');
    bas.append(baslik, rozet); kok.append(bas);
    const p = { kok, rozet, kartlar: {}, acik: true, deneme: 0, ws: null, zaman: null, ozetlendi: false, semboller };
    semboller.forEach((s, i) => {
      const bilgi = M.PARALAR.find((x) => x.sembol === s) || { ad: s, kisa: s.replace('USDT', '') };
      const kart = el('div', 'kart'); kart.style.animationDelay = (0.12 + i * 0.09) + 's';
      const ad = el('div', 'ad'); ad.append(el('b', '', bilgi.kisa), document.createTextNode(bilgi.ad + ' / USDT'));
      const fiyat = el('div', 'fiyat', '—'), degisim = el('div', 'degisim', '—');
      const grafik = el('canvas'); grafik.width = 440; grafik.height = 76;
      const alt = el('div', 'alt'); const dusuk = el('span', '', 'En düşük —'), yuksek = el('span', '', 'En yüksek —'), hacim = el('span', '', 'Hacim —');
      alt.append(dusuk, yuksek, hacim);
      kart.append(ad, fiyat, degisim, grafik, alt); kok.append(kart);
      p.kartlar[s] = { bilgi, fiyat, degisim, grafik, dusuk, yuksek, hacim, seri: [], son: null, yuzde: null };
    });
    p.ozet = el('footer', '', 'Veri bekleniyor…'); kok.append(p.ozet);
    $('paneller').append(kok);
    panel = p; durum.panelAcik = true;
    baglan(p, 0);
    return p;
  }

  function baglan(p, uc) {
    if (!p.acik) return;
    const ws = new WebSocket(UCLAR[uc % UCLAR.length] + p.semboller.map((s) => s.toLowerCase() + '@ticker').join('/'));
    p.ws = ws;
    ws.onopen = () => { p.deneme = 0; p.rozet.textContent = 'Canlı'; p.rozet.classList.remove('kopuk'); };
    ws.onmessage = (olay) => {
      let d; try { d = JSON.parse(olay.data).data; } catch (_) { return; }
      if (d && p.kartlar[d.s]) kartGuncelle(p, p.kartlar[d.s], d);
    };
    ws.onclose = () => {
      if (!p.acik) return;
      p.rozet.textContent = 'Yeniden bağlanıyor'; p.rozet.classList.add('kopuk');
      p.zaman = setTimeout(() => baglan(p, uc + 1), Math.min(10000, 800 * Math.pow(2, p.deneme++)));
    };
    ws.onerror = () => { try { ws.close(); } catch (_) { /* onclose yeniden dener */ } };
  }

  function kartGuncelle(p, k, d) {
    const fiyat = Number(d.c), yuzde = Number(d.P);
    k.fiyat.textContent = M.bicim(fiyat);
    if (k.son !== null && fiyat !== k.son) {
      k.fiyat.classList.remove('yukari', 'asagi');
      k.fiyat.classList.add(fiyat > k.son ? 'yukari' : 'asagi');
      clearTimeout(k.zaman); k.zaman = setTimeout(() => k.fiyat.classList.remove('yukari', 'asagi'), 700);
    }
    k.son = fiyat; k.yuzde = yuzde;
    k.degisim.textContent = (yuzde >= 0 ? '▲ +' : '▼ ') + yuzde.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%  (24s)';
    k.degisim.className = 'degisim ' + (yuzde >= 0 ? 'arti' : 'eksi');
    k.dusuk.textContent = 'En düşük ' + M.bicim(d.l); k.yuksek.textContent = 'En yüksek ' + M.bicim(d.h);
    k.hacim.textContent = 'Hacim ' + (Number(d.q) / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 1 }) + ' M $';
    k.seri.push(fiyat); if (k.seri.length > 120) k.seri.shift();
    grafikCiz(k);
    const dolu = Object.values(p.kartlar).filter((x) => x.yuzde !== null);
    if (dolu.length) {
      const sirali = dolu.slice().sort((a, b) => b.yuzde - a.yuzde), yz = (v) => (v >= 0 ? '+' : '') + v.toFixed(2).replace('.', ',') + '%';
      p.ozet.textContent = (dolu.length > 1
        ? 'En güçlü: ' + sirali[0].bilgi.kisa + ' ' + yz(sirali[0].yuzde) + '  ·  En zayıf: ' + sirali[sirali.length - 1].bilgi.kisa + ' ' + yz(sirali[sirali.length - 1].yuzde) + '  ·  '
        : '') + 'Gecikme ' + Math.max(0, Date.now() - d.E) + ' ms  ·  Kaynak: Binance WebSocket';
    }
    if (!p.ozetlendi && dolu.length === p.semboller.length) {   // ilk tam veride sesli özet
      p.ozetlendi = true;
      const ilk = p.kartlar[p.semboller[0]];
      soyle(ilk.bilgi.ad + ' şu an ' + M.bicim(ilk.son) + ' dolar; son yirmi dört saatte yüzde ' +
        Math.abs(ilk.yuzde).toFixed(1).replace('.', ',') + (ilk.yuzde >= 0 ? ' yükseldi.' : ' geriledi.'));
    }
  }

  function grafikCiz(k) {
    const g = k.grafik.getContext('2d'), w = k.grafik.width, h = k.grafik.height, s = k.seri;
    g.clearRect(0, 0, w, h);
    if (s.length < 2) return;
    const enaz = Math.min(...s), encok = Math.max(...s), aralik = encok - enaz || 1;
    const renk = s[s.length - 1] >= s[0] ? '62,240,166' : '255,93,122';
    g.beginPath();
    s.forEach((v, i) => { const x = i / (s.length - 1) * w, y = h - 6 - (v - enaz) / aralik * (h - 12); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.strokeStyle = 'rgba(' + renk + ',.95)'; g.lineWidth = 2; g.stroke();
    g.lineTo(w, h); g.lineTo(0, h); g.closePath();
    g.fillStyle = 'rgba(' + renk + ',.12)'; g.fill();
  }

  // ============================================================ onay penceresi (fare + ses + klavye)
  let onay = null;
  function onayIste(baslik, aciklama, evetIslem, evetYanit, hayirYanit) {
    if (onay) onayKapat(false, true);
    const katman = el('div'); katman.id = 'onayKatman';
    const kutu = el('div', 'onay');
    const evet = el('button', 'evet', 'Onayla'), hayir = el('button', '', 'İptal et');
    const dugmeler = el('div', 'dugmeler'); dugmeler.append(evet, hayir);
    kutu.append(el('h2', '', baslik), el('p', '', aciklama), el('div', 'ipucu', '"Onayla" / "Evet"  ·  "İptal et" / "Kapat"'), dugmeler);
    katman.append(kutu); document.body.append(katman);
    onay = { katman, evetIslem, evetYanit, hayirYanit };
    durum.onayAcik = true;
    evet.onclick = () => onayKapat(true); hayir.onclick = () => onayKapat(false);
    soyle(baslik + ' Onaylıyor musunuz?');
  }
  function onayKapat(kabul, sessizce) {
    if (!onay) return;
    const o = onay; onay = null; durum.onayAcik = false;
    o.katman.classList.add('kapaniyor');
    setTimeout(() => o.katman.remove(), 420);
    if (!sessizce) soyle(kabul ? o.evetYanit : o.hayirYanit);
    if (kabul && o.evetIslem) o.evetIslem();
  }

  // ============================================================ komut işleme
  const gecmis = [];
  async function isle(metin) {
    const n = M.niyet(metin, durum);
    if (n.tur === 'yok') return n;
    if (n.tur !== 'uyan') $('senMetin').textContent = '“' + String(metin).trim() + '”';
    switch (n.tur) {
      case 'uyan': uyan(); break;
      case 'onayla': onayKapat(true); break;
      case 'reddet': onayKapat(false); break;
      case 'onayBekliyor': soyle('Onay bekliyorum. Onayla ya da iptal et diyebilirsiniz.'); break;
      case 'analiz': {
        const adlar = n.semboller.map((s) => (M.PARALAR.find((x) => x.sembol === s) || {}).ad || s);
        panelOlustur(n.semboller);
        soyle(adlar.length > 3 ? 'Binance canlı analiz panelini hazırlıyorum.' : adlar.join(' ve ') + ' için canlı paneli hazırlıyorum.');
        break;
      }
      case 'panelKapat': if (!panelKapat(false)) soyle('Açık bir panel yok.'); break;
      case 'islem': {
        const ad = (M.PARALAR.find((x) => x.sembol === n.sembol) || {}).ad || n.sembol;
        onayIste('Sanal işlem: ' + ad + ' ' + (n.yon === 'AL' ? 'alımı' : 'satışı'),
          'Bu bir benzetimdir; borsaya gerçek emir gönderilmez.',
          () => {
            const kayitlar = JSON.parse(localStorage.getItem('sanalIslemler') || '[]');
            kayitlar.push({ zaman: new Date().toISOString(), sembol: n.sembol, yon: n.yon,
              fiyat: panel && panel.kartlar[n.sembol] ? panel.kartlar[n.sembol].son : null });
            localStorage.setItem('sanalIslemler', JSON.stringify(kayitlar.slice(-200)));
          }, 'Onaylandı. Sanal işlem kaydedildi.', 'İptal edildi. İşlem yapılmadı.');
        break;
      }
      case 'cikis':
        onayIste('AgentOS Supreme kapatılsın mı?', 'Uygulama kapanacak.',
          () => setTimeout(() => (kopru ? kopru.kapat() : window.close()), 1600), 'Kapatıyorum. Görüşmek üzere.', 'Vazgeçildi. Buradayım.');
        break;
      case 'uyu': soyle('Bekleme moduna geçiyorum.'); setTimeout(uyu, 1800); break;
      case 'saat': soyle('Saat ' + new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) + '.'); break;
      case 'tarih': soyle('Bugün ' + new Date().toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) + '.'); break;
      case 'selam': soyle('Merhaba. Size nasıl yardımcı olabilirim?'); break;
      case 'hal': soyle('Bütün sistemlerim çalışıyor, teşekkür ederim. Sizin için ne yapabilirim?'); break;
      case 'tesekkur': soyle('Rica ederim.'); break;
      case 'yardim': soyle('Binance analizini getir, bitcoin fiyatı, paneli kapat, saat kaç ya da uygulamayı kapat diyebilirsiniz.'); break;
      case 'sohbet': {
        if (!kopru) { soyle('Bunu henüz yapamıyorum. Binance analizini getir ya da saat kaç diyebilirsiniz.'); break; }
        durumYaz('dusunuyor');
        gecmis.push({ role: 'user', content: n.metin });
        const r = await kopru.sohbet(gecmis);
        if (r.metin) { gecmis.push({ role: 'assistant', content: r.metin }); soyle(r.metin); }
        else {
          gecmis.pop();
          soyle(r.yok ? 'Bunu henüz yapamıyorum. Binance analizini getir ya da saat kaç diyebilirsiniz.'
            : 'Sohbet modeline ulaşamadım.');
        }
        break;
      }
    }
    return n;
  }

  // ============================================================ fare ve klavye
  $('karsilama').addEventListener('click', uyan);
  $('komut').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.value.trim()) { isle(e.target.value); e.target.value = ''; }
    e.stopPropagation();
  });
  addEventListener('keydown', (e) => {
    if (onay) { if (e.key === 'Enter') onayKapat(true); else if (e.key === 'Escape') onayKapat(false); return; }
    if (e.key === 'Escape') {
      if (!durum.uyanik) uyan();
      onayIste('AgentOS Supreme kapatılsın mı?', 'Uygulama kapanacak.',
        () => setTimeout(() => (kopru ? kopru.kapat() : window.close()), 1600), 'Kapatıyorum. Görüşmek üzere.', 'Vazgeçildi. Buradayım.');
    } else if (!durum.uyanik && (e.key === 'Enter' || e.key === ' ')) uyan();
  });

  // ============================================================ başlangıç
  (async () => {
    const mikrofon = await sesBaslat();
    if (!kopru) return;
    kopru.sesIlerleme((v) => { $('hazirlik').textContent = 'Ses modeli indiriliyor… %' + v.yuzde; });
    if (mikrofon) $('hazirlik').textContent = 'Ses tanıma hazırlanıyor…';
    const r = await kopru.sesHazirla();
    if (mikrofon) $('hazirlik').textContent = r.tamam ? 'Dinliyorum' : 'Ses tanıma yüklenemedi (' + r.hata + '); tıklayarak ve yazarak kullanabilirsiniz.';
  })();

  window.__agentos = { durum, isle, kare, gunluk, soyle, get panel() { return panel; } };
})();
