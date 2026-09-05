# Numan Bekir Özçelik - 05.09.2026
"""Arayüzün headless açılıp kapanabildiğini doğrular; CSS hataları burada yakalanır"""

import unittest

from app.ui import ChatApp


class DummyDetector:
    vocab_size = 1199

    def is_ready_on_disk(self):
        return True

    def load(self, progress=None):
        pass


class UiSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_app_mounts(self):
        app = ChatApp(None, DummyDetector(), None, None, None)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertTrue(app.query_one("#inbox"))
            self.assertTrue(app.query_one("#status1"))


if __name__ == "__main__":
    unittest.main()
