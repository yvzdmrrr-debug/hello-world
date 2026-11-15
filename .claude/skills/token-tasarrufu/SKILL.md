---
name: "token-tasarrufu"
description: "Use when planning multi-step work, delegating to agents/models, resuming unfinished tasks, or when the user asks about token/cost savings or a usage audit."
---

# Token Tasarrufu (Claude Supreme V17 özeti)

Amaç: doğruluk, güvenlik ve kabul kriterlerinden ödün vermeden toplam maliyeti düşürmek.

## Temel kurallar
1. Önce elde olanı kullan: konuşmadaki bilgi, hafıza, mevcut dosyalar. Aynı araştırmayı tekrarlama.
2. Sadece gerekli parçaları oku; tüm dosya/geçmişi varsayılan olarak yükleme.
3. Ayrıştırma, filtreleme, hesap ve tekrar tespiti için LLM yerine betik/kod kullan.
4. İşe yeten en ucuz modeli/aracı seç; kontrol başarısız olursa güçlüye yükselt.
5. Alt ajanı ancak kalite/süre kazancı ek maliyetten büyükse başlat.
6. Harici LLM sadece gerçekten bağlı bir bağlayıcı (MCP) varsa kullanılır; yoksa varmış gibi davranma.

## Görev devri (yarım kalan iş / ajana aktarım)
Şunları kısaca kaydet: hedef, kapsam, kabul kriterleri, son tamamlanan adım, kararlar ve nedenleri, denenen/başarısız yollar, değişen dosyalar, çalıştırılan testler, kalan işler ve engeller. Devralan taraf önce durumu doğrular, sonra sıradaki adımdan devam eder.

## Ölçüm ve dürüstlük
- Tasarrufu yalnızca ölçülmüşse gerçek diye raporla; tahminleri "tahmin" diye işaretle.
- Veri yoksa "ölçülemez" de; yüzde uydurma. %90 tasarruf hedeftir, garanti değil.
- Net tasarruf = önceki maliyet − (yeni maliyet + optimizasyon maliyeti).
- Uygulanmamış/test edilmemiş özelliği çalışıyor diye gösterme.

## Onay
Riskli, geri alınamaz, finansal veya canlı sistem değişikliklerinden önce onay al.