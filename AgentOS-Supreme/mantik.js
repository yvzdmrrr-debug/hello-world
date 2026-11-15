// AgentOS Supreme — komut anlama mantığı (arayüzden bağımsız, Node ile test edilebilir).
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Mantik = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const HARF = { 'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u', 'â': 'a', 'î': 'i', 'û': 'u' };

  // Küçük harf, Türkçe karakterler sadeleşmiş, noktalama atılmış metin.
  function sade(metin) {
    return String(metin || '').toLocaleLowerCase('tr-TR')
      .replace(/[çğıöşüâîû]/g, (h) => HARF[h])
      .replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function mesafe(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++)
      for (let j = 1; j <= b.length; j++)
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[a.length][b.length];
  }

  // Ses tanıma hatalarına dayanıklı eşleşme: metnin içinde kelime (ya da kelime grubu) geçiyor mu?
  function gecer(metin, kalip, tolerans) {
    const m = sade(metin), k = sade(kalip);
    if (!m || !k) return false;
    if ((' ' + m + ' ').includes(' ' + k + ' ')) return true;
    const pay = tolerans === undefined ? (k.length >= 6 ? 2 : k.length >= 4 ? 1 : 0) : tolerans;
    if (!pay) return false;
    const kelimeler = m.split(' '), n = k.split(' ').length;
    for (let i = 0; i < kelimeler.length; i++)
      for (const boy of [n, n + 1]) {
        const parca = kelimeler.slice(i, i + boy).join('');
        if (parca && Math.abs(parca.length - k.replace(/ /g, '').length) <= pay &&
            mesafe(parca, k.replace(/ /g, '')) <= pay) return true;
      }
    return false;
  }

  const herhangi = (metin, liste, tolerans) => liste.some((k) => gecer(metin, k, tolerans));

  const PARALAR = [
    { sembol: 'BTCUSDT', ad: 'Bitcoin', kisa: 'BTC', soz: ['bitcoin', 'btc', 'bitkoin', 'bitjoin', 'bit join', 'bitgon', 'bitkoyn'] },
    { sembol: 'ETHUSDT', ad: 'Ethereum', kisa: 'ETH', soz: ['ethereum', 'eth', 'eterim', 'etereum', 'ether'] },
    { sembol: 'BNBUSDT', ad: 'BNB', kisa: 'BNB', soz: ['bnb', 'binance coin'] },
    { sembol: 'SOLUSDT', ad: 'Solana', kisa: 'SOL', soz: ['solana', 'sol'] },
    { sembol: 'XRPUSDT', ad: 'XRP', kisa: 'XRP', soz: ['xrp', 'ripple', 'ripıl'] },
    { sembol: 'DOGEUSDT', ad: 'Dogecoin', kisa: 'DOGE', soz: ['dogecoin', 'doge', 'doc', 'dojkoin'] },
    { sembol: 'ADAUSDT', ad: 'Cardano', kisa: 'ADA', soz: ['cardano', 'ada', 'kardano'] },
    { sembol: 'AVAXUSDT', ad: 'Avalanche', kisa: 'AVAX', soz: ['avalanche', 'avax', 'avalans'] },
  ];
  const VARSAYILAN = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT'];

  function paralar(metin) {
    return PARALAR.filter((p) => herhangi(metin, p.soz, undefined)).map((p) => p.sembol);
  }

  const UYANIS = ['hey agentos', 'agentos', 'agent os', 'ajan os', 'hey ajan', 'hey agent', 'eycint',
    'hey ayant', 'ayen tos', 'agent o s', 'ecint os', 'uyan'];
  const ONAY = ['onayla', 'onay', 'evet', 'tamam', 'kabul', 'onayliyorum', 'ona ile', 'ona ila'];
  const RED = ['iptal et', 'iptal', 'hayir', 'kapat', 'vazgec', 'reddet', 'istemiyorum'];

  /**
   * Metni niyete çevirir. durum: { uyanik, onayAcik, panelAcik }
   * Dönen: { tur, ... }  tur ∈ uyan | onayla | reddet | analiz | panelKapat | islem | cikis |
   *                             uyu | saat | tarih | selam | hal | tesekkur | yardim | sohbet | yok
   */
  function niyet(metin, durum) {
    const d = durum || {};
    const m = sade(metin);
    if (!m) return { tur: 'yok' };
    if (!d.uyanik) {
      // Kısa bir seslenme ("hey …") ya da asistanın adına benzeyen bir kelime uyandırır.
      const kelime = m.split(' ');
      const hey = /^(hey|hei|ey|hay)$/.test(kelime[0]) && kelime.length >= 2 && kelime.length <= 5;
      const ad = kelime.length <= 6 && kelime.some((k) => /^(agent|ayent|ayant|ajan|ajah|eycint|ecint|eycent)/.test(k));
      return hey || ad || herhangi(m, UYANIS) ? { tur: 'uyan' } : { tur: 'yok' };
    }
    if (d.onayAcik) {
      if (herhangi(m, RED)) return { tur: 'reddet' };       // "iptal et" önce: güvenli taraf
      if (herhangi(m, ONAY)) return { tur: 'onayla' };
      return { tur: 'onayBekliyor' };
    }
    if (herhangi(m, ['programi kapat', 'cikis yap', 'sistemi kapat', 'kendini kapat']) || gecer(m, 'uygulamayi kapat', 3))
      return { tur: 'cikis' };
    const coin = paralar(m);
    const yon = /(^| )(satin al|al|alim)( |$)/.test(m) ? 'AL' : /(^| )(sat|satis)( |$)/.test(m) ? 'SAT' : null;
    if (yon && coin.length && !herhangi(m, ['analiz', 'fiyat', 'goster'])) return { tur: 'islem', yon, sembol: coin[0] };
    if (herhangi(m, ['paneli kapat', 'analizi kapat', 'ekrani temizle', 'paneli kaldir']) ||
        (d.panelAcik && herhangi(m, ['kapat', 'kaldir', 'gizle']))) return { tur: 'panelKapat' };
    const binance = /(^| )(bina?n[cs]|ba[iy]n)/.test(m);          // "binans", "baynens", "baina" …
    if (coin.length || binance || herhangi(m, ['analiz', 'piyasa', 'kripto', 'fiyatlar', 'borsa']) || /analiz/.test(m))
      return { tur: 'analiz', semboller: coin.length ? coin : VARSAYILAN };
    if (herhangi(m, ['uyu', 'bekleme moduna gec', 'gorusuruz', 'iyi geceler', 'hosca kal'])) return { tur: 'uyu' };
    if (herhangi(m, ['saat kac', 'saat'])) return { tur: 'saat' };
    if (herhangi(m, ['bugun gunlerden ne', 'tarih', 'bugun ayin kaci', 'hangi gun'])) return { tur: 'tarih' };
    if (herhangi(m, ['nasilsin', 'naber', 'ne haber', 'iyi misin'])) return { tur: 'hal' };
    if (herhangi(m, ['merhaba', 'selam', 'gunaydin', 'iyi aksamlar', 'hey'])) return { tur: 'selam' };
    if (herhangi(m, ['tesekkur', 'tesekkurler', 'sag ol', 'eyvallah'])) return { tur: 'tesekkur' };
    if (herhangi(m, ['ne yapabilirsin', 'yardim', 'komutlar', 'neler yapabilirsin'])) return { tur: 'yardim' };
    return { tur: 'sohbet', metin: String(metin).trim() };
  }

  function bicim(sayi) {
    const n = Number(sayi);
    if (!isFinite(n)) return '—';
    const basamak = n >= 1000 ? 2 : n >= 1 ? 3 : 5;
    return n.toLocaleString('tr-TR', { minimumFractionDigits: basamak, maximumFractionDigits: basamak });
  }

  // Ses tanıma için 16 kHz'e doğrusal yeniden örnekleme.
  function ornekle16k(veri, hiz) {
    if (hiz === 16000) return veri;
    const n = Math.round(veri.length * 16000 / hiz), cikti = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = i * hiz / 16000, j = Math.floor(x), k = Math.min(j + 1, veri.length - 1);
      cikti[i] = veri[j] + (veri[k] - veri[j]) * (x - j);
    }
    return cikti;
  }

  /**
   * Enerji tabanlı konuşma algılayıcı. Her ses karesi için besle(rms, ms) çağrılır.
   * Olaylar: 'basladi' (kullanıcı konuşmaya başladı → söz kesme), 'bitti' (sessizlik → çözümle).
   * asistanKonusuyor iken eşik yükselir ki hoparlör yankısı yanlışlıkla sözü kesmesin.
   */
  function Algilayici(ayar) {
    const a = Object.assign({ taban: 0.004, enAz: 0.012, kat: 3, baslaKare: 2, yankiKat: 1.8,
      yankiKare: 3, sessizlikMs: 700, enUzunMs: 12000 }, ayar || {});
    let zemin = a.taban, ust = 0, konusma = false, sessiz = 0, sure = 0;
    return {
      get konusuyor() { return konusma; },
      get esik() { return Math.max(a.enAz, zemin * a.kat); },
      besle(rms, ms, asistanKonusuyor) {
        const esik = this.esik * (asistanKonusuyor ? a.yankiKat : 1);
        const gerek = asistanKonusuyor ? a.yankiKare : a.baslaKare;
        if (!konusma) {
          if (rms > esik) { if (++ust >= gerek) { konusma = true; sessiz = 0; sure = 0; ust = 0; return 'basladi'; } }
          else { ust = 0; zemin = zemin * 0.97 + rms * 0.03; }
          return null;
        }
        sure += ms;
        sessiz = rms > this.esik * 0.6 ? 0 : sessiz + ms;
        if (sessiz >= a.sessizlikMs || sure >= a.enUzunMs) { konusma = false; return 'bitti'; }
        return null;
      },
    };
  }

  return { sade, mesafe, gecer, niyet, paralar, bicim, ornekle16k, Algilayici, PARALAR, VARSAYILAN };
});
