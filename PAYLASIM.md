# Paylaşım taslakları

> Kullanılmadan önce oku ve kendi ağzınla düzelt. Buradaki her sayı ölçüldü,
> abartı yok — o yüzden rahatça savunabilirsin. Mülakatta "bunu nasıl yaptın"
> diye sorulursa `ILERLEME.md` tam günlük.

---

## LinkedIn — ana gönderi

> Görsel olarak `figures/demo.gif` ekle. Bağlantıyı ilk yoruma koy.

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

Yol boyunca üç şey buldum, hiçbiri bana söylenmemişti:

• Kamera 2 derece öne eğik monteliymiş. 466 metre irtifada bu, yerde 16 metre
  kayma demek — hatanın tek en büyük kaynağıydı.

• Uçağın pusulası bozukmuş ve bozukluk uçuş yönüne göre değişiyormuş. Bunu
  haritaya bakarak ölçtüm; sistem kendi pusulasını GPS olmadan kalibre ediyor.

• Veri kümesinin kendi belgelerinde iki hata varmış (duruş açılarının
  etiketleri ters, yönelim yanlış sütunda).

Hepsi 4 GB'lık bir dizüstü ekran kartında çalışıyor.

Sonra aynı soruyu geceye taşıdım: termal kamerayla, ayrı bir veri kümesinde.
Gündüz sistemi gecede bozulmuyor, **duruyor** — LoFTR 100 karenin 100'ünde
sıfır iç nokta veriyor. Ama aynı yasa orada da geçerli çıktı, hatta daha
güçlü biçimde: bir karonun konumlanabilir olup olmadığını, **sadece haritaya
bakarak**, eşleşme hiç denenmeden söyleyebiliyorsunuz. Bu ölçü, eşleşme
yapıldıktan *sonra* hesaplanan iç nokta sayısından daha iyi yorduyor.

Çalışmayan üç uçuşu da, ağır titreşimde sistemin kırıldığını da, gecenin
hâlâ çalışan bir sistem olmadığını da depoda yazdım. Bir sistemin nerede
çalışmadığını bilmek, nerede çalıştığını bilmek kadar önemli.

#bilgisayarlıgörü #İHA #seyrüsefer #yapayzeka

---

## İlk yorum

Depo: github.com/YusufGUNEL/GeoAnchor
Makale (IEEE konferans biçimi, 6 sayfa): depoda `paper/geoanchor.pdf`

Veri: UAV-VisLoc (arXiv:2405.11936) — 9 gerçek tarama uçuşu. Gerçek konum
işlenmiş GNSS; düz uçuş hatlarındaki sapması 1,5 m ölçüldü, yani referansın
kendisi temiz.

---

## Kısa sürüm (X / Bluesky)

GPS'siz İHA konumlandırma, 9 gerçek uçuşta:

görsel odometri → 74 km sonra 2,8 km sürüklenme
uydu eşlemesi → karelerin %25'inde hiç tutmuyor
ikisi + parçacık süzgeci → %99,7 kare, 8-25 m

Asıl bulgu: hangi uçuşta çalışacağını irtifa değil, görüntünün haritayla
örtüşmesi belirliyor. Uçmadan önce ölçülebiliyor.

4 GB VRAM'de çalışıyor.

---

## Mülakatta sorulacak sorular ve hazır cevaplar

**"Neden Kalman değil parçacık süzgeci?"**
Uydu eşlemesinin hatası Gauss değil. Çoğu zaman birkaç metreyle doğru, ama
arada bir tam özgüvenle bambaşka bir yeri gösteriyor — benzer tarla, bir
sokak ötedeki aynı yapı deseni. Dağılım çok tepeli ve ağır kuyruklu. Kalman
tek tepeli Gauss varsayar, böyle bir aykırı ölçüm onu kalıcı olarak yanlış
yere çeker. Parçacık süzgeci birkaç hipotezi canlı tutuyor.

