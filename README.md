# Görüntülü Sohbet Uygulaması

Verilen bir URL'deki ya da yerel dosyadaki görüntünün ön planındaki objeyi
tanır, objeye uygun anahtar kelimeler çıkarır, web'de arama yapıp sayfa
içeriklerinden derlenen bir metni sunar. Tüm etkileşimler `records.json`
dosyasına kaydedilir, sohbet bağlamı oturum boyunca sürdürülür.

## Kurulum

Python 3.10+ gerektirir.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Uygulama tamamen CPU üzerinde çalışır. PyTorch'un varsayılan paketi büyük
olduğundan, indirme boyutunu küçültmek isterseniz kurulumdan önce CPU
sürümünü kurabilirsiniz (isteğe bağlı):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Model ağırlığı ve WordNet verisi ilk çalıştırmada bir kereye mahsus otomatik
indirilir.

## Kullanım

```bash
python3 main.py
```

- Görsel URL'si ya da dosya yolu girin (dosyayı terminale sürüklemek de çalışır).
- Görsel analizinden sonra düz metin yazarak aynı obje bağlamında yeni arama
  yapabilirsiniz (örn. `fiyatları ne kadar`).
- Çıkış: `q`

Pipeline kararlarını ayrıntılı görmek için: `python3 main.py --debug`

## Yapı

- `main.py` — CLI döngüsü ve girdi ayrıştırma
- `app/` — görüntü, tespit, anahtar kelime, arama, içerik, sentez, bağlam,
  kayıt ve arayüz katmanları
- `training/` — cümle sınıflandırıcısının veri toplama, etiketleme ve eğitim
  kodları
- `data/` — tespit dağarcığı ve anahtar kelime haritaları
- `models/` — eğitilmiş sınıflandırıcı ve ilk çalıştırmada inen tespit modeli
- `scripts/` — yardımcı araçlar (dağarcık doğrulama)
- `tests/` — birim testleri

Model tercihi gerekçeleri ve teknik ayrıntılar: `RAPOR.md`
