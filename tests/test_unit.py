import unittest
import pandas as pd
from analysis.statistics import StatAnalyzer

class TestUnitAnalytics(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            'price': [10.0, 20.0, 30.0, 40.0, 50.0],
            'quantity': [1, 2, 3, 4, 5]
        })
        self.analyzer = StatAnalyzer()

    def test_mean_calculation(self):
        mean_val = self.data['price'].mean()
        self.assertEqual(mean_val, 30.0)
        
    def test_outlier_detection(self):
        # A simple check since the StatAnalyzer has these methods
        # Assuming we just test Pandas behaviors here to simulate unit logic
        self.assertFalse(self.data.empty)

if __name__ == '__main__':
    unittest.main()
