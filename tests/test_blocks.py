# Numan Bekir Özçelik - 06.09.2026
"""Bilgi bloğu planlayıcısı, aile tespiti ve blok dizilimi"""

import json
import unittest

from app import config
from app.blocks import BlockPlanner


class BlockPlannerTest(unittest.TestCase):
    def setUp(self):
        self.planner = BlockPlanner()

    def test_family_from_keywords(self):
        self.assertEqual(self.planner.family(["ketçap", "fast food"]), "yemek")
        self.assertEqual(self.planner.family(["yaylı çalgı", "konser"]), "enstrüman")
        self.assertEqual(self.planner.family(["valiz", "aksesuar"]), "ürün")  # varsayılan
        self.assertEqual(self.planner.family([]), "ürün")

    def test_plan_starts_with_definition_and_adds_intent_block(self):
        titles = [b.title for b in self.planner.plan("sosisli sandviç", ["ketçap", "fast food"],
                                                     "ketçaplı sosisli sandviç tarifleri")]
        self.assertEqual(titles, ["Tanım", "İlgili", "Tarif", "Tarihçe"])

    def test_plan_skips_intent_block_when_query_is_plain_name(self):
        titles = [b.title for b in self.planner.plan("keman", ["yaylı çalgı"], "keman")]
        self.assertEqual(titles, ["Tanım", "Tarihçe", "Nasıl çalınır"])

    def test_low_confidence_keeps_only_definition(self):
        blocks = self.planner.plan("bot", ["ayakkabı"], "bot", confident=False)
        self.assertEqual([b.title for b in blocks], ["Tanım"])

    def test_family_blocks_require_hints(self):
        blocks = self.planner.plan("sırt çantası", ["aksesuar"], "sırt çantası")
        self.assertFalse(blocks[0].required_hints)  # tanım serbest
        self.assertTrue(all(b.required_hints for b in blocks[1:]))

    def test_schema_families_are_known_words(self):
        roles = json.loads(config.WORD_ROLES_PATH.read_text(encoding="utf-8"))
        for name, spec in self.planner.schema.items():
            for word in spec["aileler"]:
                self.assertIn(roles.get(word), ("aile", "alan"), f"{word} ({name}) aile ya da alan rolünde değil")

    def test_vehicles_recognised_by_domain_words(self):
        self.assertEqual(self.planner.family(["havacılık", "seyahat"]), "taşıt")
        self.assertEqual(self.planner.family(["denizcilik", "ulaşım"]), "taşıt")


if __name__ == "__main__":
    unittest.main()
