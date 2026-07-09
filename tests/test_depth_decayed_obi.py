import unittest
from realtime_engine import calc_book_imbalance

class TestDepthDecayedOBI(unittest.TestCase):
    def test_calc_book_imbalance_decayed(self):
        # 1. Test balanced book
        bids = [(60000.0, 1.0), (59990.0, 2.0)]
        asks = [(60010.0, 1.0), (60020.0, 2.0)]
        val = calc_book_imbalance(bids, asks, 2)
        self.assertAlmostEqual(val, 0.0)
        
        # 2. Test bid dominated book
        bids = [(60000.0, 2.0), (59990.0, 1.0)]
        asks = [(60010.0, 1.0), (60020.0, 1.0)]
        val_bid = calc_book_imbalance(bids, asks, 2)
        self.assertTrue(val_bid > 0.0)
        
        # 3. Test closer levels have higher weight
        # bids: level 0 = 2.0, level 1 = 1.0
        # asks: level 0 = 1.0, level 1 = 2.0
        # since bid decayed > ask decayed, balance should be positive,
        # even though simple sum is equal (3.0 vs 3.0).
        bids = [(60000.0, 2.0), (59990.0, 1.0)]
        asks = [(60010.0, 1.0), (60020.0, 2.0)]
        val_weight = calc_book_imbalance(bids, asks, 2)
        self.assertTrue(val_weight > 0.0)