**"Parçacık süzgecinde ne sorun yaşadın?"**
Klasik parçacık tükenmesi. Bulut birkaç metreye toplanınca 100 m uzaktaki
doğru ölçüme hiçbir parçacık yakın olmuyor, olabilirlik her yerde sıfıra
iniyor, ağırlıklar hiç değişmiyor. Süzgeç doğru ölçümü görüyor ama
kıpırdayamıyor — erken bir yanlış eşleşmeye kilitlenip orada kalıyordu.
Çözüm karma öneri dağılımı: her adımda parçacıkların bir kısmı hareket
modeli yerine ölçüm dağılımından çekiliyor. ATE 47 metreden 10 metreye indi.

**"Neden bazı uçuşlarda çalışmıyor?"**
Ölçtüm. Gerçek konum biliniyorken bile o uçuşların görüntüleri uydu
haritasıyla eşleşmiyor — uçuş 08'de doğru konumda medyan 8 iç nokta, uçuş
03'te 544. Yani sistem kötü çalışmıyor, o veride eşleştirilecek bir şey yok.
Eşik %50 eşleşme oranı; üstünde 8-25 m, altında çöküyor. Bunu uçuş öncesi
ölçmek mümkün, o yüzden bu bir kusur değil bir kullanım kuralı.

**"SIFT neden yetmedi?"**
Uydu görüntüsü uçuştan farklı mevsimden. Aynı dört karede SIFT 12/4/24/7 iç
nokta verdi, LoFTR 104/21/280/140. Dedektörsüz yoğun eşleme görünüm farkını
aşıyor. Ama ardışık İHA kareleri arasında görünüm farkı yok, orada SIFT
kullandım — daha hızlı ve CPU'da çalışıp GPU'yu harita eşlemesine bırakıyor.

**"Duruş bilgisini kullanman hile değil mi? GPS'siz demiştin."**
Eğim, yalpa, yönelim ataletsel ölçüm biriminden; irtifa barometre veya
altimetreden geliyor. Hiçbiri uyduya bağlı değil. AnyVisLoc kıyas kümesinin
protokolü de aynı varsayımı kullanıyor. Zaten pusula bulgusu tam olarak o
duyargaların kusursuz olmadığını gösteriyor — sistem onların hatasını
haritadan düzeltiyor.

**"Kalibrasyonda gerçek konumu kullanıyorsun, bu hile değil mi?"**
İki yerde kullanıyorum: kamera montaj açısı ve ölçek. İkisi de gerçek
sistemlerde kurulumda bir kez yapılan fabrika ayarı. Her uçuşun sadece ilk
%20'sinde ölçüp kalan %80'inde değerlendiriyorum. Ayrıca bir güvenlik kuralı
koydum: kalibrasyon kareleri ikiye bölünüyor, düzeltme sınama yarısında
hatayı azaltmıyorsa hiç uygulanmıyor. İki uçuşta gerçekten devreye girdi.

**"Sistemin en zayıf yanı ne?"**
İki tane var. Birincisi ağır titreşim bulanıklığı: medyan hata 6,6'dan
58 metreye çıkıyor. Uydu karosunu da aynı kadar bulanıklaştırarak 20 metreye
indirdim ama çözmedim. İkincisi özelliksiz arazi: su üstünde ve tekdüze
tarlada eşleme sıfır iç nokta veriyor, orada odometriyle devam ediyor ve
338 metreye kadar bozuluyor. İkisi de README'de yazılı, şekilde gösterili.

**"Bunu gerçek bir İHA'ya koyabilir misin?"**
Şu haliyle hayır — çevrimdışı işleniyor. Kare başına 866 ms, bu veri
kümesinde kareler 7 saniyede bir geldiği için rahat yetiyor ama gömülü
donanımda denenmedi. Sıradaki adım o olurdu: eşleyiciyi damıtıp Jetson
sınıfı bir karta indirmek.
