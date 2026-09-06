# Görüntülü Sohbet Uygulaması

Verilen bir URL'deki ya da yerel dosyadaki görüntünün ön planındaki objeyi
tanır, objeye uygun anahtar kelimeler çıkarır, Vikipedi ve web aramasından
derlenen paragrafları sunar. Tüm turlar `records.json` dosyasına kaydedilir,
sohbet bağlamı oturum boyunca sürdürülür.

## Kurulum

Python 3.10+ gerektirir. Uygulama tamamen CPU üzerinde çalışır.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

CLIP ağırlığı (~340 MB) ilk çalıştırmada bir kereye mahsus indirilir, ardından
dağarcık kodlanıp `models/` altına önbelleklenir. Sonraki açılışlar birkaç
saniye sürer.

## Kullanım

```bash
python3 main.py
```

- Görsel URL'si ya da dosya yolu girin (dosyayı terminale sürüklemek de çalışır).
- Görsel analizinden sonra düz metin yazarak aynı obje bağlamında yeni arama
  yapabilirsiniz (örn. `kalorisi ne kadar`).
- Çıkış: `q`

Seçenekler: `--debug` pipeline kararlarını gösterir, `--plain` terminal
arayüzü yerine düz satır modunu açar (tty olmayan ortamda otomatik seçilir).

## Nasıl çalışır

```
girdi ─► görüntü yükle ─► CLIP ─► obje adı + anahtar kelimeler ─► kaydet
      ─► Vikipedi tanımı + DuckDuckGo araması ─► alakalı paragraflar ─► göster ─► kaydet
```

1. **Obje tespiti (sıfır atış):** CLIP ViT-B/32 görüntüyü kodlar, 1200 obje
   adıyla kosinüs benzerliği hesaplanır, en yakın ad objedir.
2. **Anahtar kelimeler:** Aynı görüntü vektörü 480 tema kavramıyla karşılaştırılır,
   en güçlü temaların Türkçe karşılıkları anahtar kelime olur. Tema listesi
   `data/theme_map.json` dosyasında durur ve koda dokunmadan büyütülebilir.
3. **Bağlam:** Yeni turun kelimeleri önceki bir turla kesişiyorsa ortak kelime
   arama sorgusuna eklenir (sırt çantası → el çantası: "aksesuar").
4. **Metin:** Vikipedi giriş paragrafı ve arama sonuçlarından, objeyle en alakalı
   paragraflar TF-IDF benzerliğiyle seçilir. Cümle kolajı yapılmaz, paragraf
   bütün alınır.

## Yapı

- `main.py` — girdi ayrıştırma ve tur akışı
- `app/image_loader.py` — URL/dosya okuma, doğrulama, EXIF düzeltme
- `app/vision.py` — CLIP ile obje ve tema çıkarımı
- `app/search.py` — Vikipedi ve DuckDuckGo araması
- `app/extractor.py` — sayfa indirme ve paragraf seçimi
- `app/session.py` — sohbet bağlamı
- `app/storage.py` — JSON kayıt
- `app/ui.py` — terminal arayüzü (Textual)
- `data/` — obje adları (Türkçe) ve tema haritası
- `tests/` — birim testleri: `python3 -m unittest discover -s tests -t .`

Model tercihi gerekçeleri ve teknik ayrıntılar: `RAPOR.md`
