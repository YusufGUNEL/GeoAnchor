# GeoAnchor Night — nerede kaldık

**Son güncelleme:** 2026-09-06

## Tek cümle

Gündüz sistemi gecede tamamen çöküyor (%0); yapısal temsil ile karelerin
%8,6'sında doğru fix çıkıyor ve **hangi karelerde çıkacağı önceden belli**:
uydu karosunun yapı içeriği, eşleşme daha denenmeden, doğru fix'i yanlıştan
**AUC 0,852** ile ayırıyor — eşleşme *sonrası* ölçülen iç nokta sayısından
(0,803) daha iyi. Yani gündüzdeki yasanın gece karşılığı var ve daha güçlü
biçimde: uçuş da, termal görüntü de, eşleşme de gerekmiyor, sadece harita.

Bu bir açıklama olmakla kalmıyor, bileşen olarak da işe yarıyor: ön-kapı ile
birleşik kapı **%93 kesinlik / %34 duyarlılık** veriyor (tek başına sonraki
kapı %92 / %28) ve karelerin yarısı eşleşme denenmeden eleniyor, doğru
fix'lerin %90'ı korunarak.

En iyi çalışma noktası bunların birleşimi: iki temsilin uzlaşması + ön-kapı,
**%95 kesinlik, karelerin %6,2'sinde doğru fix**, üstelik taban çizgisinin
**0,6 katı** hesapla. Başlangıç %92 / %2,4 / 1,0× idi.

Yine de bu çalışan bir gece sistemi değil: gündüz çapa oranı %70-100'dü.

## Veri

- **Boson-nighttime v1**, Hugging Face (`xjh19972/boson-nighttime`), kapılı ama
  anlık kabul. Hub'da MIT olarak listeli; kapıda kabul edilen şart **ticari
  olmayan araştırma ve eğitim kullanımı**. Veri Bing uydu görüntüsü içeriyor,
  o kısım Microsoft'un kendi telif şartlarına tabi.
- `night/veri/` ve `night/ornekler/` gitignore'da: 85 GB depoya konmaz, ve
  şartları zaten her kullanıcının kaynağında kendisi kabul etmesi gerekiyor.
  Betikler veriyi kendileri indiriyor.
- Arazi: **çöl, tarla ve yollar**; 33 km² termal, 216 km² uydu. Gece
  uçuşları (21:00-04:00), Boson termal kamera, Bing uydu haritası.
  Kaynak makale: STHN, Xiao vd., IEEE RA-L 2024 (arXiv:2405.20470).
- 74 GB indirildi, 85 GB açıldı: `night/veri/thermal_dataset/*.h5`
- Test kümesi: 26 568 **hizalı** termal/uydu çifti, 512x512.
  `test_queries.h5` termal, `test_database.h5` uydu, **aynı indeks = aynı yer**.
- Dosya adları `@a@b` grid koordinatı. Ölçüldü (`00_olcek.py`):
  **1 grid birimi = tam 1 piksel**, ve ikinci koordinat görüntüde **yatay** eksen.

## Ölçümler

Hepsi 70 px'lik bilinen gerçek kayma ile, sıfır kayma dejenere olduğu için.

| kol | doğru konum | kesinlik | not |
|---|---|---|---|
| uydu→uydu (tavan, LoFTR) | %100 | %100 | 0.1 px — boru hattı sağlam |
| termal→uydu, LoFTR, ham | **%0** | — | 100 karede sıfır iç nokta |
| termal→uydu, RoMa, ham | %2 | %2 | her kareyi kabul ediyor |
| termal→uydu, LoFTR, sobel | %12 | **%86** | seyrek ama dürüst |
| termal→uydu, RoMa, clahe+dog | **%16** | %16 | en çok doğru bulan |

### Doğrulama ölçütleri — 1000 kare (`03_dogrulama_1000.json`)

120 karelik ilk koşu tekrarlandı; sıralama aynı çıktı, değerler biraz düştü.

| ölçüt | AUC (n=1000) | AUC (n=120) |
|---|---|---|
| yön uyumu (gradyan yönü, cos 2Δ) | **0,878** | 0,885 |
| iç nokta sayısı | 0,803 | 0,854 |
| ncc (dog), ters işaretli | 0,781 | 0,807 |
| karşılıklı bilgi | 0,489 | 0,521 — işe yaramıyor |

Bu koşuda 1000 karenin **86'sında** (%8,6) doğru fix var.

### Kapı (`04_kapi.py`, 1000 kare)

