# Teknik Rapor

Numan Bekir Özçelik, Eylül 2026

## 1. Problem ve yaklaşım

Kullanıcı bir görsel adresi verir. Uygulama görseldeki objeyi adlandırır,
anahtar kelimeler üretir, web üzerinden objeyle ilgili bilgi derler ve bunları
kaydeder. Akış kullanıcı çıkana kadar sürer ve önceki turlar sonraki aramaları
etkiler.

Problem üç alt parçaya ayrılır. Görüntüden obje adı çıkarmak, objeden anahtar
kelime üretmek ve obje ile kelimelerden anlamlı metin derlemek. İlk ikisi tek
bir görüş modeliyle, üçüncüsü kendi yazdığım bilgi erişim ve doğal dil
üretim kurallarıyla çözülür.

Girdi güvenilmez kabul edilir. Adres yalnız http ve https şemalarıyla kabul
edilir, iç ağ ve yerel makine adreslerine istek atılmaz, yönlendirmeler elle
izlenir ve her durak aynı denetimden geçer. İndirme akışlı yapılır ve yirmi
megabaytta kesilir, sunucunun web sayfası döndürmesi ayrı bir mesajla
bildirilir. Dosya içeriği uzantıya değil gerçek çözümlemeye göre doğrulanır,
telefon fotoğraflarının yön bilgisi düzeltilir, tüm görüntüler RGB'ye
çevrilir, çok kareli formatlarda ilk kare alınır. Çok küçük görüntüler
reddedilir, çok büyükler bellek için küçültülür. Her hata kullanıcıya ne
yapması gerektiğini söyleyen tek cümlelik bir mesajla döner ve döngü sürer.

## 2. Obje tespiti

Kullanılan model açık kaynak CLIP ViT-B/32 modelidir. Model yüz milyonlarca
görüntü ve altyazı çiftiyle, doğru çiftler vektör uzayında yakın ve yanlış
çiftler uzak olacak biçimde eğitilmiştir. Bir görüntünün sınıfı, aday isimlerin
metin vektörleriyle kosinüs benzerliği hesaplanıp softmax uygulanarak bulunur.
Sınıf listesi modelin dışında, veri klasöründeki obje adları dosyasında durur.
Bu liste LVIS veri setinin 1200 kategori adı ve Türkçe karşılıklarından oluşur.
Listeye satır eklemek yeni objeyi tanınır kılar, kod değişmez.

Çıkarım hattını kendim yazdım. Birden çok kalıpla metin kodlama ve
ortalama alma, tam görüntü ile merkez kırpımının öznitelik ortalaması, kosinüs
ve softmax hesabı, tema skorlarından kelime seçimi bu hatta yer alır.
Kütüphaneden yalnızca model ağırlıkları ve görüntü ön işleme alınır.

Model seçimi ölçüme dayanır. Geliştirme sırasında üç aday kıyaslandı. Kapalı
kümeli YOLO11n modeli seksen sınıfla sınırlıdır, kapsam dışı objede sessiz
kalır ya da en yakın sınıfa zorlar. Ölçümde keman görselini makas olarak
sınıfladı. Açık dağarcıklı YOLO-World modeli isim listesi büyüdükçe skor
seyrelmesi yaşar, aynı objeyi yirmi isimli listede bulurken bin isimli
listede bulamadı. Ayrıca burada konum bilgisi gerekmez, görselde ön plana
çıkan tek obje olduğu varsayılır. CLIP binlerce isim arasında ayrım yapabilir,
aynı öznitelik vektörü hem obje adını hem temaları verir ve işlemci üzerinde
görüntü başına elli milisaniyede çalışır.

Obje ve tema sınıflandırmaları aynı görüntüye iki ayrı bakıştır. Beyaz fonlu
ürün fotoğraflarında obje listesi ince ayrımlarda yanılırken tema listesi
kaba kavramda doğru kalabilir. Bu yüzden bir uzlaşma kuralı vardır. Obje
güveni 0.5 altındaysa ve en güçlü temalardan birinin adı obje listesinde de
bulunuyorsa ve bu ad obje adayları arasındaysa, o aday obje olarak seçilir.
Güven yüksekken kural çalışmaz.

