# Numan Bekir Özçelik - 06.09.2026
"""Arama niyeti üreticisinin Türkçe ek ve şablon kuralları"""

import unittest

from app.intent import IntentBuilder, harmony, merge_names, plural, plural_possessive, possessive


class SuffixTest(unittest.TestCase):
    def test_vowel_harmony(self):
        self.assertEqual("sos" + harmony("sos", "lı"), "soslu")
        self.assertEqual("et" + harmony("et", "lı"), "etli")
        self.assertEqual("süt" + harmony("süt", "lı"), "sütlü")
        self.assertEqual("ketçap" + harmony("ketçap", "lı"), "ketçaplı")

    def test_plural_keeps_possessive_in_compounds(self):
        self.assertEqual(plural("sırt çantası"), "sırt çantaları")
        self.assertEqual(plural("cep telefonu"), "cep telefonları")
        self.assertEqual(plural("fotoğraf makinesi"), "fotoğraf makineleri")
        self.assertEqual(plural("keman"), "kemanlar")
        self.assertEqual(plural("kapı"), "kapılar")  # tek kelimede iyelik aranmaz

    def test_possessive_forms(self):
        self.assertEqual(possessive("demlik"), "demliği")  # ünsüz yumuşaması
        self.assertEqual(possessive("pizza"), "pizzası")
        self.assertEqual(plural_possessive("keman"), "kemanları")
        self.assertEqual(plural_possessive("demlik"), "demlikleri")

    def test_merge_names(self):
        self.assertEqual(merge_names("el çantası", "sırt çantası"), "el ve sırt çantası")
        self.assertIsNone(merge_names("keman", "gitar"))
        self.assertIsNone(merge_names("el çantası", "el çantası"))


class IntentTest(unittest.TestCase):
    def setUp(self):
        self.builder = IntentBuilder()

    def test_scenario_one(self):
        self.assertEqual(
            self.builder.build("sırt çantası", ["aksesuar", "seyahat", "okul", "ergonomik"]),
            "ergonomik seyahat ve okul sırt çantaları")
        self.assertEqual(
            self.builder.build("el çantası", ["aksesuar", "kadın", "deri"], "sırt çantası"),
            "kadın deri el ve sırt çantaları")

    def test_scenario_two(self):
        self.assertEqual(
            self.builder.build("sosisli sandviç", ["ketçap", "fast food", "sosis"], "sandviç"),
            "ketçaplı sosisli sandviç tarifleri")  # sosis obje adında zaten var
        self.assertEqual(self.builder.build("pizza", ["hamurlu yemek", "peynir"], "hamburger"),
                         "peynirli pizza tarifleri")  # ad paylaşımı yok, özne yeni obje

    def test_single_word_object_with_use(self):
        self.assertEqual(self.builder.build("demlik", ["sofra", "çay", "demleme"]),
                         "sofra ve çay demlikleri")

    def test_vehicles_skip_use_words(self):
        self.assertEqual(self.builder.build("uçak", ["havacılık", "seyahat"]), "uçak")

    def test_opposite_qualities_cancel_out(self):
        self.assertEqual(self.builder.build("pantolon", ["erkek", "moda", "kadın", "giyim"]),
                         "pantolon")
        self.assertEqual(self.builder.build("pantolon", ["erkek", "moda"]), "erkek pantolonlar")

    def test_no_query_words_returns_object(self):
        self.assertEqual(self.builder.build("fotoğraf makinesi", ["fotoğrafçılık", "lens"]),
                         "fotoğraf makinesi")


if __name__ == "__main__":
    unittest.main()
