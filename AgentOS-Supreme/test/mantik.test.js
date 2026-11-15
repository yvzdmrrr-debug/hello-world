// AgentOS Supreme — mantık testleri:  npm test
const assert = require('assert');
const M = require('../mantik.js');
const uyanik = { uyanik: true }, onay = { uyanik: true, onayAcik: true };
const t = (ad, fn) => { fn(); console.log('  ✓', ad); };

t('uyanış: doğru ve bozuk tanınmış ifadeler', () => {
  for (const s of ['Hey AgentOS', 'hey agent os', 'Hey ayant olsun.', 'Hey, ayen toste.', 'AgentOS', 'Ey ayent olsun.',
    " Hey Ajahn'a olsa.", ' Hei Ayyent Oße.', " Hey Ajan Vos'a", ' Hey Agent OS.'])
    assert.equal(M.niyet(s, {}).tur, 'uyan', s);
  for (const s of ['bugün hava çok güzel değil mi', '', 'televizyonu açar mısın lütfen şimdi'])
    assert.equal(M.niyet(s, {}).tur, 'yok', s);
});
t('uyanmadan komut çalışmaz', () => assert.equal(M.niyet('Binance analizini getir', {}).tur, 'yok'));
t('analiz: varsayılan ve seçili paralar', () => {
  assert.deepEqual(M.niyet('Binance analizini getir', uyanik), { tur: 'analiz', semboller: M.VARSAYILAN });
  assert.deepEqual(M.niyet(" Baina'nın sanalizini getir.", uyanik).tur, 'analiz');       // Whisper çıktısı
  assert.deepEqual(M.niyet('Bitcoin ve ethereum analizini getir', uyanik).semboller, ['BTCUSDT', 'ETHUSDT']);
  assert.deepEqual(M.niyet(' BitJoin ve Eterim analizini getir.', uyanik).semboller, ['BTCUSDT', 'ETHUSDT']);
  assert.deepEqual(M.niyet('solana fiyatı ne', uyanik).semboller, ['SOLUSDT']);
  for (const s of [' Binancı analizini getir.', ' Baina sanalizini getir.', ' binanca analizini getir.', ' Baynan Sanalizini getir.',
    ' Piyasa analizini getir.', " Baina'nın sanal zini ilektir."]) assert.equal(M.niyet(s, uyanik).tur, 'analiz', s);
  assert.deepEqual(M.niyet(' Bit.join fiyatını göster.', uyanik).semboller, ['BTCUSDT']);
});
t('onay penceresi: sesli komutlar', () => {
  for (const s of ['Onayla', 'Evet.', 'tamam', ' Ona ile.']) assert.equal(M.niyet(s, onay).tur, 'onayla', s);
  for (const s of ['İptal et.', 'Kapat', 'hayır', 'vazgeç']) assert.equal(M.niyet(s, onay).tur, 'reddet', s);
  assert.equal(M.niyet('hava nasıl', onay).tur, 'onayBekliyor');
  assert.equal(M.niyet('evet iptal et', onay).tur, 'reddet');                              // şüphede iptal
});
t('işlem ve çıkış onay ister', () => {
  assert.deepEqual(M.niyet('bitcoin al', uyanik), { tur: 'islem', yon: 'AL', sembol: 'BTCUSDT' });
  assert.deepEqual(M.niyet('ethereum sat', uyanik), { tur: 'islem', yon: 'SAT', sembol: 'ETHUSDT' });
  assert.equal(M.niyet('uygulamayı kapat', uyanik).tur, 'cikis');
  assert.equal(M.niyet(' Bu yü bulamayı kapat.', uyanik).tur, 'cikis');                  // Whisper çıktısı
});
t('panel kapatma yalnızca panel açıkken "kapat" ile', () => {
  assert.equal(M.niyet('kapat', { uyanik: true, panelAcik: true }).tur, 'panelKapat');
  assert.equal(M.niyet('paneli kapat', uyanik).tur, 'panelKapat');
  assert.notEqual(M.niyet('kapat', uyanik).tur, 'panelKapat');
});
t('küçük konuşmalar ve sohbet', () => {
  assert.equal(M.niyet(' Saat kaç?', uyanik).tur, 'saat');
  assert.equal(M.niyet('merhaba', uyanik).tur, 'selam');
  assert.equal(M.niyet('teşekkürler', uyanik).tur, 'tesekkur');
  assert.equal(M.niyet('bana bir fıkra anlat', uyanik).tur, 'sohbet');
});
t('yardımcılar', () => {
  assert.equal(M.sade('İPTAL Et!'), 'iptal et');
  assert.equal(M.mesafe('onayla', 'onaile'), 2);
  assert.equal(M.ornekle16k(new Float32Array(48000), 48000).length, 16000);
  assert.equal(M.bicim(64250.5), '64.250,50');
});
t('konuşma algılayıcı: başlama, bitiş, söz kesme eşiği', () => {
  const a = M.Algilayici();
  for (let i = 0; i < 50; i++) assert.equal(a.besle(0.003, 21, false), null);            // sessizlik
  assert.equal(a.besle(0.05, 21, false), null);
  assert.equal(a.besle(0.05, 21, false), 'basladi');                                     // ~42 ms
  for (let i = 0; i < 20; i++) assert.equal(a.besle(0.05, 21, false), null);
  let olay = null, ms = 0;
  while (!olay) { olay = a.besle(0.002, 21, false); ms += 21; }
  assert.equal(olay, 'bitti'); assert.ok(ms >= 700 && ms < 760);
  const b = M.Algilayici();                                                              // asistan konuşurken
  for (let i = 0; i < 10; i++) assert.equal(b.besle(0.018, 21, true), null);             // zayıf yankı kesmez
  assert.equal(b.besle(0.08, 21, true), null); assert.equal(b.besle(0.08, 21, true), null);
  assert.equal(b.besle(0.08, 21, true), 'basladi');                                      // ~63 ms'de söz kesme
});
console.log('Tüm mantık testleri geçti.');