Ölçüm on dört görsellik bir test setiyle yapıldı. Sette gündelik
yedi obje ile keman, fotoğraf makinesi, demlik, karışık bir
sahne ve alakasız bir görsel vardır. Ön planda tek obje olan on iki görselin
on biri doğru bulundu. Karışık sahne ve alakasız görsel düşük güven eşiğinin
altında kalarak emin olamadım mesajı aldı.

## 3. Kendi eğittiğim sınıflandırıcı

Sıfır atış sınıflandırmanın yanına kendi eğittiğim küçük bir model eklendi.
Model, CLIP görüntü kodlayıcısının ürettiği 512 boyutlu birim vektörü girdi
alan tek katmanlı doğrusal bir sınıflandırıcıdır. Görüntü kodlayıcı donmuş
tutulur, yalnız bu katman eğitilir. İşlemci üzerinde dakikalar içinde
eğitilebilen ve sıfır atıştan iyi sonuç veren tek makul seçenek budur,
sıfırdan bir evrişimli ağ günlerce sürer ve daha kötü kalır.

Veri seti Caltech-101'dir. Yüz bir nesne sınıfı ve yaklaşık dokuz bin görsel
içerir, torchvision üzerinden indirilir. Yüz ve arka plan sınıfları çıkarıldı,
sınıflar dengesiz olduğu için her sınıftan en fazla altmış görsel alındı.
Toplam 5173 görsel ve 99 sınıf kaldı. Her sınıftan yüzde yirmi doğrulama
kümesine ayrıldı.

Eğitim kodu training klasöründedir. Öznitelik çıkarma scripti görselleri
kodlayıp tek dosyaya yazar, eğitim scripti sınıflandırıcıyı eğitir. Eğitim
döngüsünü kendim yazdım. Çapraz entropi kaybı, Adam eniyileyici,
yığın boyutu 128, en fazla üç yüz epoch ve doğrulama kaybı on epoch
iyileşmezse erken durdurma.

Öğrenme oranı ve ağırlık çürümesi tarama ile seçildi. Tarama scripti dört
öğrenme oranı ve üç çürüme değerini aynı eğitim ve doğrulama kümesinde
denedi. Sonuçlar doğrulama doğruluğudur.

| Öğrenme oranı | Çürüme 0 | Çürüme 0.0001 | Çürüme 0.001 |
|---|---|---|---|
| 0.001 | 0.955 | 0.935 | 0.806 |
| 0.005 | 0.954 | 0.936 | 0.803 |
| 0.01 | 0.953 | 0.935 | 0.806 |
| 0.02 | 0.953 | 0.934 | 0.792 |

Belirleyici olan ağırlık çürümesidir, öğrenme oranı yalnız yakınsama hızını
değiştirir. Çürüme arttıkça doğruluk düşer, çünkü giriş vektörleri birim
uzunluktadır ve sınıfları ayırmak için ağırlıkların büyümesi gerekir.

Doğruluk tek ölçüt değildir. Uygulama sınıflandırıcının görüşünü güvenine
göre kullanır, bu yüzden güvenlerin anlamlı olması gerekir. Aynı doğrulama
kümesinde yanlış tahminlerin güveni de ölçüldü.

| Çürüme | Doğruluk | Yanlış tahminde ortalama güven | Yanlış ve güven 0.8 üstü |
|---|---|---|---|
| 0 | 0.953 | 0.64 | yüzde 21 |
| 0.0001 | 0.935 | 0.27 | yüzde 0 |
| 0.001 | 0.806 | 0.05 | yüzde 0 |

Çürümesiz model eğitim örneklerini ezberler ve yanlış tahminlerinde bile
yüksek güven verir, yanlışların beşte biri 0.8 üstü güvenle gelir. Böyle bir
görüş uygulamada sıfır atışın doğru cevabını yanlışla değiştirebilir,
ölçümde demlik görselini sürahi yaptı. Çürüme 0.0001 iki puan doğruluk
kaybeder ama yanlış tahminlerde güven düşük kalır ve hiçbiri eşiği geçmez.
Seçilen değerler öğrenme oranı 0.01 ve çürüme 0.0001. Erken durdurma bu
ayarda yetmiş epoch civarında devreye girer. Eğitim doğruluğu yüzde 97,
doğrulama yüzde 93.5, sıfır atış aynı kümede yüzde 86. Yedi puanlık fark,
alan verisiyle eğitimin genel modele katkısını gösterir.

