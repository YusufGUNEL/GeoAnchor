# SİU sürümü

`siu_geoanchor.tex` — Türkçe, 4 sayfa, anonim. `../geoanchor.tex`'in SİU'ya
gönderilebilir hâli.

**Bu ayrı bir metin, çevirisi değil.** Depoda bir dönem "aynı metin şubatta
SİU'ya" yazıyordu; bu hiçbir zaman mümkün değildi. SİU bildiri çağrısı üç şey
istiyor ve arXiv sürümü üçünü de karşılamıyor:

| | arXiv sürümü | SİU şartı |
|---|---|---|
| dil | İngilizce | **Türkçe** (yazarlardan biri Türkçe anadilli değilse İngilizce kabul ediliyor — burada geçerli değil) |
| uzunluk | 6 sayfa | **en fazla 4 sayfa** |
| kimlik | yazar ve GitHub bağlantısı var | **çift kör: anonim olmalı** |

## Neyin çıkarıldığı

4 sayfaya sığdırmak için iki bölüm tamamen çıktı:

- **Gece/termal bölümü (V-C).** Ayrı bir veri kümesi ve kare bazında bir
  bulgu; ana savı taşımıyor, yerini hak etmiyor.
- **Hata dağılımı şekli (fig2).** Aynı şeyi bileşen karşılaştırması paragrafı
  sayılarla söylüyor.

Kalanlar sıkıştırıldı ama duruyor: sıralı füzyon, öz-kalibrasyon,
konuşlandırılabilirlik yordayıcısı, eşleyici çalışması, ablasyon ve
dayanıklılık. İki şekil (yörünge, yasa) ve bir tablo var.

## Anonimlik

Çift kör değerlendirme için gönderim öncesi kontrol edin:

- [ ] `\author` bloğu boş (dosyada öyle bırakıldı)
- [ ] Metinde GitHub bağlantısı **yok** — arXiv sürümünde var, burada
      "kabul hâlinde yayımlanacaktır" yazıyor
- [ ] PDF üstverisinde ad yok: `pdfinfo siu_geoanchor.pdf` ile bakın;
      TinyTeX yazar adı gömmüyor ama derleyen makine değişirse kontrol edin
- [ ] arXiv ön baskısı yayımlandıysa, kendi çalışmanıza üçüncü şahıs gibi
      atıf yapın ya da hiç atıf yapmayın

## Şekiller

Türkçe etiketli, `../../scripts/30_paper_figures.py` ile aynı sonuç
dosyalarından üretiliyor:

```bash
python ../../scripts/30_paper_figures.py --tr
```

İngilizce sürümle tek fark dizeler; sayılar tek kaynaktan geldiği için iki
makalenin şekilleri birbirinden ayrı düşemiyor.

## Derleme

```bash
latexmk -pdf siu_geoanchor.tex
```

## Uyarı: şablon

Bu dosya IEEEtran kullanıyor, çünkü SİU 2026 çağrısında ayrı bir şablon
bağlantısı verilmiyordu. **SİU 2027 çağrısı açıldığında resmî şablonu indirip
karşılaştırın**; sayfa sınırı, sütun düzeni veya başlık biçimi değişmiş
olabilir. Gönderim Microsoft CMT üzerinden yapılıyor.
