import unittest
from young_tableau import FerrersDiagram, YoungTableau
from yor import *
from utils import partitions
import pdb
from fft import fft, fourier_transform
import numpy as np
from perm import Perm

class TestYoungTableau(unittest.TestCase):
    def test_get_rowcols(self):
        contents = [(1, 3, 5), (2,), (4, )]

        y = YoungTableau(contents, (1, 3, 5, 2, 4))
        for r, row in enumerate(contents):
            row_idx = r + 1
            for c, val in enumerate(row):
                col_idx = c + 1
                self.assertEqual(y.get_row(val), row_idx)
                self.assertEqual(y.get_col(val), col_idx)

    def test_valid(self):
        valid_tab = [(1, 3, 4), (2,), (5, )]
        invalid_tab = [(1, 2, 4), (5,), (3, )]

        v_yt = YoungTableau(valid_tab, (1, 3, 4, 2, 5))
        inv_yt = YoungTableau(invalid_tab, (1, 2, 4, 5, 3))
        self.assertTrue(v_yt.valid())
        self.assertFalse(inv_yt.valid())

    def test_lt(self):
        p1 = [(1, 3, 5), (2,), (4, )]
        p2 = [(1, 3, 4), (2,), (5, )]
        y1 = YoungTableau(p1, (1, 3, 5, 2, 4))
        y2 = YoungTableau(p2, (1, 3, 4, 2, 5))
        self.assertTrue(y1 < y2)

    def test_gentableaux(self):
        p_dict = {
            (4, ): 1,
            (3, 1): 3,
            (2, 2): 2,
            (2, 1, 1): 3,
            (1, 1, 1, 1): 1,
        }
        for partition, num_parts in p_dict.items():
            f = FerrersDiagram(partition)
            tableaux = f.gen_tableaux()
            self.assertEqual(len(tableaux), num_parts)

    def test_ysemi(self):
        ferr = FerrersDiagram((3, 1))
        p12 = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, 1]])
        p23 = np.array([[0.5, 0.75, 0], [1, -0.5, 0], [0, 0, 1]])
        p34 = np.array([[1, 0, 0], [0, 1./3., 8./9.], [0, 1, -1./3.]])
        self.assertTrue(np.allclose(p12, ysemi(ferr, Perm([(1,2)]))))
        self.assertTrue(np.allclose(p23, ysemi(ferr, Perm([(2,3)]))))
        self.assertTrue(np.allclose(p34, ysemi(ferr, Perm([(3,4)]))))

    def test_fft(self):
        # any random function
        f = lambda p: 1 if p[1] == 2 else 3.23
        for partition in partitions(5):
            ferrers = FerrersDiagram(partition)
            fft_result = fft(f, ferrers) # which irrep
            full_transform = fourier_transform(f, ferrers)
            fft_sum = np.sum(fft_result)
            self.assertTrue(np.allclose(fft_result, full_transform))

if __name__ == '__main__':
    unittest.main()