`04_kapi.py` artık eşiği **karelerin yarısında seçip diğer yarısında ölçüyor**,
400 rastgele bölmeyle. Eski sürüm eşiği ölçtüğü verinin üstünde seçiyordu.

| ölçüt | örnek-içi kesinlik | **ayrık kümede** kesinlik (p10) | ayrık duyarlılık |
|---|---|---|---|
| yön × iç nokta | %93 | **%92** (%76) | **%28** |
| -ncc (dog) | %91 | %100 (%71) | %23 |
| iç nokta | %100 | %89 (%73) | %17 |
| yön uyumu | %90 kesinliğe ulaşamıyor | — | — |

**Eski "%100 kesinlik / %45 duyarlılık" rakamı iyimsermiş.** n=5 üstüne
kuruluydu ve DURUM'un kendi şüphesi doğrulandı: 1000 kareyle dürüst değer
%92 / %28.

Kazanan seçimi de düzeltildi: yalnızca duyarlılığa bakıyordu ve en *düşük*
kesinlikli ölçütü seçiyordu — kapının bütün amacına aykırı. Artık önce
kesinlik hedefini tutturanlar süzülüyor, sonra duyarlılığa bakılıyor.

## Bulgular (ana hikâye)

1. **Gündüz sistemi gecede bozulmuyor, çöküyor.** LoFTR 100 karede sıfır iç
   nokta. Bu bir derece kaybı değil, tam kayıp.
2. **Asıl sorun eşleştirme değil, güven.** Doğru cevap karelerin %9-16'sında
   zaten bulunuyor; sistem hangisinin doğru olduğunu bilmiyordu.
3. **Sinyal en başından elimizdeymiş.** "İç nokta sayısı gecede işe yaramıyor"
   diye yazmıştım, kendi ölçümüm çürüttü: AUC 0,803. İşe yaramayan şey sinyal
   değil, gündüzden kalma eşikti.
4. **Yapı kalıyor, görünüm gitmiyor.** Kum dokusu iki modalitede ortak değil;
   yollar, tarla sınırları, bina hatları ortak. Gradyan/bant-geçiren temsiller
   ibreyi sıfırdan kaldıran şey oldu.
5. **DINOv2 tek başına kurtarmıyor.** RoMa'nın kodlayıcısı zaten DINOv2;
   ham girdide %2'de kalıyor. "Anlamsal öznitelikler modaliteye dayanıklıdır"
   varsayımı bu veride tutmuyor — dayanıklılığı sağlayan şey temsil.

## Kanıt figürleri (`05_kanit.py`)

- `figures/30_gece_neden.png` — aynı yer, iki kip: ham görüntülerde ortak
  parlaklık yok, bant-geçirenden sonra yapı iki tarafta da çıkıyor.
