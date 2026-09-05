# Numan Bekir Özçelik - 04.09.2026
"""URL'den veya yerelden görüntü okur, modele girmeden önce toparlar (exif, rgb, boyut)"""

import io
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

CHUNK_SIZE = 64 * 1024
MAX_REDIRECTS = 5


class ImageLoadError(Exception):
    """Mesajı doğrudan kullanıcıya gösterilir"""


class ImageLoader:
    def load(self, source: str, kind: str):
        """RGB görüntü döndürür, sorun varsa ImageLoadError"""
        if source.lower().split("?")[0].endswith(".svg"):
            # svg piksel değil çizim talimatı içerir, tespit modeli fotoğraf bekler
            raise ImageLoadError("SVG gibi vektörel formatları desteklemiyorum. JPG ya da PNG dener misin?")
        data = self._download(source) if kind == "url" else self._read_file(source)
        return self._decode(data)

    def _download(self, url: str) -> bytes:
        # redirect'ler elle izlenir; her durak isteğe çıkmadan ÖNCE iç ağ denetiminden geçer
        for _ in range(MAX_REDIRECTS + 1):
            if urlparse(url).scheme not in ("http", "https"):
                raise ImageLoadError("Bu adresi desteklemiyorum.")
            self._reject_internal_hosts(url)
            try:
                response = requests.get(url, stream=True, timeout=config.DOWNLOAD_TIMEOUT,
                                        allow_redirects=False,
                                        headers={"User-Agent": "Mozilla/5.0"})
            except requests.RequestException:
                raise ImageLoadError("Adrese ulaşamadım. Bağlantını ve adresi kontrol eder misin?")
            if response.is_redirect or response.is_permanent_redirect:
                target = response.headers.get("location")
                response.close()
                if not target:
                    raise ImageLoadError("Adres geçersiz bir yönlendirme döndürdü.")
                url = urljoin(url, target)
                continue
            break
        else:
            raise ImageLoadError("Adres çok fazla yönlendirme yapıyor.")

        with response:
            if response.status_code != 200:
                raise ImageLoadError(f"Adres görüntü yerine {response.status_code} hatası döndürdü.")
            content_type = response.headers.get("content-type", "").lower()
            if content_type.startswith("text/"):
                raise ImageLoadError("Bu adres bir görüntü değil, bir web sayfası döndürüyor.")

            limit = config.MAX_DOWNLOAD_MB * 1024 * 1024
            data = bytearray()
            try:
                for chunk in response.iter_content(CHUNK_SIZE):
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ImageLoadError(f"Dosya {config.MAX_DOWNLOAD_MB} MB sınırını aşıyor.")
            except requests.RequestException:
                raise ImageLoadError("İndirme yarıda kesildi. Tekrar dener misin?")
        return bytes(data)

    def _reject_internal_hosts(self, url: str):
        # iç ağa (localhost, 192.168.x vb.) istek atılmasın
        host = urlparse(url).hostname
        if not host:
            raise ImageLoadError("Adresi çözümleyemedim. Kontrol eder misin?")
        try:
            address_infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            raise ImageLoadError("Alan adını çözümleyemedim. Adresi kontrol eder misin?")
        for info in address_infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ImageLoadError("Bu adresi desteklemiyorum.")

    def _read_file(self, path: str) -> bytes:
        file_path = Path(path)
        if not file_path.is_file():
            raise ImageLoadError(f"Bu konumda bir dosya bulamadım: {path}. Yolu kontrol eder misin?")
        if file_path.stat().st_size > config.MAX_DOWNLOAD_MB * 1024 * 1024:
            raise ImageLoadError(f"Dosya {config.MAX_DOWNLOAD_MB} MB sınırını aşıyor.")
        try:
            return file_path.read_bytes()
        except OSError:
            raise ImageLoadError("Dosyayı okuyamadım. İzinleri kontrol eder misin?")

    def _decode(self, data: bytes):
        if not data:
            raise ImageLoadError("Dosya boş görünüyor.")
        try:
            image = Image.open(io.BytesIO(data))
            image = ImageOps.exif_transpose(image)  # telefon fotoğrafların yan gelmemesi için
            image = image.convert("RGB")  # gif/tiff gibi çok karelilerde ilk kare alınır
        except Image.DecompressionBombError:
            raise ImageLoadError("Görüntünün çözünürlüğü işleyemeyeceğim kadar yüksek.")
        except (UnidentifiedImageError, OSError):
            raise ImageLoadError("Bu geçerli bir görüntü dosyası değil. JPG ya da PNG formatında bir dosya dener misin?")

        if min(image.size) < config.MIN_IMAGE_SIDE:
            raise ImageLoadError("Görüntü tespit için çok küçük. Daha yüksek çözünürlüklü bir görsel dener misin?")
        if max(image.size) > config.MAX_IMAGE_SIDE:
            # tespit kalitesini etkilemeden bellek için küçültme
            image.thumbnail((config.MAX_IMAGE_SIDE, config.MAX_IMAGE_SIDE))
        return image
