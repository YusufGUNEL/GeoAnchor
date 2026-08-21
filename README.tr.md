# GeoAnchor — GPS'siz İHA Mutlak Görsel Konumlandırma

*[English version: **[README.md](README.md)**]*

GPS'i karıştırılan bir İHA nerede olduğunu bilmez. Görsel odometri bağıl
hareketi verir ama **sürüklenir** — bu 74 km'lik uçuşta sonunda **2,8 km**
şaşıyor. Kamerayı uydu haritasıyla eşlemek mutlak konum verir ama **kare kare
güvenilmez** — bu uçuşta karelerin **%23'ünde** hiç tutmuyor (su üstü, tekdüze
tarla, tekrar eden yapı deseni).

GeoAnchor ikisini bir parçacık süzgecinde birleştirir. Tek başına hiçbiri
yetmiyor; birlikte, **hiçbir uydu sinyali olmadan**, sürekli ve sürüklenmesiz
metre seviyesi konum veriyorlar.

![Karşılaştırma](figures/10_karsilastirma.png)

---

## Ana sonuç

Gerçek bir İHA tarama uçuşu (UAV-VisLoc, uçuş 03): **768 kare, 74 km, 77
dakika, 466 m irtifa**, Taizhou'nun 8,8 × 7,3 km'lik uydu ortofotosu üzerinde.
Gerçek konum işlenmiş GNSS verisi — düz uçuş hatlarındaki ölçülen sapma
**1,5 m**, yani referansın kendisi temiz.

| | Kapsama | Medyan hata | %90 dilim | 10 m içinde | Kare başına eşleme |
|---|---|---|---|---|---|
| Sadece görsel odometri | %100 | **2803 m** sürükleniyor | — | %0 | 0 |
| Tek kare harita eşlemesi | **%76,6** | 5,46 m | 10,71 m | %66,1 | 3,80 |
| **GeoAnchor (füzyon)** | **%100** | **6,20 m** | 14,76 m | **%76,8** | **1,52** |

