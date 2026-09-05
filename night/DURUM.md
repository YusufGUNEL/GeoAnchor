# GeoAnchor Night — nerede kaldık

**Son güncelleme:** 2026-09-05

## Tek cümle

Gece termal konumlandırmanın taban çizgisi bir günde çıkarıldı: gündüz sistemi
gecede tamamen çöküyor (%0), yapısal temsil + yeniden ayarlanmış eşik ile
güvenilir ama seyrek fix üretilebiliyor; darboğaz artık doğru fix'in azlığı.

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

Doğrulama ölçütleri (RoMa + clahe+dog, 120 kare, `03_dogrulama.py`):

| ölçüt | AUC |
|---|---|
| yön uyumu (gradyan yönü, cos 2Δ) | **0.885** |
| iç nokta sayısı | 0.854 |
| -ncc (dog) | 0.807 (ters işaretli) |
| karşılıklı bilgi | 0.521 — işe yaramıyor |

Kapı (`04_kapi.py`): iç nokta eşiği **15 → 2958** ile %100 kesinlik / %45
duyarlılık. **Ama n=5**; 5/5'in Wilson alt sınırı ~%57, bu rakama güvenilmez.

## Yarın ilk iş

1000 karelik doğrulama koşusu yarıda kaldı (oturum kapandı). Tekrar başlat:

```bash
cd C:\Dark\GeoAnchor
python night/03_dogrulama.py 1000      # ~25 dk, RTX 3050 Ti
python night/04_kapi.py                # kapı çalışma noktası
```

`04_kapi.py` şu an `03_dogrulama.json`'u okuyor; 1000'lik koşu
`03_dogrulama_1000.json` yazacak, dosya adını oraya çevir.

## Bulgular (ana hikâye)

1. **Gündüz sistemi gecede bozulmuyor, çöküyor.** LoFTR 100 karede sıfır iç
   nokta. Bu bir derece kaybı değil, tam kayıp.
2. **Asıl sorun eşleştirme değil, güven.** Doğru cevap karelerin %9-16'sında
   zaten bulunuyor; sistem hangisinin doğru olduğunu bilmiyordu.
3. **Sinyal en başından elimizdeymiş.** "İç nokta sayısı gecede işe yaramıyor"
   diye yazmıştım, kendi ölçümüm çürüttü: AUC 0.854. İşe yaramayan şey sinyal
   değil, gündüzden kalma eşikti. (Bu düzeltme `03_dogrulama.py` başlığında da
   duruyor.)
4. **Yapı kalıyor, görünüm gitmiyor.** Kum dokusu iki modalitede ortak değil;
   yollar, tarla sınırları, bina hatları ortak. Gradyan/bant-geçiren temsiller
   ibreyi sıfırdan kaldıran şey oldu.

## Darboğaz ve sıradaki hamle

Güvenilir çapa oranı **~%4** (karelerin %9'unda doğru fix var, kapı yarısını
alıyor). GeoAnchor gündüz %70-100 ile çalışıyordu. Yani sıradaki iş kapıyı
iyileştirmek değil, **doğru fix sayısını artırmak**:

- eğitimli cross-modal eşleştirme (literatürdeki STHN/UASTHN hattı bu veriyle
  homografi ağı eğitiyor)
- ya da DINOv2 gibi anlamsal özniteliklerin modalite dayanıklılığını ölçmek
- temsil taramasını genişletmek (phase congruency, yapı tensörü)

Ayrıca yapılmadı: **kanıt figürü** — LoFTR'ın hiçbir şey bulamadığını,
RoMa'nın yanlış yere bağladığını gösteren yan yana görsel. README'nin ve
paylaşımın merkezi bu olacak.

## Dosyalar

```
night/indir.py         veri indirme + akış halinde acma
night/00_olcek.py      grid biriminin piksel karsiligi + ayni-modalite tavani
night/01_taban.py      uc kol: tavan / LoFTR gece / RoMa gece
night/02_kopru.py      temsil taramasi (ham, clahe, sobel, dog, canny, ...)
night/03_dogrulama.py  dogru fix'i yanlistan ayiran olcut arayisi
night/04_kapi.py       calisma noktasi: kesinlik hedefiyle esik secimi
night/sonuclar/*.json  her kosunun ciktisi
```
