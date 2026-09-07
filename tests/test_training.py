# Numan Bekir Özçelik - 07.09.2026
"""Eğitim yardımcıları, ağ ve veri gerektirmez"""

import unittest

import numpy as np

from training.train_probe import accuracy, stratified_split, train, zero_shot_accuracy


class TrainingTest(unittest.TestCase):
    def test_stratified_split_keeps_ratio_per_class(self):
        labels = np.array([0] * 10 + [1] * 20)
        train_idx, val_idx = stratified_split(labels, 0.2, seed=1)
        self.assertEqual(sorted(labels[val_idx].tolist()), [0] * 2 + [1] * 4)
        self.assertEqual(len(train_idx) + len(val_idx), 30)

    def test_accuracy_and_zero_shot(self):
        scores = np.array([[0.9, 0.1], [0.2, 0.8], [0.6, 0.4]])
        self.assertAlmostEqual(accuracy(scores, np.array([0, 1, 1])), 2 / 3)
        x = np.array([[1.0, 0.0], [0.0, 1.0]]); text = np.array([[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(zero_shot_accuracy(x, text, np.array([0, 1])), 1.0)

    def test_linear_probe_learns_separable_data(self):
        rng = np.random.default_rng(0)
        x = np.concatenate([rng.normal(1, 0.2, (40, 4)), rng.normal(-1, 0.2, (40, 4))]).astype(np.float32)
        y = np.array([0] * 40 + [1] * 40)
        layer = train(x, y, 2, epochs=30, x_val=x, y_val=y, log=lambda *_: None)
        import torch
        with torch.no_grad():
            scores = layer(torch.tensor(x)).numpy()
        self.assertGreater(accuracy(scores, y), 0.95)


if __name__ == "__main__":
    unittest.main()
