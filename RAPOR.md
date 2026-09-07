# Teknik Rapor

Numan Bekir Özçelik, Eylül 2026

## 1. Problem ve yaklaşım

Kullanıcı bir görsel adresi verir. Uygulama görseldeki objeyi adlandırır,
anahtar kelimeler üretir, web üzerinden objeyle ilgili bilgi derler ve bunları
kaydeder. Akış kullanıcı çıkana kadar sürer ve önceki turlar sonraki aramaları
etkiler.

Görev üç alt probleme ayrılır. Görüntüden obje adı çıkarmak, objeden anahtar
kelime üretmek ve obje ile kelimelerden anlamlı metin derlemek. İlk ikisi tek
bir görüş modeliyle, üçüncüsü kendi yazdığımız bilgi erişim ve doğal dil
üretim kurallarıyla çözülür.

## 2. Obje tespiti

Kullanılan model açık kaynak CLIP ViT-B/32 modelidir. Model yüz milyonlarca
görüntü ve altyazı çiftiyle, doğru çiftler vektör uzayında yakın ve yanlış
çiftler uzak olacak biçimde eğitilmiştir. Bir görüntünün sınıfı, aday isimlerin
metin vektörleriyle kosinüs benzerliği hesaplanıp softmax uygulanarak bulunur.
Sınıf listesi modelin dışında, veri klasöründeki obje adları dosyasında durur.
Bu liste LVIS veri setinin 1200 kategori adı ve Türkçe karşılıklarından oluşur.
Listeye satır eklemek yeni objeyi tanınır kılar, kod değişmez.

Çıkarım hattı tarafımızdan yazılmıştır. Birden çok kalıpla metin kodlama ve
ortalama alma, tam görüntü ile merkez kırpımının öznitelik ortalaması, kosinüs
ve softmax hesabı, tema skorlarından kelime seçimi bu hatta yer alır.
Kütüphaneden yalnızca model ağırlıkları ve görüntü ön işleme alınır.

Model seçimi ölçüme dayanır. Geliştirme sırasında üç aday kıyaslandı. Kapalı
kümeli YOLO11n modeli seksen sınıfla sınırlıdır, kapsam dışı objede sessiz
kalır ya da en yakın sınıfa zorlar. Ölçümde keman görselini makas olarak
sınıfladı. Açık dağarcıklı YOLO-World modeli isim listesi büyüdükçe skor
seyrelmesi yaşar, aynı objeyi yirmi isimli listede bulurken bin isimli
listede bulamadı. Ayrıca bu görev konum bilgisi istemez, görselde ön plana
çıkan tek obje olduğu varsayılır. CLIP binlerce isim arasında ayrım yapabilir,
aynı öznitelik vektörü hem obje adını hem temaları verir ve işlemci üzerinde
görüntü başına elli milisaniyede çalışır.

Obje ve tema sınıflandırmaları aynı görüntüye iki ayrı bakıştır. Beyaz fonlu
ürün fotoğraflarında obje listesi ince ayrımlarda yanılırken tema listesi
kaba kavramda doğru kalabilir. Bu yüzden bir uzlaşma kuralı vardır. Obje
güveni 0.5 altındaysa ve en güçlü temalardan birinin adı obje listesinde de
bulunuyorsa ve bu ad obje adayları arasındaysa, o aday obje olarak seçilir.
Güven yüksekken kural çalışmaz.

Ölçüm on iki görsellik bir test setiyle yapıldı. Sette görev senaryolarındaki
yedi obje ile keman, fotoğraf makinesi, demlik, karışık bir sahne ve alakasız
bir görsel vardır. Ön planda tek obje olan on görselin dokuzu doğru bulundu,
ortalama güven 0.62 oldu. Karışık sahne ve alakasız görsel düşük güven
eşiğinin altında kalarak emin olamadım mesajı aldı. Alışılmadık bir sosisli
görseli pide olarak sınıflandı, klasik sosisli görsellerinde güven 0.90 oldu.

## 3. Anahtar kelimeler

Görev tanımındaki görüntüden öznitelik çıkarıp önceden belirlenmiş
özniteliklerle karşılaştırma yaklaşımı uygulanır. Tema haritası dosyasında
480 tema kavramı bulunur. Her kavramın İngilizce bir adı ve Türkçe anahtar
kelimeleri vardır. Görüntü vektörü bu temalarla karşılaştırılır. En iyi
temanın yüzde on beşinin ve mutlak eşiğin üstündeki temalardan kelime alınır.
Her temadan önce bir kelime alınır ki liste tek temaya kilitlenmesin. Objenin
kendi adı kelime olarak tekrar edilmez. Eşik üçten az kelime bırakırsa
sıradaki temalardan üçe tamamlanır.

Kelimeler görüntüye özgüdür. Aynı obje farklı görsellerde farklı kelimeler
alabilir, bu da sohbet bağlamının ayırt edici olmasını sağlar.

