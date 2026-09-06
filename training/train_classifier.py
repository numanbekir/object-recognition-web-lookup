# Numan Bekir Özçelik - 06.09.2026
"""Cümle sınıflandırıcısını eğitir, modeli models klasörüne yazar.

TF-IDF kelime ve karakter n-gramları üzerinde lojistik regresyon kurulur,
Türkçe ekleri karakter n-gramlar yakalar. Train ve test ayrımı sızıntıyı
önlemek için cümle bazlı değil domain bazlıdır, aynı sitenin kalıp
cümleleri iki kümeye bölünemez. Uygulama dolgu kararını yalnız yüksek
güvenle verdiği için rapor bu eşikteki davranışı da ölçer.
"""

import json
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402

LABELS = Path(__file__).parent / "data" / "labels.jsonl"
TEST_BUCKETS = 5  # domain'lerin ~1/5'i test kümesine


def load_rows():
    with open(LABELS, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def is_test_domain(domain: str) -> bool:
    return zlib.crc32(domain.encode("utf-8")) % TEST_BUCKETS == 0


def main():
    from joblib import dump
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.pipeline import FeatureUnion, Pipeline

    rows = load_rows()
    if len(rows) < 300:
        print(f"{len(rows)} etiket az görünüyor, kılavuz 500-800 öneriyor.")
    train = [row for row in rows if not is_test_domain(row["domain"])]
    test = [row for row in rows if is_test_domain(row["domain"])]
    print(f"eğitim {len(train)} cümle, test {len(test)} cümle, "
          f"{len({r['domain'] for r in test})} test domaini")

    pipeline = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                     min_df=2)),
        ])),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])
    pipeline.fit([r["cumle"] for r in train], [r["etiket"] for r in train])

    texts = [r["cumle"] for r in test]
    truth = [r["etiket"] for r in test]
    predictions = pipeline.predict(texts)
    print(classification_report(truth, predictions,
                                target_names=["dolgu", "bilgi"], digits=2))

    # uygulamadaki temkinli eşik, dolgu kararı yalnız yüksek güvenle verilir
    threshold = config.CLASSIFIER_FILLER_THRESHOLD
    probabilities = pipeline.predict_proba(texts)[:, 0]
    dropped = [(p, t) for p, t in zip(probabilities, truth) if p >= threshold]
    wrong = sum(1 for _p, t in dropped if t == 1)
    print(f"eşik {threshold} ile {len(dropped)} cümle elenirdi, "
          f"{wrong} tanesi aslında bilgiydi")

    config.MODELS_DIR.mkdir(exist_ok=True)
    dump(pipeline, config.SENTENCE_CLASSIFIER_PATH)
    print(f"model yazıldı, {config.SENTENCE_CLASSIFIER_PATH}")


if __name__ == "__main__":
    main()
