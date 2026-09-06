# GeoAnchor Night — nerede kaldık

**Son güncelleme:** 2026-09-06

## Tek cümle

Gündüz sistemi gecede tamamen çöküyor (%0); yapısal temsil + yeniden ayarlanmış
kapı ile **güvenilir ama seyrek** fix üretiliyor — 1000 kareyle ölçülen dürüst
rakam **%92 kesinlik / %28 duyarlılık**, yani karelerin ancak **~%2,4'ünde**
güvenilebilir bir çapa var. İki temsilin uzlaşmasını kapı olarak kullanmak bunu
%6'ya çıkarıyor (%82 kesinlikle, n=11 — doğrulanması gerek). Temsil ailesinin
tavanı ölçüldü: birleşim %11, en iyi tek temsil %9, yani sıradaki gerçek adım
eğitimli cross-modal eşleyici.

## Veri

- **Boson-nighttime v1**, Hugging Face (`xjh19972/boson-nighttime`), kapılı ama
  anlık kabul. **Ticari olmayan araştırma kullanımı**, yeniden dağıtım yasak —
  bu yüzden `night/veri/` ve `night/ornekler/` gitignore'da.
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

Güvenilir çapa oranı **~%2,4** (karelerin %8,6'sında doğru fix, kapı %28'ini
alıyor). GeoAnchor gündüz %70-100 ile çalışıyordu. Sıradaki iş kapıyı
iyileştirmek değil, **doğru fix sayısını artırmak**.

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

**Temsiller aynı kareleri buluyor.** Birleşim en iyi tek temsilin ancak iki
puan üstünde, 150 karenin sadece 4'ü tek bir temsile özgü. Yani bu yöntem
ailesi tavanına gelmiş: temsil eklemek darboğazı açmaz. Sıradaki adım
**eğitimli cross-modal eşleyici** olmak zorunda.

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
Güvenilir çapa oranı %2,4 → **%6**'ya çıkıyor.

Uzlaşmanın ayrı bir üstünlüğü var: **ayarlanacak eşiği yok.** 20 px zaten
doğruluk toleransı, veriye uydurulmuş bir sayı değil — 04'ün ayrık kümede
kaybettiği payı uzlaşma en baştan ödemiyor.

**Ama n=11.** 9/11'in Wilson alt sınırı ~%52. Bu rakama şu hâliyle
güvenilmez; 1000 karelik koşu gerekiyor. Ve süzgecin kaldıramadığı şey tam
olarak kendinden emin yanlış fix, yani %82 muhtemelen yetmez.

### Sıradaki

1. `06_uzlasma.py 1000` — uzlaşma kapısının kesinliği gerçekten %82 mi.
2. Eğitimli cross-modal eşleştirme (STHN/UASTHN hattı bu veriyle homografi ağı
   eğitiyor; train bölümü diskte). Temsil tavanı ölçüldüğü için bu artık bir
   tahmin değil, ölçüme dayanan tek yol.
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
night/sonuclar/*.json  her kosunun ciktisi
```
