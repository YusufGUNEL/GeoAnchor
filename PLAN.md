# GeoAnchor — Plan

**GPS'siz İHA Mutlak Görsel Konumlandırma**
Aşağı bakan kamerayı uydu haritasıyla eşleyip görsel odometriyle
birleştirerek, GNSS olmadan sürüklenmesiz metre seviyesi konum üreten sistem.

Başlangıç: 2026-08-21 · Klasör: `C:\Dark\GeoAnchor`
Karar gerekçesi: `C:\Dark\ProjeSecimi\02-PUANLAMA-VE-KARAR.md`

---

## Bir cümlelik problem
İHA'nın GPS'i karıştırılırsa nerede olduğunu bilemez. Görsel odometri bağıl
hareketi verir ama **sürüklenir** — 1 km sonra yüzlerce metre şaşar. Uydu
haritasıyla eşleme mutlak konum verir ama **kare kare güvenilmez** (ağaç,
gölge, mevsim farkı yüzünden çoğu kare tutmaz). Bu proje ikisini bir
**parçacık süzgecinde** birleştirir: her biri tek başına yetersiz, birlikte
sürekli ve sürüklenmesiz.

## Kırılacak hedef (yayınlanmış sayı)
WildNav (TIERS): **%62 konumlandırma oranı, 15,82 m ortalama hata**
AnyVisLoc kıyası: en iyi **%74,1 (5 m içinde)**

---

## Fazlar

### Faz 0 — Temel ve veri  ✅
- [x] Klasör iskeleti, bağımlılıklar, yapılandırma dosyası
- [x] UAV-VisLoc örnek küme (2,04 GB) indir + aç + doğrula
- [x] GeoTIFF uydu haritasını oku, **piksel ↔ enlem/boylam** dönüşümünü kur
- [x] Gerçek konum CSV'sini oku, uçuş dizilerini zaman sırasına diz
- [x] Metrik altyapısı: haversine mesafe (m), başarı@{1,3,5,10,20} m, medyan/ortalama hata
- **Çıktı:** her uçuş için "N kare, şu koordinat aralığı, şu irtifa" özeti

### Faz 1 — Tek kare mutlak konum (temel hat)  🔵 sürüyor
- [ ] Uydu haritasını örtüşen karolara böl
- [ ] Dondurulmuş omurga (DINOv2) ile karo tanımlayıcı veritabanı çıkar
- [ ] İHA karesi → en yakın K karo (küresel geri getirme)
- [ ] Yerel eşleme (LightGlue / SIFT) + RANSAC homografi → kare merkezi → enlem/boylam
- [ ] Güven puanı üret (eşleşen nokta sayısı, iç nokta oranı)
- **Çıktı:** kare bazlı hata dağılımı; WildNav tarzı "şu kadarı tuttu" sayısı
- **Beklenti:** kareler tutar ama %30-40'ı ıskalar → sonraki fazın gerekçesi

### Faz 2 — Görsel odometri (bağıl hareket)  ⬜
- [ ] Ardışık kareler arası özellik eşleme + homografi
- [ ] Nadir/düzlemsel varsayımla ölçekli düzlem içi hareket (Δkuzey, Δdoğu, Δyön)
- [ ] Sadece görsel odometri ile yörünge kur, gerçek değerle kıyasla
- **Çıktı:** sürüklenme eğrisi — mesafeyle büyüyen hata (bu bir başarısızlık
  değil, **kanıt**: mutlak düzeltme neden şart)

### Faz 3 — Parçacık süzgeci füzyonu (işin kalbi)  ⬜
- [ ] Durum: (kuzey, doğu, yön, ölçek)
- [ ] Hareket modeli: görsel odometri artışı + gürültü
- [ ] Ölçüm modeli: geri getirme benzerliği + eşleme doğrulaması → olabilirlik
- [ ] Yeniden örnekleme, etkin parçacık sayısı, kaçırılan karede sadece tahmin
- [ ] Kaçınılmaz ıskaların süzgeci bozmaması (aykırı değer reddi)
- **Çıktı:** sürekli, sürüklenmesiz yörünge + her karede belirsizlik elipsi

### Faz 4 — Reddedilme ve bozulma testi (savunma senaryosu)  ⬜
- [ ] Bozulma üret: sis, hareket bulanıklığı, düşük ışık, ağır JPEG, kısmi kapanma
- [ ] "Ölçüm kesintisi" senaryosu: N saniye eşleme yok → süzgeç ne kadar dayanıyor
- [ ] Kare düşürme oranını %0'dan %90'a taradıkça hata eğrisi
- **Çıktı:** dayanıklılık eğrileri — gerçek harekât koşullarını taklit eden kısım

### Faz 5 — Değerlendirme, ablasyon, kıyas  ⬜
- [ ] Ana tablo: tek kare / sadece odometri / füzyon
- [ ] WildNav'ın yayınlanmış sayısıyla açık kıyas
- [ ] Ablasyon: parçacık sayısı, odometrisiz, doğrulamasız, K değeri
- [ ] Hız: kare/saniye, bellek kullanımı (4 GB'ta çalıştığının kanıtı)
- **Çıktı:** `results/` altında yeniden üretilebilir tablolar + grafikler

### Faz 6 — Sunum  ⬜
- [ ] Yan yana video: İHA görüntüsü | canlı harita iğnesi | hata eğrisi
- [ ] README (Türkçe + İngilizce), şekiller, GIF
- [ ] `.gitignore`, lisans, yeniden üretim talimatı
- [ ] GitHub'a yükleme
- [ ] LinkedIn paylaşım taslağı
- [ ] (İsteğe bağlı) SİU/ELECO bildiri taslağı

---

## Dürüstlük sınırları (README'ye de yazılacak)
Bu bölüm baştan tutuluyor ki sonda abartı olmasın.
- Kayıtlar gerçek İHA uçuşlarından, ama **çevrimdışı** işleniyor (uçuş anında değil)
- Düzlemsel homografi varsayımı: dik bakan kareler için geçerli, eğik bakışta zayıflar
- Uydu haritası önceden indirilmiş kabul ediliyor (gerçek sistemde de böyle olur)
- Yükseklik, sayısal yüzey modeli olmadan kaba kestiriliyor
