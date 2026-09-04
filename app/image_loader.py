# Numan Bekir Özçelik - 04.09.2026
"""URL'den veya yerelden görüntü okur, modele girmeden önce toparlar (exif, rgb, boyut)"""


class ImageLoadError(Exception):
    """Mesajı doğrudan kullanıcıya gösterilir"""


class ImageLoader:
    def load(self, source: str):
        """RGB görüntü döndürür, sorun varsa ImageLoadError"""
        raise NotImplementedError

    def _load_from_url(self, url: str):
        raise NotImplementedError

    def _load_from_path(self, path: str):
        raise NotImplementedError
