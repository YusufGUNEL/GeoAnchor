# Paylaşım taslakları

> Kullanılmadan önce oku ve kendi ağzınla düzelt. Buradaki her sayı ölçüldü,
> abartı yok — o yüzden rahatça savunabilirsin. Mülakatta "bunu nasıl yaptın"
> diye sorulursa `ILERLEME.md` tam günlük.

---

## LinkedIn — ana gönderi

> GIF veya videoyu (figures/demo.gif) gönderinin görseli olarak ekle.
> Bağlantıyı ilk yoruma koy (LinkedIn dış bağlantılı gönderiyi az gösteriyor).

---

GPS'i karıştırılan bir İHA nerede olduğunu bilmez.

Son birkaç gündür bunun üzerine çalıştım. Elimde tek şey vardı: aşağı bakan
bir kamera ve önceden indirilmiş bir uydu haritası.

İki yöntem var, ikisi de tek başına yetmiyor:

→ Görsel odometri kareler arası hareketi verir, ama sürüklenir.
  74 km'lik gerçek bir uçuşta sonunda 2,8 kilometre şaşıyor.

→ Kamerayı uydu haritasıyla eşlemek mutlak konum verir, ama kare kare
  güvenilmez. Aynı uçuşta karelerin %23'ünde hiç tutmadı — su üstünde,
  tekdüze tarlada, tekrar eden yapı deseninde.

İkisini bir parçacık süzgecinde birleştirince:
768 karenin tamamında konum, medyan hata 6,2 metre.
Üstelik her karede haritanın tamamını aramaktan 2,5 kat daha ucuz — çünkü
kabaca nerede olduğunu bilmek küresel aramayı tek bir yerel kontrole indiriyor.

En beğendiğim kısım bu olmadı ama.

Sistem çalışırken fark ettim ki, İHA karesini uydu karosuna oturtan
dönüşümün dönme bileşeni, uçağın yönelim açısının ne kadar yanlış olduğunu
söylüyor. Ölçtüm: hata uçağın hangi yöne baktığına göre değişiyordu —
bir kolda 1,9 derece, diğerinde 7,1 derece. Bu manyetometrelerdeki
sert-demir hatasının klasik imzası.

Yani uçak, kendi pusulasını haritaya bakarak, hiçbir uydu sinyali olmadan
kalibre edebiliyor. Bunu geri besleyince odometrinin sürüklenmesi
%3,8'den %0,9'a indi.

Bir de veri kümesinin belgesinde iki hata buldum (duruş açılarının
etiketleri ters, yönelim açısı yanlış sütunda) ve kameranın 2 derece öne
monte edildiğini keşfettim — 466 metre irtifada bu yerde 16 metre kayma
demek. Tek en büyük hata kaynağı buydu.

Hepsi 4 GB'lık bir dizüstü ekran kartında çalışıyor.

Kod, ölçümler ve dürüst sınırlar (eşlemenin tamamen çöktüğü %5,7'lik kesim
dahil, üstü örtülmedi) depoda.

#bilgisayarlıgörü #İHA #seyrüsefer #yapayzeka

---

## İlk yorum

Depo: github.com/YusufGUNEL/GeoAnchor

Veri: UAV-VisLoc (arXiv:2405.11936) — gerçek bir tarama uçuşu, 768 kare,
77 dakika, 466 m irtifa. Gerçek konum işlenmiş GNSS.

---

## Kısa sürüm (X / Bluesky)

GPS'siz İHA konumlandırma:

görsel odometri → 74 km sonra 2,8 km sürükleniyor
uydu eşlemesi → karelerin %23'ünde hiç tutmuyor
ikisi + parçacık süzgeci → %100 kare, medyan 6,2 m hata

Bonus: sistem kendi pusula sapmasını haritadan ölçüp düzeltiyor.
Sürüklenme %3,8 → %0,9.

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

**"Sistemin en zayıf yanı ne?"**
Özelliksiz arazi. Dört kesimde (karelerin %5,7'si, en uzunu 21 kare, yaklaşık
2 km) uydu eşlemesi sıfır iç nokta verdi. Orada süzgeç odometriyle devam
ediyor ve yeniden çapa atana kadar en fazla 338 metreye kadar bozuluyor.
Bunu README'de saklamadım, şekilde kırmızı noktalarla gösterdim. Çözümü
muhtemelen daha iyi bir ataletsel ölçüm birimi veya çok mevsimli harita.

**"Bunu gerçek bir İHA'ya koyabilir misin?"**
Şu haliyle hayır — çevrimdışı işleniyor. Kare başına 866 ms, bu veri
kümesinde kareler 7 saniyede bir geldiği için rahatça yetiyor ama gömülü
donanımda denenmedi. Sıradaki adım o olurdu: LoFTR'ı damıtıp Jetson sınıfı
bir karta indirmek.