## 4. Arama niyeti

Obje adı, anahtar kelimeler ve bağlamdan kural tabanlı doğal dil üretimiyle
Türkçe bir arama cümlesi kurulur. Her anahtar kelimenin kelime rolleri
dosyasında bir rolü vardır. Nitelik ve malzeme kelimeleri başa sıfat olarak
girer. Bileşen kelimeleri ünlü uyumuna göre lı, li, lu ya da lü ekini alır.
Kullanım kelimeleri ve bağlacıyla listelenir. Aile ve alan kelimeleri sorguya
girmez çünkü obje adı o bilgiyi zaten taşır. Kadın ve erkek gibi karşıt
nitelikler birlikte gelirse ikisi de sorguya girmez.

Obje adı çoğullanır, tamlamalarda çoğul eki kökle iyelik eki arasına girer.
Tek kelimeli objede kullanım kelimesi tamlama kurar. Bağlamdaki önceki obje
son kelimeyi paylaşıyorsa iki ad tek tamlamada birleşir. Yemek ailesinde
cümle tarifleri kelimesiyle biter. Ünlü uyumu, ünsüz yumuşaması, iyelik ve
çoğul ekleri küçük bir Türkçe morfoloji üreteciyle hesaplanır. Bu cümle hem
ekranda gösterilir hem de arama sorgusudur. Obje güveni eşiğin altındaysa
anahtar kelimeler de güvenilmez sayılır, sorgu yalnız obje adı olur ve
yalnız tanım bloğu gösterilir.
Kullanıcı düz metin yazdığında sorgu obje adı ile metnin birleşimidir.
Görselle birlikte metin yazıldığında da niyet o metinden kurulur, bloklar
yalnız tanım ve cevap olur, çünkü kullanıcı ne istediğini söylemiştir.

## 5. Web araması ve paragraf seçimi

Vikipedi için önce tam başlıkla sayfa istenir, bulunamazsa arama yapılır.
Anlam ayrımı sayfaları ve objeden söz etmeyen sayfalar atlanır. Giriş tek
cümleyse yeterli uzunluğa ulaşana kadar sonraki paragraflar eklenir. Sayfanın
kendi bölümleri de tek istekle okunur ve bilgi bloklarını besler.

Arama motoru sonuçlarında sosyal medya, pazaryeri, sözlük ve çeviri siteleri
elenir, alan başına bir sayfa alınır. Sonuçlar başlığa göre önceliklendirilir.
Bilgi vadeden kelimeler içeren başlıklar öne, satış dili taşıyan başlıklar
arkaya alınır. Servis geçici hata verirse sorgu kısa bir bekleme sonrası bir
kez daha denenir.

Sayfaların ana metni çıkarılır ve paragraflara bölünür. Paragraf yüz elli ile
dokuz yüz karakter arasında olmalı, nokta ile bitmeli, Türkçe bağlaç içermeli,
objeden söz etmeli ve site kalıntısı taşımamalıdır. Tarif ve soru cevap
sitelerinin bilgi taşımayan kalıp cümleleri paragraftan kırpılır. Adaylar obje
adı ve anahtar kelimelerden kurulan sorguya tf-idf kosinüs benzerliğiyle
sıralanır. Terim sıklığı, kökün paragraftaki sayısının paragraftaki toplam kök
sayısına oranıdır. Ters belge sıklığı, aday sayısı artı birin kökü içeren
paragraf sayısı artı bire oranının doğal logaritması artı birdir. Bu hesap
hazır kütüphane kullanılmadan yazılmıştır. Türkçe ekleri hoş görmek için
kelimelerin ilk beş harfi kök olarak kullanılır. Kaynak başına bir paragraf
alınır, Jaccard benzerliği yüksek tekrarlar elenir.

## 6. Bilgi blokları

Çıktı düz bir paragraf listesi değil, objenin ailesine göre başlıklı
bloklardır. Her tur tanım bloğuyla başlar. Arama niyeti obje adından farklıysa
ilgili bloğu gelir. Ardından aileye özgü bloklar gelir. Yemekte tarif ve
tarihçe, enstrümanda tarihçe ve nasıl çalınır, canlıda özellikleri ve yaşam
alanı, taşıtta tarihçe ve türleri, diğer ürünlerde çeşitleri ve kullanım
alanları. Aile, anahtar kelimelerin aile rolündeki kelimelerinden bulunur.
Şema veri klasöründeki blok dosyasında durur.

