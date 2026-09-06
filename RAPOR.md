# Teknik Rapor: Görüntülü Sohbet Uygulaması

Numan Bekir Özçelik · Eylül 2026

## 1. Problem ve yaklaşım

Kullanıcı bir görsel adresi verir; uygulama görseldeki objeyi adlandırır,
anahtar kelimeler üretir, web'den objeyle ilgili metin derler ve tüm bunları
kaydeder. Akış kullanıcı çıkana kadar sürer ve önceki turlar sonraki
aramaları etkiler.

Görev üç alt probleme ayrılır: (1) görüntüden obje adı, (2) objeden anahtar
kelime, (3) obje ve kelimelerden anlamlı metin. İlk ikisi tek bir modelle,
üçüncüsü klasik bilgi erişim yöntemleriyle çözülür.

## 2. Obje tespiti: CLIP ile sıfır atış sınıflandırma

**Model:** OpenAI CLIP ViT-B/32 (açık kaynak, 400 milyon görüntü-metin çiftiyle
eğitilmiş). Görüntü ve metin aynı 512 boyutlu uzaya kodlanır; bir görüntünün
sınıfı, aday isimlerin metin vektörleriyle kosinüs benzerliği üzerinden
softmax ile bulunur. Sınıf listesi modelin dışında, `data/object_names_tr.json`
dosyasında durur (LVIS veri setinin 1200 kategori adı ve Türkçe karşılıkları).

**Çıkarım kodu** (`app/vision.py`) tarafımızdan yazılmıştır: kalıp topluluğu
("a photo of a {}", "a close-up photo of a {}") ile metin kodlama, tam görüntü
ve merkez kırpımının öznitelik ortalaması, kosinüs ve softmax hesabı, tema
skorlarından kelime seçimi. Kütüphaneden yalnızca model ağırlıkları ve ön
işleme alınır.

**Neden CLIP, alternatifleri neden değil:**

| Aday | Kapsam | Sorun |
|---|---|---|
| YOLO11n (COCO) | 80 sınıf | Kapsam dışı objede sessiz kalır ya da en yakın sınıfa zorlar; keman görselini "makas" saydı. |
| YOLO-World (açık dağarcık) | Sınırsız isim | Büyük listede skor seyrelmesi: aynı objeyi 20 isimle 0.62, 1200 isimle görünmez buluyor. Konum bilgisi bu görevde gerekmiyor. |
| CLIP ViT-B/32 | Sınırsız isim | Binlerce isim arasında ayrım yapabilir; aynı vektör hem obje adını hem temaları verir; CPU'da 50 ms. |

Görev "görüntüde ön plana çıkan bir obje" varsayımıyla tanımlandığından
lokalizasyon gereksizdir; sınıflandırma yeterlidir. Merkez kırpımı ön plandaki
objenin ağırlığını artırır.

**Ölçüm:** 12 görsellik test seti (görev senaryolarındaki 7 obje + keman,
fotoğraf makinesi, demlik, karışık sahne, kaya). Ön planda tek obje olan 10
görselin 9'u doğru (%90), ortalama güven 0.62. Karışık sahne ve alakasız
görsel düşük güven eşiğinin (0.25) altında kalarak "emin değilim" mesajı
aldı. Bir chili dog görseli "pide" olarak sınıflandı; klasik sosisli
görsellerinde güven 0.90.

## 3. Anahtar kelimeler: tema dağarcığıyla karşılaştırma

Görev tanımındaki "görüntüden öznitelik çıkarıp önceden belirlenmiş
özniteliklerle karşılaştırma" yaklaşımı uygulanır. `data/theme_map.json`
dosyasında 480 tema kavramı (İngilizce anahtar → Türkçe kelimeler) bulunur:
`fast_food → fast food`, `italian_cuisine → İtalyan mutfağı`,
`baggage → valiz, seyahat`. Görüntü vektörü bu temalarla karşılaştırılır,
en iyi temanın %15'inin ve mutlak 0.05 eşiğinin üstündeki temalardan kelime
alınır. Her temadan önce bir kelime alınır ki liste tek temaya kilitlenmesin;
objenin kendi adı kelime olarak tekrar edilmez.

Kelimeler görüntüye özgüdür: ketçaplı sosisli görseli "ketçap, fast food,
sos, sosis" verirken pizza "hamurlu yemek, İtalyan mutfağı", sırt çantası
"valiz, aksesuar, seyahat" verir. Aynı obje farklı görsellerde farklı
kelimeler alabilir; bu, sohbet bağlamının ayrıştırıcı olmasını sağlar.

## 4. Web araması ve metin derleme

- **Sorgu:** Türkçe obje adı, varsa bağlam kelimesi, varsa kullanıcının yazdığı
  metin. Fazladan kelime aramayı kendi alanına çektiği için sorgu kısa tutulur.
- **Vikipedi:** MediaWiki API ile giriş paragrafı alınır; her turda güvenilir
  bir tanım garantilenir, anlam ayrımı sayfaları atlanır.
- **DuckDuckGo:** `ddgs` ile 10 sonuç, sosyal medya ve pazaryeri alanları elenir,
  alan başına bir sayfa, 5 sayfa paralel indirilir.
- **Paragraf seçimi** (`app/extractor.py`): `trafilatura` ana metni çıkarır,
  metin paragraflara bölünür. Kurallar sade tutulur: 150-900 karakter, nokta ile
  biten, Türkçe karakter içeren, obje adından söz eden, site kalıntısı
  içermeyen paragraflar aday olur. Adaylar obje adı + anahtar kelimelerden
  kurulan sorguya TF-IDF kosinüs benzerliğiyle sıralanır (Türkçe ekleri hoş
  görmek için kelimelerin ilk beş harfi kök olarak kullanılır). Kaynak başına
  bir paragraf, Jaccard benzerliği 0.6'yı aşan tekrarlar elenir, en iyi 3
  paragraf gösterilir.

Cümle cümle seçim yerine bütün paragraf alınması metnin okunabilirliğini
korur; her paragrafın altında kaynağı yazılır.

## 5. Sohbet bağlamı

Son 3 turun objesi ve kelimeleri tutulur. Yeni turun kelimeleri önceki bir
turla kesişiyorsa iki tur aynı konudadır ve ortak kelime sorguya eklenir
(sırt çantası → el çantası turunda "aksesuar"). Kesişim yoksa konu değişmiş
sayılır ve eski tur aramaya karışmaz. Düz metin girdisi son objenin
bağlamında yeni arama yapar ("kalorisi ne kadar" → "sosisli sandviç kalorisi
ne kadar").

## 6. Kayıt

Her tur `records.json` dosyasında oturum bloğu altına yazılır: girdi, obje ve
güven, anahtar kelimeler, bağlam, sorgu, arama izi, gösterilen paragraflar ve
kaynakları, durum. Dosya önce geçici dosyaya yazılıp atomik taşınır.

## 7. Sınırlılıklar

- Karışık sahnelerde (birden çok eşit ağırlıklı obje) sınıflandırma belirsiz
  kalır; bu durumda düşük güven mesajı verilir.
- Tema dağarcığı elle derlenmiştir; kapsam dışı bir alanda kelimeler genel
  kalabilir. Dosyaya satır eklemek yeterlidir.
- Arama servisi zaman zaman istek sınırlar; bu durumda Vikipedi paragrafı tek
  başına gösterilir.