Uydu eşlemesinin tamamen çöktüğü dört kesim hariç tutulduğunda (karelerin
%5,7'si — bkz *Dürüst sınırlar*), füzyon **medyan 5,97 m, %90 dilim 11,97 m,
20 m içinde %99,9** tutturuyor.

![Hata dağılımı](figures/13_dagilim.png)

Füzyon iki girdisinden de doğru olmakla kalmıyor, her karede haritanın
tamamını aramaktan **2,5 kat daha ucuz** — çünkü kabaca nerede olduğunu
bilmek, küresel aramayı tek bir yerel kontrole indiriyor.

---

## Bu neden "uydu haritasında görüntü arama" değil

İHA çapraz görüş coğrafi konumlandırma literatürü ezici çoğunlukla **tek
görüntü** getirme üzerine kurulu ve standart kıyas kümesi doygun
(University-1652, Mart 2026 itibarıyla %97,5 Recall@1). Ama gerçek bir İHA tek
fotoğraf çekmez — bir **yörünge** uçar. Güncel İHA literatüründe bunu
kullanan neredeyse hiçbir şey yok. En yakın iş olan *BEV-Patch-PF* (Aralık
2025) sıralı Bayesçi süzgeç kullanıyor ama **yer araçları** için.

GeoAnchor diziyi merkeze alıyor:

1. **Görsel odometri** hareket modelini verir.
2. **Uydu eşlemesi** mutlak düzeltmeleri verir — ve başarısız olmasına izin verilir.
3. **Parçacık süzgeci** birden çok hipotezi taşır, aykırı ölçümü eler,
   eşlemenin kesildiği yerde kendi başına devam eder.
4. **Harita, uçağın kendi duyargalarını çevrimiçi kalibre eder** (aşağıda).

---

## Beklemediğim kısım: sistem kendi pusulasını kalibre ediyor

Kuzey-yukarı yapılmış İHA karesini kuzey-yukarı uydu karosuna oturtan
homografinin bir dönme bileşeni vardır. Bu artık dönme sıfır değilse,
**yönelim açısının kendisi tam o kadar yanlıştır.**

Uçuş boyunca ölçünce, yönelim hatasının uçağın hangi yöne baktığına göre
değiştiği çıktı: kuzeybatı kollarında **−1,93°**, güneydoğu kollarında
**−7,08°**. Yöne bağlı bu imza, manyetometrenin sert-demir hatasının klasik
parmak izi — uçaklarda "compass swing" ile düzeltilen şey.

Gerçek konumla çapraz kontrol doğruladı: GNSS'ten hesaplanan odometri yön
sapması **+1,65°** ve **+7,22°** — aynı büyüklükler, geometrinin öngördüğü
gibi ters işaretle.

| | Haritadan ölçülen (GNSS yok) | Gerçek konumdan hesaplanan |
|---|---|---|
| Kuzeybatı kolları | −1,93° (σ 0,86) | +1,65° |
| Güneydoğu kolları | −7,08° (σ 1,73) | +7,22° |

Yani uçak, kendi pusula sapmasını haritaya bakarak, hiçbir uydu sinyali
olmadan ölçüp düzeltebiliyor. Bunu odometriye geri beslemek sürüklenmeyi kat
edilen yolun **%3,795'inden %0,865'ine** indirdi — 74 km'de 2803 m → 639 m.
Aynı numarayla ölçek de kurtarılıyor: arazi yüksekliği değiştikçe gerçek yer
örnekleme aralığı kayıyor, homografinin ölçek bileşeni bunu ele veriyor.

---

## Verinin sakladığı iki şey daha

**Veri kümesinin kendi üstverisi iki yerde yanlış.** İkisi de belgeyi okuyarak
değil, ölçerek bulundu.

1. *Duruş kanalları yer değişmiş.* Veri kümesi "Omega = eğim, Kappa = yalpa"
   diyor. Konum hatasını gövde çerçevesinde regresyona sokunca iz-boyu hata
   Kappa ile **+0,981** katsayısıyla (R² 0,677), iz-dışı hata Omega ile
   **−0,972** katsayısıyla (R² 0,765) açıklanıyor. Katsayıların ±1'e oturması,
   fiziğin (yerdeki kayma = irtifa × tan θ) birebir doğru olduğunu, sadece
   etiketlerin ters olduğunu gösteriyor.

2. *Kamera yönelimi Phi2 değil, Phi1.* Phi2 uçuşun yer üstündeki rotasıyla
   medyan 0,00° farkla örtüşüyor — ikna edici görünüyor. Ama uyduyla LoFTR
   eşlemesi Phi1 ile ~0°, Phi2 ile ~12° artık açı bırakıyor. Aradaki 12°
   rüzgâr kaynaklı yengeç açısı: Phi1 burnun baktığı yön, Phi2 uçağın
   gerçekten gittiği yön.

**Kamera 2° öne bakacak şekilde monteliymiş.** 466 m irtifada 2°'lik eğim,
görüntü merkezini yerde uçağın **16 m** önüne koyuyor. Hatanın tek en büyük
kaynağı buydu. Uçuşun ilk %20'sinde kalibre edilip kalan %80'de ölçüldü:

| | Önce | Sonra |
|---|---|---|
| Medyan hata | 16,82 m | **6,12 m** |
| 5 m içinde | %2,6 | **%40,0** |
| 10 m içinde | %17,4 | **%80,9** |

---

## Nasıl çalışıyor

```
İHA karesi ──−yönelim kadar döndür, irtifayla ölçekle──► kuzey-yukarı, metrik kırpma
                                                              │
                    ┌─────────────────────────────────────────┤
                    ▼                                         ▼
        DINOv2 küresel tanımlayıcı                   LoFTR yoğun eşleme
        (2709 uydu karosu indekslenmiş)              400 m'lik kırpmaya karşı
                    │                                         │
                    │ aday bölgeler                           │ homografi
                    ▼                                         ▼
              ┌───────────────────────────────────────────────────┐
              │  duruş düzeltmesi: görüntü merkezi → uçak konumu   │
              │  çevrimiçi kalibrasyon: pusula sapması, ölçek      │
              └───────────────────────────────────────────────────┘
                                    │
   görsel odometri ────────────────►│ PARÇACIK SÜZGECİ ──► konum + belirsizlik
   (SIFT, ardışık kareler)          │  hareket + çok tepeli ölçüm
                                    └──────────────────────────────────
```

**Neden Kalman değil parçacık süzgeci.** Uydu eşlemesinin hatası Gauss değil.
Çoğu zaman birkaç metreyle doğru; ama arada bir tam bir özgüvenle bambaşka
bir yeri gösteriyor (benzer tarla, bir sokak ötedeki aynı yapı deseni). Bu
dağılım çok tepeli ve ağır kuyruklu. Kalman süzgeci tek tepeli Gauss varsayar
ve böyle bir aykırı ölçüm onu kalıcı olarak yanlış yere çeker. Parçacık
süzgeci birkaç hipotezi canlı tutup zamanla hangisinin uçuşla tutarlı olduğuna
karar veriyor; olabilirliğe eklenen düz "aykırı değer tabanı" da tek bir kötü
ölçümün tüm inanışı silmesini engelliyor.

**Harita eşlemesinde neden SIFT değil LoFTR.** Uydu görüntüsü uçuştan farklı
bir mevsimden — altın sarısı sonbahar tarlalarına karşı koyu yeşil olanlar,
farklı güneş açısı, henüz yapılmamış binalar. Aynı dört karede ölçüldü: SIFT
12/4/24/7 iç nokta verdi, LoFTR **104/21/280/140**. Dedektörsüz yoğun eşleme
görünüm farkını aşıyor, klasik köşe noktaları aşamıyor. (SIFT ardışık İHA
kareleri arasındaki odometride kullanılıyor — orada görünüm farkı yok, üstelik
daha hızlı ve CPU'da çalışıp GPU'yu harita eşlemesine bırakıyor.)

---

## Dürüst sınırlar

Hiçbir şey abartılmasın diye önce bunlar yazıldı.

- **Özelliksiz arazide uydu eşlemesi çöküyor.** Dört kesimde (karelerin %5,7'si,
  en uzunu 21 kare ≈ 2 km uçuş) sıfır iç nokta çıktı. Orada süzgeç odometriyle
  devam ediyor ve yeniden çapa atana kadar en fazla 338 m'ye kadar bozuluyor.
  Bu gerçek ve şekilde kırmızı noktalarla görünüyor — üstü örtülmedi.
- **Çevrimdışı işleniyor**, uçuş sırasında uçakta değil. Dizüstü RTX 3050 Ti'de
  kare başına 866 ms; bu veri kümesinde kareler 7 saniyede bir geliyor, yani
  *bu uçuş için* rahatça gerçek zamanlı — ama gömülü donanımda denenmedi.
- **Duruş ve irtifa mevcut varsayılıyor** (ataletsel ölçüm birimi ve
  barometre/altimetre). İkisi de uyduya bağlı değil ve bu, AnyVisLoc kıyas
  kümesinin kullandığı protokolle aynı — ama yine de bir varsayım, üstelik
  yukarıdaki pusula bulgusu o duyargaların da kusursuz olmadığını gösteriyor.
- **Montaj kalibrasyonu uçuşun ilk %20'sini kullanıyor.** Gerçek sistemlerde
  bu kurulumda bir kez yapılır; burada veriden yapıldı ve raporlanan her şey
  ayrılan geri kalan kısımda ölçüldü.
- **Tek uçuş, tek bölge, tek mevsim.** Taizhou düz bir nehir deltası. Burada
  hiçbir şey dağlık arazide, gece veya kışın nasıl davranacağını göstermiyor.
- **Pusula sapma eğrisi sadece iki yönelimde uyduruldu**, çünkü tarama deseni
  sadece iki yön uçuyor. Fiziksel model (sert-demir hatası) yönelime bağlı bir
  sinüs öngörüyor ama bu uçuş onu belirleyemez — iki yönle bu, pratikte iki
  noktalı bir çizelgedir.
- **Düzlemsel homografi varsayımı.** Dik bakan kareler için geçerli (burada
  eğim ve yalpa ±5° içinde kalıyor), eğik bakışta zayıflar. Bina yüksekliğinden
  gelen kayma en büyük artık hata kaynağı ve tabanın ~1 m değil ~6 m olmasının
  sebebi bu.

---

## Yeniden üretmek için

```bash
pip install torch torchvision timm kornia opencv-python rasterio gdown \
            numpy pandas matplotlib imageio

# 1. veri (UAV-VisLoc'un 2,04 GB'lık örneği, uçuş 03)
python -m gdown "https://drive.google.com/uc?id=16tY7tPZiNIoyAhknvyXnp0jAfccIcHtL"

python scripts/00_inspect.py          # coğrafi referansı doğrula, ölçeği kestir
python scripts/01b_convention.py      # yönelim konvansiyonunu deneyle belirle
python scripts/02_build_tiledb.py     # 2709 karo için DINOv2 tanımlayıcıları
python scripts/03a_cache_northup.py   # kuzey-yukarı İHA kırpmalarını önbelleğe al
python scripts/03b_cache_tiles.py
python scripts/03c_retrieval_sweep.py # getirme kalitesi taraması
python scripts/04f_oracle2.py         # eşleme doğruluk tavanı
python scripts/05_single_frame.py     # FAZ 1 temel hat
python scripts/06_odometry.py         # FAZ 2 odometri + sürüklenme
python scripts/06c_yaw_from_map.py    # pusula sapmasını haritadan ölç
python scripts/07_sequential.py       # FAZ 3 füzyon  ← ana sonuç
python scripts/08_robustness.py       # FAZ 4 bozulma + ölçüm kesintisi
python scripts/11_ablation.py         # FAZ 5 ablasyon
python scripts/09_figures.py          # şekiller
python scripts/10_demo_video.py       # gösterim videosu
```

Kullanılan donanım: Windows 11 dizüstü, **NVIDIA RTX 3050 Ti, 4 GB VRAM**.
En yüksek kullanım 1,4 GB — buradaki hiçbir şey veri merkezi kartı istemiyor.

## Dosya düzeni

```
src/geo.py              coğrafi referans, pencereli GeoTIFF erişimi, metrik kırpma
src/flight.py           uçuş dizisi yükleme
src/features.py         DINOv2 küresel tanımlayıcıları (CLS + GeM)
src/tiles.py            uydu karo ızgarası ve tanımlayıcı veritabanı
src/matching.py         LoFTR sarmalayıcı + RANSAC benzerlik
src/geometry.py         duruş kaynaklı kayma modeli, montaj kalibrasyonu
src/localize.py         tek kare konumlandırma (getirme → doğrula → düzelt)
src/odometry.py         ardışık kareler arası görsel odometri
src/particle_filter.py  ölçüm güdümlü enjeksiyonlu parçacık süzgeci
src/sequential.py       birleşik sıralı sistem + çevrimiçi kalibrasyon
src/degrade.py          altı gerçekçi görüntü bozulması
```

`ILERLEME.md` tam çalışma günlüğü: her ölçüm, her çıkmaz sokak, bulunan her
hata ve neye mal olduğu. İş yapılırken yazıldı.

## Veri

UAV-VisLoc (Xu vd., 2024, arXiv:2405.11936) — uçuş 03, ticari olmayan
araştırma için yayımlandı. Uydu haritası veri kümesiyle birlikte geliyor.

## Lisans

Kod MIT. Veri kümesi kendi şartlarına tabi.
