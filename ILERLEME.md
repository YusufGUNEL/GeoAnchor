# GeoAnchor — İlerleme Günlüğü

Her yapılan iş buraya kısa ve net yazılır. Tarih, ne yapıldı, sonuç ne çıktı.

## 2026-08-21

**Seçim yapıldı.** 13 alan araştırıldı, puanlandı (`C:\Dark\ProjeSecimi\`).
GPS'siz İHA mutlak konumlandırma 890/1000 ile kazandı. İkinci sıradaki
atmosferik türbülans giderme fikri yedek dosyaya kaydedildi.

**Ortam:** Python 3.12.10, PyTorch 2.9.1+cu126 (CUDA çalışıyor),
OpenCV 4.13.0, RTX 3050 Ti 4 GB. gdown/rasterio/kornia kuruldu.

### Faz 0 — Temel ve veri ✅ BİTTİ

**Veri.** UAV-VisLoc örnek kümesi indirildi (2,19 GB), açıldı → `D:\GeoAnchorData\raw`.
İçinde tek uçuş var ama tam istediğim şey: **gerçek bir dizi**.

| Ne | Değer |
|---|---|
| Kare sayısı | 768 |
| Süre / mesafe | 77 dakika / 73,9 km |
| İrtifa | 466 m (±1,3 m, çok kararlı) |
| Kare aralığı | ortalama 96,3 m |
| Bakış | neredeyse dik (eğim ve yalpa ±5° içinde) |
| Uydu haritası | 35092 x 24308 px, 0,275 m/px, 8,8 x 7,3 km |
| Gerçek konum | her karede enlem, boylam, irtifa, yönelim |

**Yazılanlar.** `src/geo.py` (piksel↔coğrafi dönüşüm, haversine, yerel düzlem,
2,6 GB GeoTIFF'ten pencere okuma — dosya asla belleğe alınmıyor),
`src/flight.py` (uçuş yükleme + türetilmiş sütunlar),
`scripts/00_inspect.py` (doğrulama).

**Ölçülenler.**
- Coğrafi dönüşüm gidiş-dönüş hatası: **0,0000 m** — dönüşüm doğru.
- 768/768 kare haritanın içinde.
- İHA görüntü ölçeği ardışık kare eşlemesinden kestirildi: **0,1142 m/piksel**
  (veri kümesinin belirttiği 0,1–0,2 m aralığında, bağımsız doğrulama).
- Kare ayak izi **454 x 303 m**, ardışık örtüşme **%78,8**, medyan iç nokta **254**
  → Faz 2'deki görsel odometri için fazlasıyla sağlam zemin.
- Uydu/İHA ölçek oranı 2,41x.

**Görsel doğrulama yapıldı** (`figures/00_hizalama.png`): İHA karesi ile aynı
koordinattaki uydu kırpması aynı yeri gösteriyor — mavi çatılı depolar, kanal
boyu köy dizisi, tekneli nehir kıvrımı hepsi örtüşüyor.

**Ve asıl zorluk görüldü:** uydu görüntüsü farklı mevsimden (koyu yeşil tarlalar),
İHA kaydı sonbahardan (altın sarısı tarlalar). Üstelik İHA kareleri kuzeye göre
döndürülmüş. Yani bu "aynı görüntüyü bul" değil, **mevsim ve bakış açısı
değişimine rağmen aynı yeri bul** problemi. Projenin zorluğu tam da burada.

`figures/00_yorunge.png`: uçuş klasik tarama deseni; nehir, tarla, yoğun kent ve
sanayi bölgesinden geçiyor — bazı bölgelerde eşleme tutmayacak (su, tekdüze
tarla), bazılarında tutacak. Faz 3'ün gerekçesi bu.

### Geometri kalibrasyonu ✅ (Faz 1 öncesi zorunlu adım)

Üstveride hangi açının kamera yönelimi olduğu ve hangi işaretle
kullanılacağı yazmıyor. Tahmin etmek yerine ölçtüm.

**1. adım — bedava kontrol (uçuş yönü).** Ardışık gerçek konumlardan uçuş
yönünü hesaplayıp açılarla karşılaştırdım (767 kare):

| Bağıntı | Ortalama | Std |
|---|---|---|
| yön − Phi1 | −3,17° | 13,89° |
| **yön − Phi2** | **0,12°** | **9,39°** |

Phi2 uçuş yönüyle birebir örtüşüyor. Ama bu tek başına yeterli değil: uçağın
burnunun baktığı yön ile yer üstünde ilerlediği yön rüzgâr yüzünden farklı olur.

**2. adım — LoFTR ile kesin karar.** İHA karesini dört farklı şekilde döndürüp
(Phi1/Phi2 × işaret ±1) gerçek konumdaki uydu kırpmasıyla eşledim:

| Kaynak | İşaret | Toplam iç nokta | Kalan artık açı |
|---|---|---|---|
| **Phi1** | **−1** | **545** | −0,9° / −2,0° / −2,1° / +1,4° → ≈ 0 |
| Phi2 | −1 | 459 | +10,2° / +10,7° / +11,6° / +14,1° |
| Phi2 | +1 | 8 | — |
| Phi1 | +1 | 6 | — |

**Sonuç:** İHA karesi **−Phi1** ile döndürülür. Phi1 kameranın gerçek yönelimi,
Phi2 ise yer üstündeki ilerleme yönü — aradaki sabit ~12° fark rüzgâr kaynaklı
yengeç açısı. Phi1 ile döndürünce artık açı sıfıra iniyor, Phi2 ile 12° kalıyor.
Veri kümesinin "Phi1 daha güvenilir" notu doğrulandı.

### Eşleyici kararı: SIFT elendi, LoFTR seçildi

Aynı kareler, aynı kırpmalar, iki eşleyici:

| Eşleyici | İç nokta (4 kare) |
|---|---|
| SIFT + oran testi | 12, 4, 24, 7 |
| **LoFTR (outdoor)** | **104, 21, 280, 140** |

SIFT mevsim ve güneş açısı farkını aşamıyor. LoFTR dedektörsüz çalıştığı için
görünüm değişimine dayanıklı. Maliyet: 640×640'ta 0,52 sn ve **1,4 GB VRAM** —
4 GB'lık kartta rahat çalışıyor.

Yan ürün: kestirilen ölçek 0,925–1,091 arasında değişiyor. Yani sabit
0,1142 m/piksel varsayımı arazi yüksekliği değiştikçe ±%8 şaşıyor. Faz 3'te
ölçeğin de durum vektörüne girmesinin gerekçesi bu.

### Faz 1a — Getirme katmanı ✅

Uydu haritası 300 m'lik, %50 örtüşen **2709 karoya** bölündü; her karo için
DINOv2 (ViT-S/14, dondurulmuş) tanımlayıcısı çıkarıldı. Süre 1,1 dk, 7,5 MB.

**Kendi hatamı buldum ve düzelttim.** İlk ölçümde getirme berbattı (R@1 %7,3).
Sebep problemin zorluğu değil, benim boru hattımdı: İHA karesini gri tonlamaya
çevirip uydunun **renkli** karolarıyla kıyaslıyordum. Renk korunduğunda:

| Ayar | R@1 (150 m) | R@5 | R@20 |
|---|---|---|---|
| gri (hatalı) | %7,3 | %16,5 | %32,6 |
| renkli, 224 girdi | %33,1 | %54,7 | %71,6 |
| renkli, 336 girdi | %48,0 | %67,2 | %78,3 |
| **renkli, 448 girdi, cls+GeM** | **%52,7** | **%70,4** | **%79,9** |

Ders: bir sonucu "problem zor" diye kabul etmeden önce boru hattını denetle.

### Faz 1b — Tavan doğruluğu ve dört hipotezli teşhis ✅

Gerçek konum BİLİNİYORKEN eşleme ne kadar hassas? İlk ölçüm **medyan 17,75 m**.
Bu çok yüksekti; sırayla eledim:

| Hipotez | Test | Sonuç |
|---|---|---|
| Gerçek konum gürültülü | Düz uçuş hatlarına doğru uydur | **Hayır** — çapraz sapma sadece 1,50 m, adım std 0,60 m. Gerçek konum temiz |
| Sabit harita kayması | Hata vektörünün ortalaması | **Hayır** — kuzey −0,26 m, doğu +1,56 m. Kayma yok |
| Dönüşüm modeli yetersiz | benzerlik / afin / homografi | **Hayır** — üçü de 17,0–17,4 m |
| Harita en-boy oranı | EPSG:4326 pikselleri metrede kare değil (0,2526 vs 0,2974 m/px, **%17,8 fark**) | **Kısmen** — metrik kare kırpma eklendi, iç nokta 159 → 496 ama hata 17,6 m'de kaldı |

Sonra hatayı **gövde çerçevesine** ayrıştırdım (ileri / sağ) — dünya çerçevesinde
bakmak yön bilgisini yok ediyormuş:

- iz-boyu hata: **+13,81 m** (sabit, her iki uçuş kolunda da aynı)
- iz-dışı hata: −1,82 m (≈ 0)

Sabit bir **ileri** kayma. Sonra duruş açılarına regresyon:

| Bağıntı | R² |
|---|---|
| iz-boyu ~ Omega | 0,002 |
| iz-dışı ~ Kappa | 0,000 |
| **iz-boyu ~ Kappa** | **0,677** (katsayı +0,981) |
| **iz-dışı ~ Omega** | **0,765** (katsayı −0,972) |

**Açı kanalları yer değişmiş.** Veri kümesi belgesi "Omega eğim, Kappa yalpa"
diyor; gerçekte tersi. Katsayıların ±1'e oturması fiziğin (yerdeki kayma =
irtifa × tan(açı)) birebir doğru olduğunu, sadece etiketlerin ters olduğunu
gösteriyor. Phi1/Phi2'de de aynı durum vardı — bu veri kümesinin üstverisi
belgelendiği gibi değil, deneyle doğrulanması şart.

**Fiziksel düzeltme.** Eşleme bize görüntü MERKEZİNİN yere düştüğü noktayı
verir; aradığımız İHA'nın kendi konumu. Kamera dik bakmıyorsa aradaki fark
irtifa × tan(eğim). 466 m'de 2° eğim = 16 m.

Montaj sapması uçuşun **ilk %20'sinde** kalibre edildi, kalan %80'de ölçüldü:

| | Önce | Sonra |
|---|---|---|
| Medyan hata | 16,82 m | **6,12 m** |
| Ortalama | 18,66 m | 6,57 m |
| %90 dilim | 30,95 m | 11,15 m |
| 5 m içinde | %2,6 | **%40,0** |
| 10 m içinde | %17,4 | **%80,9** |
| 20 m içinde | %59,1 | **%99,1** |

Bulunan montaj sapması: **eğim +2,006°**, yalpa −0,137°. Yani kamera 2 derece
öne bakacak şekilde monte edilmiş. Bu fotogrametride "boresight kalibrasyonu"
denen standart iştir ve gerçek sistemlerde bir kez yapılır.

**Not:** duruş ve irtifa bilgisi kullanılıyor. Bu GPS'siz senaryoyu bozmaz —
eğim/yalpa/yönelim ataletsel ölçüm biriminden, irtifa barometre/altimetreden
gelir; hiçbiri uyduya bağlı değildir. (AnyVisLoc kıyas kümesinin "yp"
protokolü de aynı varsayımı kullanıyor.) README'de açıkça yazılacak.

### Faz 2 ve 3 — mimari kararlar (kod yazıldı, ölçüm sürüyor)

**Görsel odometri (`src/odometry.py`).** Ardışık kareler arasında alan farkı
yok (aynı kamera, 7 sn ara, %79 örtüşme), o yüzden burada LoFTR'a gerek yok —
klasik SIFT yetiyor ve CPU'da çalışıyor, GPU'yu uydu eşlemesine bırakıyor.
Kareler zaten kuzey-yukarı ve metrik ölçekte olduğu için iki kare arasındaki
dönüşüm neredeyse saf öteleme: sonuç doğrudan metre cinsinden okunuyor.

**Parçacık süzgeci (`src/particle_filter.py`).** Kalman yerine parçacık
süzgeci seçildi, sebebi şu: uydu eşlemesinin hata dağılımı Gauss değil. Çoğu
zaman doğru yeri birkaç metreyle bulur, ama arada bir bambaşka bir yeri
gösterir (benzer tarla, aynı desende ikinci mahalle). Bu **çok tepeli ve ağır
kuyruklu** bir dağılım. Kalman tek tepeli Gauss varsayar ve tek bir saçma
ölçüm onu kalıcı olarak yanlış yere çeker. Parçacık süzgeci birden çok adayı
canlı tutup zamanla hangisinin uçuşla tutarlı olduğuna karar verir; ayrıca
olabilirliğe düz bir "aykırı değer tabanı" eklendi ki yanlış bir ölçüm tüm
ağırlığı silip süpüremesin.

**Sıralı sistem (`src/sequential.py`) — asıl fikir.** Nerede olduğumuzu kabaca
biliyorsak haritanın tamamında 8 aday denemenin anlamı yok; tahmin edilen tek
noktaya bakmak yeter. Yani sıralı sistem sadece daha doğru değil, **daha az
eşleme çağrısı** yapıyor. Tutmazsa yakın karolara bakılıyor, tamamen kaybolursa
(parçacıklar dağılırsa veya arka arkaya ölçüm gelmezse) haritanın tamamında
yeniden konumlanma devreye giriyor — robotikteki "kaçırılmış robot" kurtarması.

**Bozulma modülü (`src/degrade.py`).** Altı gerçekçi bozulma: hareket
bulanıklığı, sis, düşük ışık, JPEG sıkıştırma, kapanma, çözünürlük kaybı.
Her biri tek bir şiddet parametresiyle ölçekleniyor ki dayanıklılık eğrisi
çizilebilsin. Bir seyrüsefer sisteminin değeri temiz karede değil, bunların
altında ayakta kalmasında.

### Faz 1 — Tek kare, tam uçuş ✅ BİTTİ

768 karenin her biri **haritanın tamamında** arandı (geçmiş bilgisi yok).

| Ölçü | Değer |
|---|---|
| Çözülen kare | **588/768 (%76,6)** |
| Medyan hata (çözülenlerde) | **5,46 m** |
| Ortalama | 6,04 m |
| %90 dilim | 10,71 m |
| 100 m'den büyük ıska | **0 kare** |
| Kare başına süre | 2630 ms (ortalama 3,8 aday denendi) |
| Toplam | 33,7 dk |

Tüm kareler üzerinden başarı: 5 m içinde %34,1 · 10 m içinde %66,1 ·
20 m içinde %76,4. Yani **doğru olduğunda çok iyi, ama karelerin dörtte biri
hiç çözülemiyor** — su üstü, tekdüze tarla, tekrar eden yapı deseni.

Kaba ıskanın sıfır olması önemli: getirme yanlış bölge önerdiğinde LoFTR
doğrulaması onu eliyor, sistem "bilmiyorum" diyor. Sessizce yanlış konum
üretmiyor. Seyrüsefer için doğru davranış budur.

### Faz 2 — Görsel odometri ✅ BİTTİ

| Ölçü | Değer |
|---|---|
| Tutan adım | 724/767 (%94,4) |
| Medyan iç nokta | 154 |
| Artık dönme | +0,046° ± 0,478° → kuzey-yukarı dönüşü doğru |
| Artık ölçek | 1,0057 ± 0,0379 → metrik ölçek doğru |
| **74 km sonra son hata** | **2802,7 m (%3,795 sürüklenme)** |

**Sonra bir sapma yakalandı.** Adım hatası uçuş koluna göre çok farklıydı:
kuzeybatı kolunda 4,90 m, güneydoğu kolunda 12,66 m. Sebep: odometrinin
ölçtüğü hareket yönü ile gerçek yön arasındaki açı farkı kola göre değişiyor
(+1,65° ve +7,22°). Bu manyetometrenin sert-demir hatasının klasik imzası —
yönelim hatası, yönün fonksiyonu. Havacılıkta "pusula sapma eğrisi" denir.

Uçuşun ilk %20'sinde kalibre edilip kalan %80'de ölçüldü:

| | Düzeltmesiz | Kalibrasyonlu |
|---|---|---|
| Adım hatası medyan | 8,671 m | **4,460 m** |
| 74 km sonra son hata | 2802,7 m | **638,6 m** |
| Sürüklenme oranı | %3,795 | **%0,865** |

### Ve asıl bulgu: bu kalibrasyon GPS'siz yapılabiliyor ✅

Yukarıdaki kalibrasyon gerçek konumu kullanıyor — gerçek bir GPS'siz sistemde
elimizde olmayan şey. Ama aynı bilgi **haritadan** okunabilir mi?

Homografinin dönme bileşeni, kuzey-yukarı yapılmış İHA karesi ile kuzey-yukarı
uydu karosu arasındaki artık açıyı verir. Bu açı sıfır değilse yönelim açısının
kendisi o kadar sapmış demektir. Ölçüldü:

| | Haritadan okunan artık dönme | Gerçek konumdan hesaplanan sapma |
|---|---|---|
| Kuzeybatı kolu | **−1,93°** (std 0,86) | +1,65° |
| Güneydoğu kolu | **−7,08°** (std 1,73) | +7,22° |

Aynı büyüklük, beklenen ters işaret. Yani sistem pusula hatasını kendi
kendine, hiçbir konum bilgisi olmadan ölçebiliyor. Bu çevrimiçi kalibrasyon
sıralı sisteme gömüldü (`SequentialLocalizer._note_angle`). Aynı mantıkla
ölçek de haritadan öğreniliyor (`_note_scale`) — arazi yüksekliği değiştikçe
İHA yer örnekleme aralığı kayıyor, homografinin ölçek bileşeni bunu ele veriyor.

### Faz 3 — Sıralı füzyon: iki gerçek hata bulundu ve düzeltildi

İlk çalıştırmada süzgeç tek kareden **daha kötüydü** (medyan 14,5 m, ATE 47 m).
Teşhis için ham ölçümü, tahmini ve süzgeç çıktısını ayrı ayrı kaydettim:

```
kare  ham olcum   tahmin   suzgec   ic nokta
   4        6.6     100.4    100.4        136
   8        4.1     107.0    106.9        424
  16        9.6     105.8    105.8        710
```

**Ölçüm mükemmeldi (4-10 m) ama süzgeç onu tamamen görmezden geliyordu.**

**Hata 1 — parçacık tükenmesi.** Bulut birkaç metreye toplandığında 100 m
uzaktaki ölçüme hiçbir parçacık yakın olmuyor; olabilirlik her yerde sıfıra
iniyor, ağırlıklar hiç değişmiyor. Süzgeç doğru ölçümü görse bile kıpırdamıyor.
Erken bir yanlış eşleşmeye kilitlenince orada kalıyor.

*Çözüm:* küresel konumlandırmada standart olan **karma öneri dağılımı** —
her adımda parçacıkların bir kısmı hareket modeli yerine ölçüm dağılımından
çekiliyor. Ölçüm doğruysa bu parçacıklar yüksek ağırlık alıp bulutu kendine
çekiyor; yanlışsa eleniyor. Yanına bir de "uyuşmazlık sayacı" güvenlik ağı
kondu: ölçüm arka arkaya 5 kare inanıştan 40 m'den uzak düşerse inanış
terk ediliyor.

**Hata 2 — kör gürültü.** Odometri adımı kaçtığında (%5,6 karede) 96 m'lik
izotropik gürültü basıyordum, yani bir karede alınan yol kadar. Tek bir kaçan
adım bulutu 130 m'ye yayıp süzgeci düşürüyordu. Oysa yönelim ataletsel
birimden biliniyor ve hız neredeyse sabit — **son adımı sürdürmek (ölü hesap)**
çok daha iyi bir tahmin. Gürültü 96 m'den 15 m'ye indi.

Ayrıca hareket modeli gürültüsü ölçülen odometri doğruluğuna oturtuldu
(3,1 m varsayımı yerine gerçek 8,7 m) ve ölçüm kapısı belirsizliğe göre
uyarlanır hale getirildi.

**120 karelik denemede etkisi:**

| | Düzeltmeden önce | Sonra |
|---|---|---|
| Medyan hata | 14,45 m | **8,22 m** |
| Ortalama | 30,41 m | **8,60 m** |
| %90 dilim | 102,88 m | **13,53 m** |
| En büyük hata | 111,13 m | **33,86 m** |
| ATE | 47,11 m | **9,94 m** |
| 20 m içinde | %66,7 | **%99,2** |

### Faz 3 — üçüncü hata ve nihai sonuç ✅ BİTTİ

120 karelik denemeler iyiydi ama tam uçuşta en büyük hata 631 m'ye çıkıyordu.
Kopmaları tek tek inceledim: dört blok (kare 192-200, 288-308, 517-522,
576-583), hepsinde iç nokta **sıfır**, hepsi eşlemenin hiç tutmadığı arazi.

İlk teşhisim yanlıştı: "dönüşlerde oluyor, ölü hesap eski yönü sürdürüyor"
dedim, ölü hesabı yönelim tabanlı yaptım — pek bir şey değişmedi. Sonra
odometrinin o bloklarda ne yaptığına baktım:

| | Kopma bloklarında | Diğer yerlerde |
|---|---|---|
| Odometri adım hatası | 8,6 m | 8,2 m |

**Odometri sapasağlamdı.** Sorun girdide değil, benim `step()` akışımdaydı:
süzgeç "kayıp" durumuna girince ayrı bir dala sapıyor ve eldeki geçerli
odometriyi tamamen atıyordu. Yeniden konumlanma, hareket modelinin yerine
geçen bir şey değil, **ek bir ölçüm denemesi** olmalı. Akış düzeltildi
(tahmin her zaman yapılır) + eşlemenin çalışmadığı arazide her karede 8 aday
denemeyi engelleyen soğuma süresi kondu.

En büyük hata **631 m → 338 m**, ATE 83 → 63,8 m.

**NİHAİ SONUÇ (768 kare, 74 km):**

| | Kapsama | Medyan | %90 | 10 m içinde | Eşleme/kare | ms/kare |
|---|---|---|---|---|---|---|
| Sadece odometri | %100 | 2803 m sürükleniyor | — | %0 | 0 | — |
| Tek kare | %76,6 | 5,46 m | 10,71 m | %66,1 | 3,80 | 2630 |
| **Sıralı füzyon** | **%100** | **6,20 m** | 14,76 m | **%76,8** | **1,52** | **866** |

Kopma blokları hariç (%94,3 kare): **medyan 5,97 m, %90 dilim 11,97 m,
20 m içinde %99,9, ATE 7,78 m**.

Füzyon iki girdisinden de iyi ve her karede haritanın tamamını aramaktan
**2,5 kat ucuz** — kabaca nerede olduğunu bilmek küresel aramayı tek yerel
kontrole indiriyor.

### Faz 5/6 — çıktılar ✅

Şekiller (`figures/`): `10_karsilastirma.png` (iki panel: odometrinin
haritadan çıkışı vs harita çapalı sistem), `13_dagilim.png` (birikimli hata
dağılımı — üç yöntem tek grafikte), `11_hata_egrisi.png`, `12_kapsama.png`.

Belgeler: `README.md` (İngilizce, GitHub yüzü), `README.tr.md` (Türkçe),
`LICENSE` (MIT), `requirements.txt`, `.gitignore`.

**README'de dürüst sınırlar bölümü var ve önce o yazıldı:** eşlemenin çöktüğü
%5,7'lik kesim, çevrimdışı işleme, duruş/irtifa varsayımı, tek uçuş-tek
mevsim, iki yönelimle uydurulmuş pusula eğrisi, düzlemsel homografi sınırı.
Hiçbiri gizlenmedi.

### Faz 5 — Ablasyon ✅ BİTTİ

Her satır tam sistemden tek bir bileşen çıkarıyor (aynı 300 kare, aynı tohum):

| Çıkarılan | Medyan | %90 | 20 m içinde |
|---|---|---|---|
| *hiçbiri (tam sistem)* | **6,62 m** | 16,17 m | **%92,7** |
| Çevrimiçi ölçek kalibrasyonu | 7,03 m | 17,18 m | %91,7 |
| Parçacık enjeksiyonu | 7,62 m | 19,50 m | %90,7 |
| Çevrimiçi pusula kalibrasyonu | 7,85 m | 18,53 m | %90,7 |
| Görsel odometri | 9,98 m | **367,66 m** | %77,7 |
| **Duruş/boresight düzeltmesi** | **17,13 m** | 29,93 m | **%67,3** |

**İki bileşen yerini hak etmedi** — bunu gizlemek yerine yazdım:

| Varyant | Medyan | 20 m içinde |
|---|---|---|
| 100 parçacık (600 yerine) | 7,08 m | %92,7 |
| 2000 parçacık | 6,80 m | %92,7 |
| Aykırı değer tabanı YOK | **6,76 m** | **%93,3** |

Parçacık sayısı neredeyse etkisiz → süzgeç parçacık kıtlığı çekmiyor, durum
uzayı küçük. Aykırı değer tabanı da ölçülebilir hiçbir şey değiştirmiyor;
ölçüm kapısı ve enjeksiyon kötü eşleşmeleri zaten daha önce eliyor. Kodda
ucuz bir güvenlik ağı olarak kalıyor ama bu veride ölü ağırlık.

En anlamlı iki satır: **boresight düzeltmesi tek başına en büyük katkı**
(17,13 → 6,62 m) ve **odometriyi çıkarmak medyanı değil KUYRUĞU bozuyor**
(%90 dilim 16 → 368 m) — hareket modelinin varlık sebebi tam olarak bu.

---

## Faz 7 — Çok uçuşlu genişletme (2026-08-22)

Projenin en büyük zayıflığı "tek uçuş"tu. Tam veri kümesi indirilip aynı kod
9 uçuşta çalıştırıldı.

**Veriyi bulmak ayrı bir işti.** Google Drive günlük indirme kotasını
doldurmuştu. Hugging Face'te aynalar arandı; `mvidem/UAV-VisLoc` 11 uçuşun
hepsini klasör klasör tutuyordu. Hugging Face de IP'yi hız sınırına takınca
bekleyip devam eden bir indirici yazıldı. **Bir tuzak:** `snapshot_download`
bağlantı hatasında mevcut klasörü döndürüp "bitti" gibi görünüyor. İlk
indirici buna kandı; tamamlanma artık kütüphanenin dönüşüne değil DOSYALARA
bakılarak doğrulanıyor.

### Uçuş başına sonuçlar (tam otomatik, her uçuş kendi ilk %20'sinde kalibre)

| Uçuş | Kare | İrtifa | Yol | Eşleşme oranı | Kapsama | Medyan | %90 |
|---|---|---|---|---|---|---|---|
| 03 | 768 | 466 m | 74 km | %93 | %100,0 | **8,35 m** | 20,03 m |
| 04 | 738 | 544 m | 83 km | %90 | %100,0 | **15,44 m** | 54,64 m |
| 06 | 344 | 834 m | 24 km | %76 | %99,7 | **15,06 m** | 365,32 m |
| 05 | 473 | 2313 m | 30 km | %50 | %99,8 | **16,69 m** | 182,51 m |
| 01 | 817 | 406 m | 66 km | %77 | %100,0 | **22,51 m** | 114,60 m |
| 11 | 590 | 2572 m | 84 km | %90 | %99,8 | **24,79 m** | 424,41 m |
| 02 | 1071 | 406 m | 86 km | %37 | %99,7 | 53,45 m | 343,39 m |
| 10 | 144 | 773 m | 9 km | %13 | %84,7 | 126,88 m | 324,98 m |
| 08 | 1033 | 551 m | 103 km | %33 | %79,7 | 648,49 m | 3785,02 m |

### Asıl bulgu: başarımı algoritma değil veri belirliyor

Sonuçlar 8 m ile 648 m arasında dağıldı. Soru şuydu: sistem bazı uçuşlarda mı
kötü çalışıyor, yoksa bazı uçuşların verisi mi eşlemeye elverişsiz?

Ölçüt olarak **gerçek konum biliniyorken** elde edilen eşleşme oranı alındı —
konum araması devrede değil, doğru yere bakılıyor; tutmuyorsa sebep veridir.

| | Uçuş | Medyan hata | Kapsama |
|---|---|---|---|
| Eşleşme oranı ≥ %50 | 6 | **8,35 – 24,79 m** (medyan 16,07 m) | ≥ %99,7 |
| Eşleşme oranı < %50 | 3 | 53 – 648 m | %80 – 85 |

Korelasyon (eşleşme oranı ~ log hata): **−0,765**.

**İrtifa ayırt edici değil** — 2572 m'deki uçuş 11 çalışıyor (24,79 m),
551 m'deki uçuş 08 çöküyor. Belirleyici olan İHA görüntüsü ile uydu
haritasının tanınabilir ölçüde aynı dünyayı gösterip göstermediği.

Bunun kullanışlı bir sonucu var: eşleşme oranı **uçmadan önce** planlanan rota
üzerinde ölçülebilir. Yani sistemin o görevde işe yarayıp yaramayacağı önceden
bilinebilir. `figures/15_ucus_zorlugu.png`

### Yol boyunca bulunan iki hata

**1. Duruş düzeltmesi yüksek irtifada ters tepiyordu.** Model "yerdeki kayma =
irtifa × tan(açı)" diyor ve kayıtlı yüksekliğe güveniyor. Uçuş 05'te (kayıtlı
2313 m) düzeltme hatayı **27,8 m'den 131,2 m'ye çıkardı** — o yükseklik
muhtemelen gerçek yerden yükseklik değil. Etkin irtifa artık veriden
kestiriliyor; aynı uçuşta kalibrasyon şimdi 21,4 → 5,5 m.

**2. Zarar verme kuralı eklendi.** Kalibrasyon kareleri ikiye bölünüyor:
yarısında uyduruluyor, diğerinde sınanıyor. Düzeltme sınama yarısında hatayı
azaltmıyorsa **hiç uygulanmıyor**. İki uçuşta gerçekten devreye girdi.

**Uçuş 07 dışlandı:** üstverisinde duruş/yönelim sütunları yok. Yükleyici artık
sessizce yanlış sonuç üretmek yerine açık hatayla reddediyor.

---

## Faz 8 — Daha güçlü eşleyici denemesi: RoMa (2026-08-22)

Dokuz uçuşluk çözümleme darboğazın eşleme kalitesi olduğunu göstermişti.
Mantıklı sonraki adım: LoFTR yerine RoMa (yoğun eşlemede bugünün en iyisi).

**İlk ölçüm heyecan vericiydi.** Gerçek konumda, aynı karelerde:
uçuş 08'de eşleşme oranı %29 → %100, uçuş 10'da %12 → %96. Üç çöken uçuş da
eşiğin üstüne çıkmıştı. 2,7 GB VRAM'e sığıyordu. Kullanıcıya "çözüm bulundu"
diye yazdım.

**Sonra uçtan uca çalıştırdım: uçuş 01'de 1669 m** (LoFTR 22 m veriyordu).

**Hatam neydi:** Kıyaslamada her iki eşleyiciye de sadece DOĞRU uydu karosunu
gösteriyordum. Oysa konumlandırma sistemi asıl mesaisini tersi soruya harcar —
"burası doğru yer mi?". Onu ölçmemiştim.

Ölçtüm — her kareyi haritanın rastgele bir köşesiyle eşledim:

| | Doğru yerde | **Yanlış yerde** | Oran |
|---|---|---|---|
| LoFTR | 709 | **0** | 709 kat |
| RoMa | 4598 | **341** | 13,5 kat |

**RoMa her şeye eşleşiyor.** "%100 eşleşme oranı" bir yetenek değil, sadece
kolay yönü ölçen bir ölçütün yan ürünüymüş.

Eşik ayarı da kurtarmıyor. Doğru/yanlış ayrımı:

| Ölçüt | LoFTR | RoMa |
|---|---|---|
| Ham iç nokta | **%100 temiz** | %98,1, örtüşme var |
| İç nokta oranı | **%100 temiz** | %98,1, örtüşme var |
| Eşleyici güveni | %96,2 | %96,2 |

LoFTR için sıfır hatalı bir eşik VAR. RoMa için yok.

**Uçtan uca, eşikler RoMa lehine ayarlıyken:**

| Uçuş | Yapılandırma | Kapsama | Medyan |
|---|---|---|---|
| 01 | LoFTR | %100 | **21,82 m** |
| 01 | RoMa (ham 3050) | %99,5 | 39,71 m |
| 01 | RoMa (oran 0,61) | %100 | 40,53 m |
| 08 | LoFTR | **%4,5** | 582 m |
| 08 | RoMa (ham 3050) | %95,5 | **6250 m** |
| 08 | RoMa (oran 0,61) | %95,5 | 3689 m |

Uçuş 08 satırı her şeyi anlatıyor: LoFTR %4,5 karede konum üretiyor, yani
**bilmediğini söylüyor**. RoMa %95,5'inde üretiyor ve 6 km yanılıyor.

**Sonuç: RoMa elendi.** Daha zayıf olduğu için değil — daha güçlü. Bu görev
o ölçütlerin ölçmediği bir şey istiyor:

> Bir eşleyicinin buradaki değeri ne kadar eşleştirdiğiyle değil, hiç
> eşleşmemesi gereken yerde susabilmesiyle ölçülür.

Kod `RomaMatcher` ve `--matcher roma` anahtarını koruyor (sonuç yeniden
üretilebilsin diye), `accept_ratio` ölçütü de bu sırada eklendi.

**Ders:** Bir iyileştirmeyi duyurmadan önce uçtan uca ölç. Ara ölçüt (eşleşme
oranı) yanlış yönü ölçüyordu ve neredeyse yanlış bir sonucu rapor ediyordum.

---

## Faz 9 — Onuncu uçuş ve makale taslağı (2026-08-22)

**Uçuş 09 aslında inmişti.** İndirici "eksik" diyordu çünkü `satellite09.tif`
arıyordu; oysa o uçuşun haritası **2×2 dört parçaya** bölünmüş (toplam 4,5 GB).

Parçaları birleştirip diske yazmak 4,5 GB'lik kopya demekti. Bunun yerine
`src/mosaic.py` yazıldı: GDAL sanal raster (VRT) — kaynaklara işaret eden
küçük bir XML. rasterio tek raster gibi açıyor, hiçbir şey kopyalanmıyor.
Sonuç: 44800×33280 px tek harita, 11,5 × 9,9 km, 766 karenin hepsi içinde.

Gerçek konuşlandırmalarda haritalar zaten karolu gelir, yani bu bir yama değil
eksik bir yetenekti.

**Uçuş 09 sonucu:** %100 kapsama, medyan **14,94 m**, %90 dilim 59,33 m.
Kalibrasyon hatası 15,1 → 6,2 m. Eşleşme oranı %70 — eşiğin üstünde, ve
sonuç tam beklenen bantta çıktı. Yasa doğrulandı.

**10 uçuşla güncel tablo:**

| | Uçuş | Medyan hata | Kapsama |
|---|---|---|---|
| Eşleşme oranı ≥ %50 | **7** | 8,35 – 24,79 m (medyan 15,44 m) | ≥ %99,7 |
| Eşleşme oranı < %50 | 3 | 53 – 648 m | %80 – 85 |

Korelasyon −0,764.

### Makale taslağı

`paper/geoanchor.tex` — IEEE konferans biçimi, 6 sayfa.

**Başlık:** *Knowing When You Do Not Know: Sequential Map-Anchored Visual
Localization for GNSS-Denied UAV Flight*

**Literatür taraması (arXiv API):** 2024-2026 arası 20 çapraz görüş
makalesinin **hiçbiri** kare sonucunu hareket modeliyle birleştirmiyor.
Parçacık süzgeci + hava haritası işleri var ama hepsi **yer aracı**
(BEV-Patch-PF 2025, Downes 2022, Dixit 2020). Tek İHA çalışması Shan 2017 —
öğrenilmiş eşleyicilerden önce, optik akış + harita korelasyonu.

Boşluk net: modern dedektörsüz eşleyici + sıralı süzgeç + uçak + metrik hata.

**Hedef:** SİU 2026 temmuzda geçti, SİU 2027 şubat civarı, ELECO iki yılda bir
(sonraki 2027). Bu yüzden **önce arXiv ön baskısı**, aynı metin şubatta SİU'ya.

**Not:** LaTeX kurulu değil sanılmıştı; Faz 10'da yanlış olduğu görüldü (TinyTeX kurulu, yerelde derleniyor).

---

## Faz 10 — Makale yayına hazır (2026-09-06)

Faz 9'un taslağı derleniyordu ama **içinde tek bir şekil yoktu**. Bir görsel
konumlandırma makalesinin dört sayfa düz metin olması, depoda on iki hazır
şekil dururken, savunulacak bir tercih değil.

**LaTeX aslında kuruluydu.** Faz 9'un "LaTeX yok, Overleaf'e yükle" notu
yanlıştı: TinyTeX `~/AppData/Roaming/TinyTeX` altında duruyor, `latexmk` ile
yerelde derleniyor. Not düzeltildi.

### Şekiller

`figures/` altındakiler Türkçe etiketli ve README ölçüsünde — makaleye
giremezler. `scripts/30_paper_figures.py` yazıldı: aynı `results/` dosyalarını
okuyup İngilizce ve IEEE sütun ölçüsünde (tek sütun 3,5", metin bloğu 7,16")
vektör PDF üretiyor. Şekillerin metinden ayrı düşmesi böylece imkânsız.

| şekil | ne gösteriyor |
|---|---|
| `fig1_trajectory.pdf` | uçuş 03, ortofoto üstünde: odometri haritayı terk ediyor, füzyon gerçeğin üstünde kalıyor |
| `fig2_cdf.pdf` | hata birikimli dağılımı, payda **uçuşun her karesi** |
| `fig3_law.pdf` | on uçuşta eşleşme oranı ↔ nihai hata |

İki tasarım kararı ölçüldükten sonra değişti:

1. **İki panel tek çerçeveye alındı.** Başta her panel kendi içeriğine göre
   ölçekleniyordu; okur iki farklı haritayı karşılaştırıyordu. Sürüklenmenin
   büyüklüğü ancak füzyonun çizildiği çerçevede okunur.
2. **CDF'in göstergesi kaldırıldı, eğriler doğrudan etiketlendi.** Tek sütun
   genişliğinde okunacak kadar büyük bir gösterge kutusu, tam da savı taşıyan
   bölgeyi kapatıyordu.

### arXiv paketi

`scripts/31_arxiv_bundle.py`. Klasörü sıkıştırmıyor; gönderimi bozan üç şeyi
tek tek denetliyor: arşivde kalmış `.aux`, metinde geçip diskte olmayan şekil,
ve her göreli yolu kıran fazladan üst dizin. Önce makaleyi baştan derliyor —
yerelde derlenmeyen kaynak sunucuda da derlenmez.

**Sınandı:** paket temiz bir dizine açıldı ve sıfırdan derlendi → 5 sayfa,
çözülmemiş referans yok. 4,9 MB (arXiv sınırı 50 MB).

Üstveri `paper/ARXIV.md`'de: `cs.CV` birincil, `cs.RO` çapraz liste, CC BY 4.0.

### Dizgi

- Başlık üç dengesiz satıra bölünüyordu; satır sonları elle ayarlandı.
- `"will this work here?"` düz tırnakla yazılmıştı, LaTeX ikisini de kapanış
  tırnağı basıyordu → `` ``...'' ``.

**Durum:** 5 sayfa, 3 şekil, 2 tablo. Gönderilmeye hazır; kalan tek iş
arXiv formunu doldurmak.

---

## Faz 11 — Gece: taban çizgisinin dürüst rakamları (2026-09-06)

05 Eylül'de gece termal kolunun taban çizgisi bir günde çıkarılmıştı
(`night/DURUM.md`). Elde bir bulgu vardı ama iki tanesi **güvenilemez**
sayıya dayanıyordu. Bu faz onları ölçtü.

### Kapı n=5 üstüne kuruluydu

`04_kapi.py` "%100 kesinlik / %45 duyarlılık" diyordu; kabul edilen kare
sayısı **beş**. DURUM'un kendi notu şüpheliydi: 5/5'in Wilson alt sınırı ~%57.

1000 karelik doğrulama koşuldu (~37 dk, RTX 3050 Ti). Sıralama değişmedi,
değerler biraz düştü:

| ölçüt | AUC n=1000 | AUC n=120 |
|---|---|---|
| yön uyumu | **0,878** | 0,885 |
| iç nokta | 0,803 | 0,854 |
| -ncc (dog) | 0,781 | 0,807 |
| karşılıklı bilgi | 0,489 | 0,521 |

1000 karenin 86'sında (%8,6) doğru fix var.

### Eşik ölçtüğü verinin üstünde seçiliyordu

Asıl sorun örneklem büyüklüğü değildi. `best_at_precision` eşiği, kesinliği
**ölçtüğü** karelerde arıyordu — az sayıda doğru fix varken geriye dönüp
bakınca hep kusursuz görünen bir eşik bulunur. Faz 7'deki "zarar verme
kuralı"nın aynısı burada eksikti.

`04_kapi.py` artık eşiği karelerin yarısında seçip diğer yarısında ölçüyor,
400 rastgele bölmeyle, medyan ve %10'luk dilim raporlanıyor.

**Dürüst rakam: %92 kesinlik / %28 duyarlılık** (eski: %100 / %45).

Aynı düzeltme ikinci bir hatayı açığa çıkardı: kazanan **yalnızca duyarlılığa**
göre seçiliyordu, yani en çok aşırı-uyan ölçüt kazanıyordu. 120 karelik koşuda
bu `-ncc_dog`'du — üç ölçüt içinde en yüksek duyarlılık, en düşük kesinlik.
Kapının bütün amacı kesinlik olduğu için sıralama düzeltildi: önce kesinlik
hedefini ayrık kümede tutturanlar süzülüyor.

### Kanıt figürü kendi metnini yalanladı

`night/05_kanit.py` üç kolu tek çift üzerinde gösteriyor. İlk çıktıda 2. satırın
başlığı "kendinden emin ve YANLIŞ" diyordu, altındaki ölçüm ise 16 px — yani
**doğru**. Seçim ölçütüm eksikti: "LoFTR kör + clahe+dog doğru" arıyordu, ama
RoMa ham karelerin %2'sinde doğru ve tam öyle bir çifte denk gelinmişti.

Ölçüt üçe çıkarıldı (RoMa ham *yanlış* da olmalı) ve satır başlıklarındaki
oranlar artık `night/sonuclar/` dosyalarından okunuyor, elle yazılmıyor.
Ayrıca ayak izi kutuları uydu panelinin dışına taşıyordu; kare merkezi +
hata oku ile değiştirildi.

Üretilenler: `figures/30_gece_neden.png`, `figures/31_gece_kanit.png`.

### Temsil ailesinin tavanı ölçüldü

02 her temsili tek tek ölçmüştü: sobel %12, dog %12, clahe+dog %16. Bu iki
bambaşka dünyayla uyumlu — aynı kolay kareler mi başarılı, farklı kareler mi?
Birincisiyse %16 tavana yakın; ikincisiyse birleşim çok daha büyük.

`night/06_uzlasma.py` kare bazında kayıt tutuyor. 150 kare, üç temsil:

| | doğru | sadece bu temsil |
|---|---|---|
| clahe+dog | %9 | 1 |
| sobel | %9 | 3 |
| dog | %7 | 0 |
| **birleşim** | **%11** | — |

**Aynı kareler.** 150 karenin 4'ü tek bir temsile özgü. Temsil eklemek
darboğazı açmaz — sıradaki adım eğitimli cross-modal eşleyici olmak zorunda.
Bu artık bir tahmin değil, ölçüm.

**Yan ürün:** iki temsil 20 px içinde aynı yeri gösteriyorsa kabul etmek,
`dog + sobel` için %82 kesinlik / %56 duyarlılık veriyor — 04'ün ayarlanmış
kapısı %92 / %28. Duyarlılık iki katı ve **ayarlanacak eşiği yok**: 20 px
zaten doğruluk toleransı. Güvenilir çapa oranı %2,4 → %6.

Ama n=11; 9/11'in Wilson alt sınırı ~%52. Bu rakam 1000 kareyle doğrulanmadan
kullanılamaz — ve bu fazın dersi tam olarak buydu.

**Ders (tekrar):** Küçük örneklemde seçilen eşik, kendi verisinde her zaman
iyi görünür. Ayırmadan ölçme.

---

## Faz 12 — Gecede de yasa var (2026-09-06)

Faz 11 şunu bırakmıştı: her temsil **aynı** %89'da başarısız. Bunun iki okuması
var ve maliyetleri bambaşka.

- *Eşleyici sorunu*: ortak yapı orada, LoFTR/RoMa kipler arası bulamıyor →
  eğitimli cross-modal eşleyici, günlerce GPU.
- *İçerik sorunu*: o karelerde bulunacak ortak yapı yok → eğitim de kurtarmaz.

Günlerce eğitmeden önce bir saatlik CPU ölçümü bunu ayırt eder. `07_yasa.py`:
her kareyi, eşleşme ve gerçek konum gerektirmeyen ölçütlerle puanla, doğru/
yanlış etiketiyle AUC'ye sok.

| ölçüt | AUC | ne zaman ölçülüyor |
|---|---|---|
| yapı skoru, zayıf taraf | **0,872** | eşleşmeden ÖNCE |
| **yapı skoru, sadece uydu karosu** | **0,852** | **eşleşmeden ÖNCE** |
| uydu yüksek frekans oranı (ters) | 0,799 | eşleşmeden ÖNCE |
| iç nokta sayısı | 0,803 | eşleşmeden sonra |
| yön uyumu | 0,878 | eşleşmeden sonra |

**Sadece haritadan okunan bir sayı, eşleşme yapıldıktan sonra ölçülen iç nokta
sayısından daha iyi yorduyor.** Decile'lara bölününce en yapısız onda birde
hiç doğru fix yok, en yapılıda %43.

Yani **içerik sorunu**, ve gündüzdeki yasanın gece karşılığı. Hatta daha güçlü
biçimde: gündüz yordayıcı (eşleşme oranı) planlanan rotada deneme eşleşmesi
istiyor, gecede sadece harita yetiyor.

**Kendi varsayımım ters çıktı.** Yüksek frekans enerjisini "yapı" sanıp öyle
kodladım; AUC 0,201 geldi — yani ters yönde güçlü bir yordayıcı. Kum benekleri
ve çalı ince dokudur, yapı değil: karoyu doldurur, eşleyiciye tutunacak bir şey
vermez. Betiğin ilk sürümü ham AUC'ye göre sıraladığı için **kendi en güçlü
sonucunu gömüyordu**; sıralama işaret duyarlı hâle getirildi.

### Yasa bir bileşen de oluyor (`08_birlesik.py`)

Ön ölçüt eşleşmeden önce hesaplandığı için maliyeti kesebilir, ve termal kareyi
hiç görmediğinden eşleyicinin söylediği her şeyden bağımsız.

| geçen kare | korunan doğru fix | elenen eşleşme |
|---|---|---|
| %70 | %98 | %30 |
| **%50** | **%90** | **%50** |
| %30 | %77 | %70 |

Aynı ayrık-küme protokolüyle kapılar:

| kapı | kesinlik | duyarlılık |
|---|---|---|
| sonra (04) | %92 | %28 |
| önce (sadece karo) | %90'a ulaşamıyor | — |
| **çarpım** | **%93** | **%34** |

Çarpım kapısı 04'ünkini kesin olarak geçiyor: aynı kesinlikte %21 fazla
duyarlılık, ön bileşen bedava. Güvenilir çapa %2,4 → %2,9.

Tek başına ön-kapının %90'a ulaşamaması beklenen: yapı içeriği hangi karenin
*tutabileceğini* söyler, hangisinin *tuttuğunu* değil.

### Makaleye girdi

Bulgu makalenin 3. katkısını doğrudan güçlendiriyor — yordayıcı ikinci bir
sensöre taşınıyor. `paper/geoanchor.tex`'e yarım sütunluk bir alt bölüm
eklendi (V-C), sistem olarak değil **yordayıcının kanıtı** olarak sunuluyor:
%3'lük güvenilir çapa oranı, tek veri kümesi ve %93/%34 kapı açıkça yazılıyor.
Makale 5 → 6 sayfa. Atıf: STHN (Xiao vd., IEEE RA-L 2024, arXiv:2405.20470) —
Boson-nighttime'ın kaynak makalesi.

### Mekân planı yanlışmış

Depo "arXiv ön baskısı, aynı metin şubatta SİU'ya" diyordu. SİU bildiri
çağrısına bakıldı: **en fazla 4 sayfa ve Türkçe** (yazarlardan biri Türkçe
anadilli değilse İngilizce kabul ediliyor — burada geçerli değil). Elimizdeki
6 sayfa ve İngilizce, yani "aynı metin" hiçbir zaman mümkün değildi.

SİU için ayrı bir Türkçe 4 sayfalık sürüm gerekiyor. Bu bir çeviri işi değil
editoryal karar: iki ikincil katkıdan biri (öz-kalibrasyon ya da eşleyici
çalışması) çıkarılırsa kalan metin tutarlı kalıyor. `paper/README.md`'de yazılı.

Ayrıca bir olgu düzeltildi: veri kümesi sadece çöl değil, **çöl + tarla + yol**
(33 km² termal, 216 km² uydu, 21:00-04:00 gece uçuşları).

---

## Faz 13 — Gece kolunun kapanışı (2026-09-06)

### Uzlaşma kapısı 1000 kareyle doğrulandı

Faz 11'in izi n=11'e dayanıyordu. `06_uzlasma.py 1000 dog,sobel`:

| | n=150 | **n=1000** |
|---|---|---|
| kesinlik | %82 (9/11) | **%82** (76/93) |
| duyarlılık | %56 | **%57** |

Sekiz kat veriyle neredeyse birebir tekrarladı.

**Ama aynı koşu kendi eski cümlemi çürüttü.** Faz 11'de "150 karenin sadece
4'ü tek bir temsile özgü, aynı kareleri buluyorlar" yazmıştım. 1000 karede:
dog 103, sobel 101 doğru, **ikisinde birden 71**, birleşim 133 — yani 62 kare
tek temsile özgü, örtüşme yarı yarıya. O "4" küçük örneklem artefaktıymış (ve
üç temsil arasında teklik arandığı için daha da sıkı bir ölçüttü).

Tavan iddiası ayakta kalıyor ama gerekçesi değişti: birleşim %13,3, en iyi tek
temsil %10,3. Her temsilin kazandığı özgün kareler ötekinin kaybettikleriyle
takas oluyor. Sınırlayan şey temsil değil, **eşleşebilir kare havuzu** — ve 07
havuzu neyin belirlediğini söylüyor.

### En iyi çalışma noktası

Uzlaşmanın sorunu kesinlikti (%82), ön-kapının sorunu tek başına karar
verememesiydi. Ön-kapı termal kareyi hiç görmediği için uzlaşmanın hatalarıyla
ilintisiz; ikisi birleşince:

| ön-kapı geçişi | kabul | kesinlik | duyarlılık | doğru çıkan kare | maliyet |
|---|---|---|---|---|---|
| yok | 93 | %82 | %57 | %7,6 | 2,0× |
| %50 | 78 | %91 | %53 | %7,1 | 1,0× |
| **%30** | 65 | **%95** | %47 | **%6,2** | **0,6×** |

Maliyet, kare başına RoMa çağrısı; taban çizgisi 1,0×. Uzlaşma baktığı her kare
için iki çağrı ister, ön-kapı kaç kareye bakılacağını belirler — bu yüzden %30
geçişte toplam maliyet taban çizgisinin **altına** düşüyor.

**Faz 11'in başlangıcına göre:** %92 → %95 kesinlik, %2,4 → %6,2 güvenilir
çapa, 1,0× → 0,6× hesap. 2,6 kat çapa, üç puan kesinlik, %40 az hesap. Ve iki
bileşenin de etiketlere uydurulmuş eşiği yok: 20 px doğruluk toleransının
kendisi, ön-kapı ise sabit bir yüzdelik.

### `scripts/32_tutarlilik.py`

README "buradaki her sayı `results/`'tan geliyor" diyor, makale de aynısını.
Bunu **doğrulayan** bir şey yoktu. Sayılar dört yerde alıntılanıyor
(README.md, README.tr.md, geoanchor.tex, night/DURUM.md) ve bir yeniden koşu
üçünü eskitip kendinden emin bırakıyor.

Betik sayıları JSON/NPZ'den yeniden türetip her belgede **o belgenin kendi
yazımıyla** arıyor. Üç yazım kuralını bilmesi gerekti, yoksa kendi biçimini
hata olarak raporluyor:

- ondalık ayracı: Türkçe 8,35 / İngilizce 8.35
- yüzde işareti: Türkçe %95 / İngilizce 95%
- LaTeX kaçışları: `95\%` ve `8.35\,m`

İlk koşuşta üçünü de yanlış yaptım ve betik kendi hatalarını gösterdi.
Şu an: **30 iddia, 57 dosya kontrolü, hepsi tutuyor.** Hata koduyla çıkıyor,
yani commit öncesi kapı olarak kullanılabilir.

### Makale

Gece bulgusu makaleye V-C olarak girdi ve son çalışma noktasıyla güncellendi:
%95 kesinlik, karelerin %6,2'si, kare başına 0,6 eşleyici çağrısı — ayarlanmış
tek-ölçüt kapısının %92 / %2,4 / 1,0×'ine karşı. Sistem olarak değil,
**yordayıcının kanıtı** olarak sunuluyor.

**Durum:** 6 sayfa, 3 şekil, 2 tablo, temiz dizinde derleniyor, arXiv paketi
hazır. Gece kolu: ölçülmüş bir yasa, ondan türetilmiş bir çalışma noktası ve
nereye bakılmayacağını söyleyen bir tavan.
