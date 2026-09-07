# Görüntülü Sohbet Uygulaması

Kullanıcının verdiği adresteki ya da yerel dosyadaki görüntünün ön planındaki
objeyi tanır, objeye uygun anahtar kelimeler çıkarır, web üzerinde arama yapıp
objeyle ilgili bilgileri başlıklı bloklar halinde sunar. Her tur kayıt dosyasına
yazılır ve sohbet bağlamı oturum boyunca sürdürülür.

## Kurulum

Python 3.10 ve üzeri gerekir. Uygulama tamamen işlemci üzerinde çalışır.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Görüş modelinin ağırlığı ilk çalıştırmada bir kereye mahsus indirilir, ardından
dağarcık kodlanıp models klasörüne önbelleklenir. Sonraki açılışlar birkaç
saniye sürer.

## Kullanım

```bash
python3 main.py
```

Görsel adresi ya da dosya yolu girilir, dosyayı terminale sürüklemek de çalışır.
Görselin yanına bir soru yazılırsa o turun araması soruya göre kurulur.
Görsel analizinden sonra düz metin yazılırsa aynı obje bağlamında yeni arama
yapılır. Çıkmak için q yazılır.

Debug seçeneği her adımın kararlarını gösterir, plain seçeneği terminal arayüzü
yerine düz satır modunu açar.

```bash
python3 main.py --debug
python3 main.py --plain
```

## Nasıl çalışır

1. Görüntü yüklenir, doğrulanır ve modele hazırlanır.
2. Görüş modeli görüntüyü kodlar, 1200 obje adıyla karşılaştırır ve en yakın adı
   obje olarak seçer. Aynı vektör 480 tema kavramıyla karşılaştırılır, en güçlü
   temaların Türkçe karşılıkları anahtar kelime olur.
3. Obje adı, rol etiketli anahtar kelimeler ve önceki turun bağlamından kural
   tabanlı bir Türkçe arama cümlesi kurulur.
4. Objenin ailesine göre bilgi blokları planlanır. Her blok kendi sorgusunu atar.
   Tarif blokları sayfanın yapısından malzeme ve adım listesi, çeşit blokları alt
   başlık listesi çıkarır. Diğer bloklar Vikipedi bölümünden ya da tf-idf ile
   seçilmiş paragraftan dolar.
5. Bloklar başlıklı ve numaralı kaynaklı tek metin olarak gösterilir ve kayıt
   dosyasına yazılır. Oturum, gösterilen kaynakları hatırlar.

## Dosyalar

- main.py, girdi ayrıştırma ve tur akışı
- app/image_loader.py, görüntü okuma ve doğrulama
- app/vision.py, görüş modeliyle obje ve tema çıkarımı
- app/intent.py, anahtar kelimelerden Türkçe arama niyeti üretimi
- app/blocks.py, objenin ailesine göre bilgi bloklarını planlama
- app/structure.py, sayfa yapısından liste, adım ve alt başlık çıkarımı
- app/search.py, Vikipedi ve arama motoru sorguları
- app/extractor.py, sayfa indirme ve paragraf seçimi
- app/session.py, sohbet bağlamı ve hafıza
- app/storage.py, kayıt dosyası
- app/ui.py, terminal arayüzü
- data klasörü, obje adları, tema haritası, kelime rolleri ve blok şeması
- tests klasörü, birim testleri
- ornek_kayit.json, görev senaryolarıyla üretilmiş örnek kayıt dosyası

Testler şu komutla çalışır.

```bash
python3 -m unittest discover -s tests -t .
```

Model tercihi gerekçeleri ve teknik ayrıntılar RAPOR.md dosyasındadır.
