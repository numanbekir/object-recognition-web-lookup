# Numan Bekir Özçelik - 07.09.2026
"""Arayüzün ekransız açılıp kapanabildiğini ve kartın kademeli dolabildiğini doğrular"""

import unittest

from textual.widgets import Markdown, Static

from app.ui import ChatApp


class DummyVision:
    vocab_size = 1200

    def is_ready_on_disk(self):
        return True

    def load(self, progress=None):
        pass


class UiSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_app_mounts_and_card_fills(self):
        app = ChatApp(None, DummyVision(), None, None, None, None, None, debug=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertTrue(app.query_one("#inbox"))
            card = app.open_card()
            await pilot.pause()
            card.set_head("sosisli sandviç", 0.9, ["ketçap", "fast food"], "ketçaplı sosisli sandviç tarifleri", size="960x469")
            card.set_progress("web'de aranıyor")
            card.set_body("### Tanım\n\nSosisli sandviç bir sandviçtir. [1]\n")
            card.set_sources(["tr.wikipedia.org"], {"tr.wikipedia.org": "https://tr.wikipedia.org/wiki/X"})
            card.add_detail("arama", "5 aday")
            card.set_stat("kayit", "1. tur")
            card.finish(7.1)
            await pilot.pause()
            def text_of(widget_id):
                widget = card.query_one(widget_id, Static)
                return str(getattr(widget, "content", None) or widget.render())

            self.assertIn("Sosisli Sandviç", text_of("#cell_object"))
            self.assertIsInstance(card.query_one("#body"), Markdown)
            self.assertIn("7.1 sn", text_of("#stats"))
            self.assertFalse(card.query_one("#progress").display)  # bitişte ilerleme gizlenir


if __name__ == "__main__":
    unittest.main()
