import unittest
import pandas as pd
from etl.transform import Transform

class TestETL(unittest.TestCase):
    def setUp(self):
        self.raw_data = pd.DataFrame({
            'id': [1, 2, 2, 3],
            'name': ['A', 'B', 'B', 'C']
        })
        self.transformer = Transform()

    def test_remove_duplicates(self):
        # Assuming transformer cleans duplicates
        cleaned = self.transformer.clean_data({'test': self.raw_data})['test']
        self.assertEqual(len(cleaned), 3)

if __name__ == '__main__':
    unittest.main()
