# Paylaşım — LinkedIn

Tek gönderi, Türkçe. İngilizce ayrı bir LinkedIn gönderisi yok, çift dilli tek
gönderi de yok: LinkedIn'de sizi takip edenler Türk, ve aynı metni iki kez
okumak zorunda kalan kimse ikisini de okumaz. Uluslararası taraf zaten kapalı
— README, Space, makale ve handbook İngilizce; gönderi onlara bağlantı veriyor.

Kullanmadan önce oku ve kendi ağzınla düzelt. Buradaki her sayı ölçüldü, abartı
yok, o yüzden rahatça savunabilirsin. "Bunu nasıl yaptın" diye sorulursa
`ILERLEME.md` tam günlük.

Reddit taslağı için: `PAYLASIM-EN.md`.

---

## Gönderi

> Görsel olarak `figures/demo.gif` ekle. Bağlantıları ilk yoruma koy —
> LinkedIn, gövdesinde dış bağlantı olan gönderiyi daha az kişiye gösteriyor.

---

GPS'i karıştırılan bir İHA nerede olduğunu bilmez.

Son günlerde bunun üzerine çalıştım. Elimde iki şey vardı: aşağı bakan bir
kamera ve önceden indirilmiş bir uydu haritası.

İki yöntem var, ikisi de tek başına yetmiyor:

→ Kareler arası hareketi takip etmek sürekli çalışır ama hata birikir.
  74 km'lik gerçek bir uçuşta sonunda 2,8 kilometre şaşıyor.

→ Kamerayı uydu haritasıyla eşlemek hata biriktirmez ama kare kare
  güvenilmez. Aynı uçuşta karelerin dörtte birinde hiç tutmadı.

İkisini bir parçacık süzgecinde birleştirdim. Sonra en önemli kısmı yaptım:
tek uçuşta durmadım, **on gerçek uçuşta** denedim — 406 metreden 2572
metreye irtifa, 2016'dan 2023'e tarih, uçuş başına 9 ile 103 kilometre.

Sonuçlar ikiye ayrıldı. Yedi uçuşta 8 ile 25 metre arası, karelerin
%99,7'sinde konum. Üç uçuşta ise sistem çöktü.

İlginç olan kısım şu: **hangi uçuşun hangi gruba düşeceğini önceden söyleyen
tek bir ölçülebilir şey var.** İrtifa değil — 2572 metredeki uçuş çalışıyor,
551 metredeki çöküyor.

Belirleyici olan, İHA görüntüsünün uydu haritasıyla ne kadar örtüştüğü.
Bunu gerçek konumu bilerek ölçtüm: eşleşme oranı %50'nin üstündeyse sistem
çalışıyor, altındaysa çöküyor. Korelasyon −0,77.

Bunun pratik karşılığı var: bir görev planlanırken, **uçmadan önce** o rota
üzerinde bu ölçüm yapılabilir. Yani sistemin orada işe yarayıp yaramayacağı
önceden bilinebilir.

Beklemediğim bir sonuç da çıktı. Darboğaz eşleme kalitesiydi, o yüzden LoFTR
yerine bugünün en iyi eşleyicisini (RoMa) denedim. Çöken uçuşlarda eşleşme
oranı %12'den %96'ya fırladı — çözülmüş göründü. Uçtan uca çalıştırınca hata
22 metreden 1669 metreye çıktı.

Sebebi şu: kıyaslama yanlış soruyu soruyordu. Her iki eşleyiciye de sadece
**doğru** karoyu gösteriyordum. Oysa bir konumlandırma sistemi mesaisinin
çoğunu "burası doğru yer mi" sorusuna harcar. İlgisiz bir karoyla denediğimde
LoFTR sıfır eşleşme veriyor, RoMa 341. **Bir eşleyicinin buradaki değeri ne
kadar eşleştirdiğiyle değil, susması gerektiğinde susabilmesiyle ölçülüyor** —
ve eşleştirme kıyas kümeleri bunu hiç ölçmüyor.

Yol boyunca üç şey daha buldum, hiçbiri belgelerde yazmıyordu:

• Kamera 2 derece öne eğik monteliymiş. 466 metre irtifada bu, yerde 16 metre
  kayma demek — hatanın tek en büyük kaynağıydı.

• Uçağın pusulası bozukmuş ve bozukluk uçuş yönüne göre değişiyormuş. Bunu
  haritaya bakarak ölçtüm; sistem kendi pusulasını GPS olmadan kalibre ediyor.