Uygulamada sınıflandırıcı ikinci görüştür. Sınıfları obje listesindeki
adlara bir eşleme dosyasıyla bağlanır, 99 sınıfın 57'sinin karşılığı vardır.
Sıfır atış emin değilse sınıflandırıcının cevabına bakılır. Cevap sıfır
atışın adayları arasındaysa iki görüş uyuşuyor demektir ve 0.5 güven yeter,
aday değilse tek başına 0.8 güven gerekir. Ölçümde bu iki eşik, telefon
görselinde doğru cevabı seçerken demlik görselinde yanlış sürahi cevabını
geçirmedi. Sıfır atış eminse dokunulmaz, böylece 1200 isimlik kapsam
korunur. İki görüş aynı cevabı veriyorsa bu bir onaydır, güven
sınıflandırıcının güvenine yükselir ve tema uzlaşma kuralı çalışmaz. Hangi
görüşün seçildiği kayda ve ayrıntılara yazılır.

Sınırlılık. Caltech sınıfları test setindeki objelerin bir kısmını
kapsar, gerisinde sınıflandırıcının görüşü olmaz. Model dosyası küçüktür ve
depoyla birlikte gelir, veri seti gelmez, eğitim scripti yeniden indirir.

## 4. Anahtar kelimeler

Görüntüden öznitelik çıkarıp önceden belirlenmiş özniteliklerle
karşılaştırma yaklaşımı uygulanır. Tema haritası dosyasında
484 tema kavramı bulunur. Her kavramın İngilizce bir adı ve Türkçe anahtar
kelimeleri vardır. Görüntü vektörü bu temalarla karşılaştırılır. En iyi
temanın yüzde on beşinin ve mutlak eşiğin üstündeki temalardan kelime alınır.
Her temadan önce bir kelime alınır ki liste tek temaya kilitlenmesin. Objenin
kendi adı kelime olarak tekrar edilmez. Eşik üçten az kelime bırakırsa
sıradaki temalardan üçe tamamlanır.

Tema listesi sezgiyle yazılmadı. Obje listesindeki 1200 ismin her birinin
WordNet üst kavram zincirlerini çıkardım ve her kavramın kaç objenin atası
olduğunu saydım. Az sayıda kavram objelerin büyük kısmını topluyor, yiyecek
iki yüz, kap yüz yetmiş iki, giysi doksan yedi objenin atasıdır. Kavramlar bu
sıralı listeden iki şartla seçildi. Çok objeyi kapsamalı ve arama sorgusuna
değer katmalı. Listenin tepesindeki cihaz, örtü ve katı madde gibi en geniş
kavramlar ikinci şartı sağlamadığı için bilinçli olarak dışarıda kaldı, şişe
açacağı için cihaz kelimesi aramaya bir şey katmaz. Olay ve eylem gibi soyut
kavramlar fotoğraf dağarcığına yabancı olduğu için elendi. Zinciri yalnız bu
dışlanan kavramlardan geçen objelere kendi adlarıyla tema girdisi yazıldı.
Türkçe değerler ders kitabı kategorisi değil arama dilidir, yangın güvenliği
ve toplu taşıma gibi tek başına aranabilir ifadeler seçildi. Bugünkü
haritada 153 kavram girdisi ve 331 obje adıyla eşleşen girdi vardır.

Kelimeler görüntüye özgüdür. Aynı obje farklı görsellerde farklı kelimeler
alabilir, bu da sohbet bağlamının ayırt edici olmasını sağlar.

## 5. Arama niyeti

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
yalnız tanım bloğu gösterilir. Taşıtlarda kullanım kelimesi niyete girmez,
çünkü seyahat uçakları gibi tamlamalar doğal değildir.