Her blok kendi sorgusunu atar, sorgular ikişer paralel gönderilir ve tüm
sonuçlar tek havuzda indirilir. Her sayfa hangi blok sorgusundan geldiğini
taşır. Blok önce kendi sorgusunun sayfalarına bakar, havuz yedektir. Blok
paragrafı en az iki farklı açı kökü içermeli ve açı sorgusuna belirli bir
eşiğin üstünde benzemelidir. Eşiği geçen paragraf yoksa blok gösterilmez.
Böylece her turda sabit sayıda blok değil, kaynağın gerçekten desteklediği
bloklar görünür. Eşikler on iki turluk ölçümde blok skorlarının dağılımına
bakılarak seçildi.

Tarif ya da çeşit listesi düz paragraf değil yapıdır. Sayfanın html yapısı
lxml ile okunur, dil modeli kullanılmaz. Madde listeleri, yapılış başlığından
sonra gelen adımlar ve alt başlıklarla altındaki ilk cümle çıkarılır. Gezinme,
altbilgi ve yorum alanları atılır. Alt başlıklar yalnız objeyi anıyorsa ve
satış dili taşımıyorsa çeşit sayılır. Blok şemasındaki biçim alanı hangi
yapının aranacağını söyler. Yapı yalnız bloğun kendi sorgusunun sayfalarından
ve başlığı objeyi anan sayfalardan alınır. Yapılı bloklarda doldurma sırası
sayfa yapısı, Vikipedi bölümü ve düz paragraftır. Paragraf bloklarında önce
Vikipedi bölümü denenir.

Bloklar başlıklı, paragraflar numaralı dipnotlu, sonda kaynak listesiyle tek
metin olarak sunulur. Ölçümde sosisli için tarif bloğu on maddelik malzeme
listesi ve altı adımlık yapılış verdi. Fotoğraf makinesi için çeşitleri bloğu
beş makine türünü kısa açıklamalarıyla listeledi.

## 7. Sohbet bağlamı ve hafıza

Son üç turun objesi, kelimeleri ve ailesi tutulur. Yeni tur önceki bir turla
anahtar kelime paylaşıyorsa, obje adları ortak kelime içeriyorsa ya da ikisi
aynı aileye giriyorsa iki tur aynı konudadır. Varsayılan ürün ailesinde aile
tek başına yetmez, ortak kelime de gerekir, aksi halde çanta ile telefon
aynı konu sayılırdı. Bağ kurulunca önceki objenin adı arama niyetine
katılabilir ve ortak kelime paragraf sıralamasında öncelik verir. Ekranda
kartın başında önceki turla kurulan bağ, giriş alanının altında ise sohbet
satırı görünür ve aynı ailede kalan ardışık objeleri sıralar. Bağ yoksa
konu değişmiş sayılır ve eski tur aramaya karışmaz.

Oturum gösterilen kaynak adreslerini hatırlar. Aynı obje ikinci kez geldiğinde
tanım tekrarlanmaz, daha önce gösterilen sayfalar seçilmez ve bloklar yeni
kaynaklarla dolar. Hiç yeni kaynak kalmazsa önceki kaynaklara dönülür ve bu
kullanıcıya söylenir.

## 8. Arayüz

Terminal arayüzü her turu tek bir kart olarak gösterir. Kart girdiden hemen
sonra açılır ve kademeli dolar. Obje adı, güven, anahtar kelimeler ve arama
niyeti yarım saniye içinde görünür, Vikipedi tanımı bir iki saniye sonra
eklenir, kalan bloklar arama bitince gelir. Bu sırada kartın altında tek
satırlık ilerleme durur ve adımı söyler. Kart gövdesi markdown olarak
üretilir ve aynı metin düz modda basılır ve kayıt dosyasına yazılır. Debug
açıkken kartın altında katlanır bir ayrıntılar bölümü bulunur, adaylar,
sorgular ve blok kararları orada listelenir. Kaynaklar ile süre ve kayıt
numarası kartın alt satırındadır. Bağlam ekranda görünür. Niyet cümlesine
önceki turdan giren kelimeler işaretlenir, kartın başında önceki turla
kurulan bağ ve ortak kelime yazılır, giriş alanının altındaki sohbet
satırı tur sayısını, konuyu ve bağı özetler.

## 9. Kayıt

Her tur kayıt dosyasında oturum bloğu altına yazılır. Girdi, obje ve güven,
anahtar kelimeler, bağlam, arama niyeti, arama izi, başlıklı bilgi blokları
ve her paragrafın kaynağı ile turun durumu kaydedilir. Dosya önce geçici
dosyaya yazılıp atomik taşınır.

## 10. Sınırlılıklar

Karışık sahnelerde sınıflandırma belirsiz kalır, bu durumda düşük güven
mesajı verilir. Tema dağarcığı elle derlenmiştir, kapsam dışı bir alanda
kelimeler genel kalabilir. Arama servisi yoğun kullanımda istek sınırlar, bu
durumda kalan sorgular ve Vikipedi ile devam edilir. Yapılandırılmış çıkarım
sayfa yapısına bağlıdır, standart dışı sayfalarda düz paragrafa düşülür.
