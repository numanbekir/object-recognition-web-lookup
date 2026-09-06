# Numan Bekir Özçelik - 06.09.2026
"""Tur kayıtlarını records.json'a yazar.

Sıfır kurulum şartı için veritabanı yerine tek JSON dosyası kullanılır.
Kayıtlar oturum bloklarında birikir. Her açılış yeni bir blok açar ve tur
numarası oturum içinde 1'den başlar. Boş oturum bloğu yazılmaz. Dosyanın
tamamı önce geçici dosyaya yazılıp atomik taşınır, yarım yazım eski kaydı
bozamaz. Kayıt hatası uygulamayı düşürmez.
"""

import json
import os
from datetime import datetime
from pathlib import Path


class Storage:
    def __init__(self, path):
        self.path = Path(path)
        self.records = {"uygulama": "gorsel-sohbet", "oturumlar": []}
        self._session = None  # ilk kayıtla açılır
        # oturum damgası açılışta alınır, böylece turlardan önce kalır
        self._started = datetime.now().isoformat(timespec="seconds")

    def load(self):
        """Var olan dosyayı okur, bozuksa kenara alır, bilgi notu döndürür."""
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("oturumlar"), list):
                raise ValueError("beklenmeyen yapı")
            self.records = data
            return None
        except (OSError, ValueError):
            broken = self.path.with_name(self.path.name + ".bozuk")
            try:
                os.replace(self.path, broken)
                return (f"{self.path.name} okunamadı, {broken.name} olarak kenara "
                        "aldım ve temiz bir dosyayla devam ediyorum.")
            except OSError:
                return f"{self.path.name} okunamadı, bu oturumun kayıtları yazılamayabilir."

    def _current_session(self) -> dict:
        if self._session is None:
            self._session = {"basladi": self._started, "turlar": []}
            self.records["oturumlar"].append(self._session)
        return self._session

    def next_turn_no(self) -> int:
        return len(self._session["turlar"]) + 1 if self._session else 1

    def append(self, record: dict) -> bool:
        self._current_session()["turlar"].append(record)
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            temp.write_text(json.dumps(self.records, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            os.replace(temp, self.path)
            return True
        except OSError:
            return False