Kullanıcı düz metin yazdığında sorgu obje adı ile metnin birleşimidir.
Görselle birlikte metin yazıldığında da niyet o metinden kurulur, bloklar
yalnız tanım ve cevap olur, çünkü kullanıcı ne istediğini söylemiştir.

## 6. Web araması ve paragraf seçimi

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
sitelerinin bilgi taşımayan kalıp cümleleri paragraftan kırpılır. Yazının
kendisinden söz eden ya da okura söz veren paragraflar, bu yazıda diye
başlayan ya da sayfa başlığındaki soruya atıf yapan blog giriş ve kapanışları
gibi, tümüyle elenir. Adaylar obje adı ve anahtar kelimelerden kurulan sorguya
tf-idf kosinüs benzerliğiyle sıralanır. Terim sıklığı, kökün paragraftaki
sayısının paragraftaki toplam kök sayısına oranıdır. Ters belge sıklığı, aday
sayısı artı birin kökü içeren paragraf sayısı artı bire oranının doğal
logaritması artı birdir. Bu hesap hazır kütüphane kullanılmadan yazılmıştır.
Türkçe ekleri hoş görmek için kelimelerin ilk beş harfi kök olarak kullanılır.
Kaynak başına bir paragraf alınır, Jaccard benzerliği yüksek tekrarlar elenir.

## 7. Bilgi blokları

Çıktı düz bir paragraf listesi değil, objenin ailesine göre başlıklı
bloklardır. Her tur tanım bloğuyla başlar. Arama niyeti obje adından farklıysa
ilgili bloğu gelir. Ardından aileye özgü bloklar gelir. Yemekte tarif ve
tarihçe, enstrümanda tarihçe ve nasıl çalınır, canlıda özellikleri ve yaşam
alanı, taşıtta tarihçe ve türleri, diğer ürünlerde çeşitleri ve kullanım
alanları. Aile, anahtar kelimelerin aile ve alan rolündeki kelimelerinden
bulunur. Havacılık ya da denizcilik gibi alan kelimeleri taşıt ailesini
işaret eder. Şema veri klasöründeki blok dosyasında durur.

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

## 8. Sohbet bağlamı ve hafıza

Oturum son üç turun objesini, anahtar kelimelerini ve ailesini tutar. Yeni
tur geldiğinde bu turlara en yeniden eskiye bakılır ve şu üç koşuldan birini
sağlayan ilk tur aynı konu sayılır. Ortak anahtar kelime, obje adlarında
ortak kelime ya da aynı aile. Varsayılan ürün ailesinde aile tek başına
yetmez, ortak kelime de gerekir, aksi halde çanta ile telefon aynı konu
sayılırdı. Hiçbir tur uymazsa konu değişmiş sayılır ve eski turlar aramaya
karışmaz.

Bağ kurulunca iki etki olur. Önceki objenin adı arama niyetine yalnız iki ad
son kelimeyi paylaşıyorsa girer ve adlar tek tamlamada birleşir, el çantası
ile sırt çantası gibi. Adlar ilişkisizse niyet değişmez, çünkü ilişkisiz iki
adı tek sorguda birleştirmek anlamlı sonuç vermez. Ortak anahtar kelime
varsa paragraf sıralamasında öncelik verir.

Bağ ekranda üç yerde görünür. Niyet cümlesine önceki turdan giren kelimeler
işaretlenir. Kartın başında önceki turla kurulan bağ ve aile, sorguya bir
şey girdiyse o da yazılır. Giriş alanının altındaki sohbet satırı tur
sayısını ve aynı ailede kalan ardışık objeleri sıralar, bağ yoksa yeni konu
der. Tur sayacı hafıza penceresinden bağımsızdır.

Düz metin girdisi son objeye bağlanır, sorgu obje adı ile metnin
birleşimidir. Böylece kullanıcı görsel vermeden aynı obje hakkında soru
sorabilir.

Oturum ayrıca gösterilen kaynak adreslerini ve her objenin kaç kez
konuşulduğunu tutar. Aynı obje yeniden geldiğinde bu kullanıcıya söylenir,
tanım tekrarlanmaz, daha önce gösterilen sayfalar indirilmez ve bloklar yeni
kaynaklarla dolar. Hiç yeni kaynak kalmazsa önceki kaynaklara dönülür ve bu
da söylenir. Ölçümde aynı sosisli görseli üst üste üç turda üç ayrı kaynak
kümesi getirdi, üçüncü turda tarihçe içerikleri geldi.