• Veri kümesinin kendi belgelerinde iki hata varmış (duruş açılarının
  etiketleri ters, yönelim yanlış sütunda).

Sonra aynı soruyu geceye taşıdım: termal kamerayla, ayrı bir veri kümesinde.
Gündüz sistemi gecede bozulmuyor, **duruyor** — LoFTR 100 karenin 100'ünde
sıfır iç nokta veriyor. Ama aynı yasa orada da geçerli çıktı, hatta daha güçlü
biçimde: bir karonun konumlanabilir olup olmadığını **sadece haritaya bakarak**,
eşleşme hiç denenmeden söyleyebiliyorsunuz.

Hepsi 4 GB'lık bir dizüstü ekran kartında çalışıyor.

Çalışmayan üç uçuşu da, ağır titreşimde sistemin kırıldığını da, gecenin hâlâ
çalışan bir sistem olmadığını da depoya yazdım. Bir sistemin nerede
çalışmadığını bilmek, nerede çalıştığını bilmek kadar önemli.

#bilgisayarlıgörü #İHA #seyrüsefer #yapayzeka

---

## İlk yorum

Sonuçları tarayıcıda gezebilirsiniz — uçuş seçin, hatanın rota boyunca nasıl
seyrettiğini ve eşlemenin nerede çöktüğünü görün:
https://huggingface.co/spaces/MANOROMAN/GeoAnchor

Kod, ölçümler ve tam çalışma günlüğü: github.com/YusufGUNEL/GeoAnchor
Makale (IEEE konferans biçimi, 6 sayfa): depoda `paper/geoanchor.pdf`

Veri: UAV-VisLoc (arXiv:2405.11936) — on gerçek tarama uçuşu. Gerçek konum
işlenmiş GNSS; düz uçuş hatlarındaki sapması 1,5 m ölçüldü, yani referansın
kendisi temiz.

---

## Yorum gelirse hazır cevaplar

**"Neden Kalman değil de parçacık süzgeci?"**
Kalman tek bir Gauss kümesi varsayar. Tekrar eden çatı desenleri ve paralel
tarla sınırları gerçekten çok tepeli bir inanış üretiyor; Kalman iki aday
konumu ortalayıp üçüncü bir yanlış konum verirdi.

**"SIFT neden yetmedi?"**
Uydu görüntüsü uçuştan farklı mevsimden. Aynı dört karede SIFT 12/4/24/7 iç
nokta verdi, LoFTR 104/21/280/140. Ama ardışık İHA kareleri arasında görünüm
farkı yok, orada SIFT kullandım — daha hızlı ve CPU'da çalışıp GPU'yu harita
eşlemesine bırakıyor.

**"Duruş bilgisini kullanman hile değil mi? GPS'siz demiştin."**
Eğim, yalpa ve yönelim ataletsel ölçüm biriminden, irtifa barometreden geliyor.
Hiçbiri uyduya bağlı değil. Zaten pusula bulgusu tam olarak o duyargaların
kusursuz olmadığını gösteriyor — sistem onların hatasını haritadan düzeltiyor.

**"Kalibrasyonda gerçek konumu kullanıyorsun, bu hile değil mi?"**
İki yerde: kamera montaj açısı ve ölçek. İkisi de gerçek sistemlerde kurulumda
bir kez yapılan fabrika ayarı. Her uçuşun sadece ilk %20'sinde ölçüp kalan
%80'inde değerlendiriyorum. Ayrıca bir güvenlik kuralı var: düzeltme, sınama
yarısında hatayı azaltmıyorsa hiç uygulanmıyor.

**"Sistemin en zayıf yanı ne?"**
İkisi var. Ağır titreşim bulanıklığı: medyan hata 6,6'dan 58 metreye çıkıyor
(uydu karosunu aynı kadar bulanıklaştırarak 20 metreye indirdim, çözmedim).
Ve özelliksiz arazi: su üstünde eşleme sıfır iç nokta veriyor, orada
odometriyle devam ediyor ve 338 metreye kadar bozuluyor.

**"Bunu gerçek bir İHA'ya koyabilir misin?"**
Şu hâliyle hayır — çevrimdışı işleniyor. Kare başına 866 ms; bu veri kümesinde
kareler 7 saniyede bir geldiği için rahat yetiyor ama gömülü donanımda
denenmedi. Sıradaki adım o olurdu.