- `figures/31_gece_kanit.png` — tek ve aynı çift üzerinde üç kol: LoFTR kör
  (9 ham karşılık, RANSAC'i geçen yok), RoMa ham kendinden emin ve 444 px
  yanlış, RoMa+clahe+dog 8 px.

Betik örneği elle seçmiyor: **üç satır başlığının da aynı anda doğru olduğu**
ilk çifti tarayıp buluyor. Ortadaki koşul (RoMa ham *yanlış* olmalı) şart —
RoMa ham karelerin %2'sinde doğru ve ilk denemede tam öyle bir çifte denk
gelinmişti, satır kendi metnini yalanlıyordu.

## Darboğaz ve sıradaki hamle

Güvenilir çapa oranı **~%2,4** (karelerin %8,6'sında doğru fix, 04'ün kapısı
%28'ini alıyor); aşağıdaki ön-kapıyla **%2,9**. GeoAnchor gündüz %70-100 ile
çalışıyordu. Sıradaki iş kapıyı iyileştirmek değil, **doğru fix sayısını
artırmak** — ve 07 bunun nerede mümkün olduğunu söylüyor.

### Temsiller aynı karelerde mi başarılı? (`06_uzlasma.py`, 150 kare)

02 her temsili tek tek ölçüp tek sayı veriyordu; bu iki bambaşka dünyayla
uyumluydu. Kare bazında kayıt tutunca ayrıldı:

| temsil | doğru | sadece bu temsil |
|---|---|---|
| clahe+dog | %9 (13/150) | 1 |
| sobel | %9 (13/150) | 3 |
| dog | %7 (11/150) | 0 |
| **birleşim** | **%11 (16/150)** | — |
| kesişim | %6 | — |

Birleşim en iyi tek temsilin ancak iki puan üstünde: bu yöntem ailesi
tavanına gelmiş, temsil eklemek darboğazı açmaz.

**Düzeltme (n=1000):** "150 karenin sadece 4'ü tek bir temsile özgü" küçük
örneklem artefaktıymış. 1000 karede dog+sobel ile: dog 103, sobel 101 doğru,
**ikisinde birden 71**, birleşim 133 — yani başarılar yalnızca yarı yarıya
örtüşüyor, 62 kare tek temsile özgü.

Tavan iddiası yine de ayakta ama gerekçesi farklı: birleşim %13,3, en iyi tek
temsil %10,3. Her temsilin kazandığı özgün kareler ötekinin kaybettikleriyle
takas oluyor; sınırlayan şey temsil değil, **eşleşebilir kare havuzu**. 07 bunun
nedenini söylüyor: havuzu belirleyen karo içeriği ve temsil onu değiştirmiyor.

### Beklenmedik: uzlaşma, ayarlanmış kapıdan iyi bir kapı

Aynı koşu ikinci bir şey ölçtü — iki temsil 20 px içinde **aynı yeri**
gösteriyorsa fix kabul edilsin (kabul edilen cevap ikisinin ortalaması):

| çift | kabul | kesinlik | duyarlılık |
|---|---|---|---|
| dog + sobel | 11 | **%82** (9/11) | %56 |
| clahe+dog + sobel | 13 | %77 (10/13) | %62 |
| clahe+dog + dog | 28 | %39 (11/28) | %69 |

`dog + sobel` **%82 kesinlik / %56 duyarlılık** veriyor; 04'ün ayarlanmış
tek-ölçüt kapısı %92 / %28. Duyarlılık iki katı, kesinlik on puan düşük.

Uzlaşmanın ayrı bir üstünlüğü var: **ayarlanacak eşiği yok.** 20 px zaten
doğruluk toleransı, veriye uydurulmuş bir sayı değil — 04'ün ayrık kümede
kaybettiği payı uzlaşma en baştan ödemiyor.

**n=11'di, 1000 kareyle doğrulandı:** %82 kesinlik / %57 duyarlılık, 93 kabul
edilmiş kare (76 doğru). Sekiz kat veriyle rakam neredeyse birebir tekrarladı.
Yine de %82, süzgecin kaldıramadığı şey olan kendinden emin yanlış fix için
yüksek; kesinliği yükseltmek gerekiyordu ve ön-kapı tam onu yaptı (aşağıda).

### Yasa: başarısızlık eşleyici sorunu değil, içerik sorunu (`07_yasa.py`, 1000 kare)

06 "hepsi aynı karelerde başarısız" dedi. Bunun iki okuması var ve bambaşka
işlere çıkıyor: *ortak yapı orada ama eşleyici bulamıyor* (→ eğitim gerekir)
ya da *o karelerde bulunacak ortak yapı yok* (→ eğitim de kurtarmaz).

Ayırt etmek için her kare, eşleşme ve gerçek konum gerektirmeyen ölçütlerle
puanlandı. Sonuç:

| ölçüt | AUC | yön |
|---|---|---|
| zayıf taraf yapı skoru | **0,872** | yüksek=iyi |
| **uydu karosu yapı skoru** | **0,852** | yüksek=iyi |
| uydu yüksek frekans oranı | 0,799 | **DÜŞÜK=iyi** |
| uydu kenar yoğunluğu | 0,746 | yüksek=iyi |
| *(karşılaştırma)* iç nokta — eşleşme SONRASI | 0,803 | |
| *(karşılaştırma)* yön uyumu — eşleşme SONRASI | 0,878 | |

**Sadece haritadan okunan bir sayı (0,852), eşleşme yapıldıktan sonra ölçülen
iç nokta sayısından (0,803) daha iyi yorduyor.** Decile'lara bölününce: en
yapısız onda birde **hiç** doğru fix yok, en yapılıda **%43**.

Bir varsayımım ters çıktı: yüksek frekans enerjisini "yapı" sanmıştım, AUC
0,201 verdi — yani **ters** yönde güçlü bir yordayıcı (0,799). Kum benekleri ve
çalı ince doku üretiyor, yapı değil; karoyu doldurup tutunacak bir şey
bırakmıyor. `yapi_skoru` bu yüzden kenar yoğunluğu **eksi** yüksek frekans.

![Gece yasası](../figures/32_gece_yasa.png)

### Ön-kapı: karo kötüyse eşleştirme (`08_birlesik.py`)

Yasa açıklama olmakla kalmıyor, bileşen de oluyor. Ön ölçüt eşleşmeden önce
hesaplandığı için maliyeti kesebilir ve termal kareyi hiç görmediğinden
eşleyicinin söylediği her şeyden istatistiksel olarak bağımsız.

| geçen kare | korunan doğru fix | elenen eşleşme |
|---|---|---|
| %70 | %98 | %30 |
| **%50** | **%90** | **%50** |
| %30 | %77 | %70 |
| %10 | %50 | %90 |

Kapı karşılaştırması (aynı ayrık-küme protokolü, 400 bölme):

| kapı | kesinlik | p10 | duyarlılık |
|---|---|---|---|
| sonra (04'ün kapısı) | %92 | %76 | %28 |
| önce (sadece karo) | %90'a ulaşamıyor | — | — |
| **çarpım (önce × sonra)** | **%93** | %75 | **%34** |
| önce VE sonra (%50 geçiş) | %89 | %80 | %36 |

**Çarpım kapısı 04'ünkinden kesin olarak iyi:** aynı kesinlikte %21 daha fazla
duyarlılık, üstelik ön bileşen bedava. Güvenilir çapa %2,4 → %2,9.

Tek başına ön-kapı %90 kesinliğe ulaşamıyor — beklenen: yapı içeriği hangi
karelerin *tutabileceğini* söylüyor, hangisinin *tuttuğunu* değil.

### En iyi çalışma noktası: uzlaşma + ön-kapı

Uzlaşmanın sorunu kesinlikti (%82), ön-kapının sorunu tek başına karar
verememesiydi. İkisi birbirini tamamlıyor: ön-kapı termal kareyi hiç görmediği
için uzlaşmanın hatalarıyla ilintisiz.

| ön-kapı geçişi | kabul | kesinlik | duyarlılık | doğru çıkan kare | maliyet |
|---|---|---|---|---|---|
| yok | 93 | %82 | %57 | %7,6 | 2,0× |
| %70 | 84 | %89 | %56 | %7,5 | 1,4× |
| %50 | 78 | %91 | %53 | %7,1 | 1,0× |
| **%30** | **65** | **%95** | %47 | **%6,2** | **0,6×** |

Maliyet = kare başına RoMa çağrısı; taban çizgisi (tek temsil, her kare) 1,0×.
Uzlaşma kare başına iki çağrı ister, ön-kapı kaç kareye bakılacağını belirler.

**Başlangıçla karşılaştırma:**

| | kesinlik | doğru çıkan kare | maliyet |
|---|---|---|---|
| 04'ün kapısı | %92 | %2,4 | 1,0× |
| **uzlaşma + ön-kapı (%30)** | **%95** | **%6,2** | **0,6×** |

2,6 kat çapa, 3 puan fazla kesinlik, %40 az hesap.

### Sıradaki

1. ~~Uzlaşma kapısını 1000 kareyle doğrula~~ — yapıldı, %82/%57.
2. Eğitimli cross-modal eşleştirme (STHN/UASTHN hattı bu veriyle homografi ağı
   eğitiyor; train bölümü diskte). Ama 07'den sonra beklenti düştü: eğitim de
   olmayan yapıyı bulamaz. Ölçülebilir hedef, yapı skoru yüksek karelerdeki
   %43'ü yukarı çekmek — düşük skorluları değil.
3. Temsil taramasını genişletmek (phase congruency, yapı tensörü) — 06'nın
   sonucundan sonra **düşük öncelik**: yeni temsil de aynı kareleri bulacak.

## Dosyalar

```
night/indir.py         veri indirme + akış halinde acma
night/00_olcek.py      grid biriminin piksel karsiligi + ayni-modalite tavani
night/01_taban.py      uc kol: tavan / LoFTR gece / RoMa gece
night/02_kopru.py      temsil taramasi (ham, clahe, sobel, dog, canny, ...)
night/03_dogrulama.py  dogru fix'i yanlistan ayiran olcut arayisi
night/04_kapi.py       calisma noktasi: ayrik kumede esik secimi
night/05_kanit.py      kanit figurleri (figures/30_*, figures/31_*)
night/06_uzlasma.py    temsiller ayni karelerde mi basarili?
night/07_yasa.py       basarisizlik esleyici sorunu mu, icerik sorunu mu?
night/08_birlesik.py   on-kapi + sonraki kapi birlikte ne veriyor?
night/sonuclar/*.json  her kosunun ciktisi
```