## 9. Arayüz

Terminal arayüzü her turu tek bir kart olarak gösterir. Kart girdiden hemen
sonra açılır ve kademeli dolar. Obje adı, güven, anahtar kelimeler ve arama
niyeti yarım saniye içinde görünür, Vikipedi tanımı bir iki saniye sonra
eklenir, kalan bloklar arama bitince gelir. Bu sırada kartın altında tek
satırlık ilerleme durur ve adımı söyler. Kart gövdesi markdown olarak
üretilir ve aynı metin düz modda basılır ve kayıt dosyasına yazılır. Debug
açıkken kartın altında katlanır bir ayrıntılar bölümü bulunur, adaylar,
sorgular ve blok kararları orada listelenir. Kaynaklar ile süre ve kayıt
numarası kartın alt satırındadır. Niyet cümlesine önceki turdan giren
kelimeler işaretlenir, kartın başında önceki turla kurulan bağ ve aile
yazılır, giriş alanının altındaki sohbet satırı tur sayısını ve aynı ailede
kalan ardışık objeleri özetler.

## 10. Kayıt

Her tur kayıt dosyasında oturum bloğu altına yazılır. Girdi, obje ve güven,
sınıflandırıcının görüşü, uzlaşma kararı, anahtar kelimeler, bağlam, arama
niyeti, arama izi, başlıklı bilgi blokları ve her paragrafın kaynağı ile
turun durumu kaydedilir. Dosya önce geçici
dosyaya yazılıp atomik taşınır.

## 11. Kütüphane tercihleri

Arama için ddgs kullanılır. Resmi arama servisleri anahtar ve hesap
gerektirir, bu da tek komutla çalıştırma şartıyla çelişir. Anahtarsız
çalışan diğer kütüphaneler bot engeline takılıp öngörülemez biçimde kırılır.
Servisin geçici hataları bir kez yeniden deneme ve Vikipedi yedeğiyle
karşılanır.

Sayfa gövdesini çıkarmak için trafilatura kullanılır. Gezinme ve reklam
temizliğinde en isabetli sonucu veren ve aktif bakımda olan kütüphane budur.
Çıkarımdan sonraki paragraf seçimi, benzerlik hesabı ve yapı çıkarımı kendi
kodumdur.

Cevap üretiminde dil modeli kullanılmaz. Cevapların web sayfası
içeriğinden gelmesi hedeflenir. Servis tabanlı bir model anahtar bağımlılığıyla
tek komutla çalışmayı bozar, yerel bir model projeyi şişirir ve
işin ağırlığını bilgi erişim hattından modelin yazı becerisine kaydırır.

Kayıt için veritabanı yerine düz json dosyası seçildi. Kurulum gerektirmez,
tek komutla çalışır, insan gözüyle okunur ve bağlam sürdürmenin veri kaynağı
olarak aynı şemayı kullanır.

## 12. Sınırlılıklar

Karışık sahnelerde sınıflandırma belirsiz kalır, bu durumda düşük güven
mesajı verilir. Tema haritası kapalı bir listedir, kapsam dışı bir alanda
kelimeler genel kalabilir. Arama servisi yoğun kullanımda istek sınırlar, bu
durumda kalan sorgular ve Vikipedi ile devam edilir. Yapılandırılmış çıkarım
sayfa yapısına bağlıdır, standart dışı sayfalarda düz paragrafa düşülür.
Beyaz fonlu ürün fotoğraflarında obje listesi ince ayrımlarda yanılabilir,
uzlaşma kuralı ve sınıflandırıcı bunu yalnız aday listesinde doğru cevap
varsa düzeltir. Sınıflandırıcı 57 objeyi bilir, gerisinde görüşü yoktur.
Metin üretimi yoktur, paragraflar kaynaktan olduğu gibi alınır, bu yüzden
bloklar arasında akıcı geçiş bulunmaz.
