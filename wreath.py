import os
import sys
import random
import time
from functools import reduce
from collections import Counter
import itertools
import pdb
from young_tableau import FerrersDiagram
from yor import yor, load_yor
import numpy as np
from utils import partitions, weak_partitions, check_memory
import perm2
from coset_utils import coset_reps, young_subgroup_canonical, young_subgroup_perm, young_subgroup, perm_from_young_tuple, tup_set

def dot(perm, cyc):
    p_inv = perm.inv()
    new_cyc = tuple(cyc[p_inv[i] - 1] for i in range(1, len(cyc) + 1))
    p_cyc = CyclicGroup(new_cyc, cyc.order)
    return p_cyc

class CyclicGroup:
    def __init__(self, cyc, order): 
        self.cyc = cyc
        self.size = len(cyc)
        self.order = order

    def inv(self):
        cyc = tuple((self.order - a) % self.order for a in self.cyc)
        return CyclicGroup(cyc, self.order)

    def __mul__(self, other):
        cyc = tuple((a+b) % self.order for a, b in zip(self.cyc, other.cyc))
        return CyclicGroup(cyc, self.order)

    def __add__(self, other):
        return self.__mul__(other)

    def __repr__(self):
        return '{}/{}'.format(str(self.cyc), self.order)

    def __len__(self):
        return len(self.cyc)

    def __getitem__(self, i):
        try:
            return self.cyc[i]
        except:
            pdb.set_trace()

class WreathCycSn:
    def __init__(self, cyc, perm):
        assert perm.size == len(cyc)
        self.cyc = cyc
        self.perm = perm

    def __mul__(self, w):
        perm = self.perm * w.perm
        cyc = self.cyc + dot(self.perm, w.cyc)
        return WreathCycSn(cyc, perm)

    def inv(self):
        perm = self.perm.inv()
        cyc = dot(self.perm.inv(), self.cyc.inv())
        return WreathCycSn(cyc, perm)

    def __repr__(self):
        return '{} | {}'.format(self.cyc, self.perm)

def cyclic_irreps(weak_partition):
    '''
    Return a list of the irreps of the cylic group of order k
    given by the weak_partition, where weak_partition is a weak partition of k.

    weak_partition: list/tuple of nonnegative ints
    Ex:
        cyclic_irreps((1, 1)) = [exp{2i pi * 0/2}, exp{2i * pi * 1/2}]
    '''
    cyc_irreps = []

    for i, cnt in enumerate(weak_partition):
        if cnt > 0:
            cyc_irreps.extend([np.exp(2j*np.pi*i) / cyc_order] * cnt)

    return cyc_irreps

def load_partition(partition, prefix='/local/hopan/irreps/'):
    '''
    partition: tuple of ints
    Returns a dict of yor matrices mapping permutation to yor rep matrices
    If the partition is (0,): 
    '''
    n = sum(partition)
    if n == 0:
        return None
    fname = os.path.join(prefix,  's_{}/{}.pkl'.format(n, '_'.join(map(str, partition))))
    return load_yor(fname, partition)

def canonical_order(tup_rep):
    new_tup_rep = []
    idx = 0
    for lvl, tup in enumerate(tup_rep):
        if lvl == 0:
            new_tup_rep.append(tup)
        else:
            tnew = tuple(idx + i for i in tup)
            new_tup_rep.append(tnew)
        idx += len(tup)

    return tuple(new_tup_rep)

# This young subgroups that are direct products
# But here, the young subgroup wont be a subgroup of S_n, where n = sum(alpha)
# S_alpha, alpha=(4,4) will just be S_{1,2,3,4} x S_{1,2,3,4}
def young_subgroup_yor(alpha, _parts, prefix='/local/hopan/irreps/'):
    '''
    Compute the wreath product group for the irreps indexed by the weak partition alpha
    with partition components given by _parts
    alpha: tuple of ints, where each part is nonnegative
    _parts: list of partitions of the ints in alpha

    Ex usage:
        alpha = (4, 4)
        parts = [(2,2), (3,1)]

        alpha = (2, 3, 0)
        parts = [(2,0), (2,1), ()]
    '''
    assert len(alpha) == 3, 'alpha must be length 3'
    #assert sum(alpha) == 8, 'alpha must be a partition of 8'
    #assert (alpha[1] * 1 + alpha[2] * 2) % 3 == 0, 'alpha must be a valid configuration'

    wreath_dict = {}
    # load the irreps for each partition
    nonzero_parts = [load_partition(p, prefix) for p in _parts if sum(p) > 0]
    # group elements are in iterproduct(
    # iterate over s_alpha subgroup and compute tensor stuff
    # currently the S_alpha looks like S_{1, ..., alpha_1} x S_{1, ..., alpha_2} x ... x S_{1, ..., alpha_n}
    # but we'd like it to look like (1...alpha_1), (alpha_1+1 .... alpha_2), .... 

    for g in young_subgroup(alpha):
        # length of g should be length of nonzero_parts
        ms = [yd[perm] for yd, perm in zip(nonzero_parts, g)]
        # convert the permutation to the corresponding perm in S_{1, ..., alpha_1} x S_{alpha_1+1, ..., alpha_1+alpha_2} x ...
        gprime = canonical_order(g) # (1,2,3,4)(1,2) -> (1,2,3,4)(5,6)
        tup = tuple(i for t in gprime for i in t)
        wreath_dict[tup] = reduce(np.kron, ms)

    return wreath_dict

def wreath_yor(alpha, _parts, prefix='/local/hopan/'):
    '''
    alpha: weak partition of 8 into 3 parts?
    _parts: list of partitions of each part of alpha
    Return a dict mapping group elmeent in S_8 -> rep
    The rep actually needs to be a dictionary of tuples (i, j) -> matrix
    where the i, j denote the i, j block in the matrix.
    Ex:
        alpha = (0, 0, 0, 0, 1, 1, 1, 1)
        _parts = [(2,2), (3,1)]
    '''
    n = sum(alpha)
    _sn = perm2.sn(n, prefix)
    young_sub = young_subgroup_perm(alpha)
    young_sub_set = tup_set(young_sub)
    young_yor = young_subgroup_yor(alpha, _parts, os.path.join(prefix, 'irreps'))
    reps = coset_reps(_sn, young_sub)
    rep_dict = {}
    print('Len coset reps: {}'.format(len(reps)))
    print('Total loop iters: {}'.format(len(_sn) * len(reps) * len(reps)))
    cnts = np.zeros((len(reps), len(reps)))

    # loop over the group
    # things we need are: group element inv, group element multiplication
    # then grabbing the yor for the appropriate yor thing
    for g in _sn:
        g_rep = {}
        for i, t_i in enumerate(reps):
            for j, t_j in enumerate(reps):
                ti_g_tj = t_i.inv() * g * t_j
                if ti_g_tj.tup_rep in young_sub_set:
                    g_rep[(i, j)] = young_yor[ti_g_tj.tup_rep]
                    cnts[i, j] = cnts[i, j] + 1

        rep_dict[g] = g_rep 

    return rep_dict, cnts

def get_mat(g, yor_dict):
    '''
    g: perm2.Perm2 object
    yor_dict: dict mapping perm2.Perm2 object -> (dict of (i, j) -> numpy matrix)

    Returns matrix for this ydict
    '''
    yg = yor_dict[g]
    vs = list(yg.values())
    block_size = vs[0].shape[0]
    size = len(yg) * block_size
    mat = np.zeros((size, size))

    for (i, j), v in yg.items():
        x1, x2 = (block_size*i, block_size*i+block_size)
        y1, y2 = (block_size*j, block_size*j+block_size)
        mat[x1:x2, y1:y2] = v

    return mat

def mult(g, h, yd):
    '''
    g: perm2.Perm2
    h: perm2.Perm2
    yd: dictionary mapping Perm2 objects -> (dicts of (i, j) int tuples -> numpy matrices)
            which represent the wreath product matrices
    Returns a numpy matrix
    '''
    mat_g = get_mat(g, yd)
    mat_h = get_mat(h, yd)
    return mat_g.dot(mat_h)

def test_wreath_class():
    perm = perm2.Perm2.from_tup((1,3,4,2))
    cyc = CyclicGroup((0, 1, 0, 2), 3)
    w = WreathCycSn(cyc, perm)
    w_inv = w.inv()
    print('w: {}'.format(w))
    print('w\': {}'.format(w_inv))
    print('I: {}'.format(w*w_inv))
    print('I: {}'.format(w_inv*w))

def test_wreath(alpha, _parts, pkl_prefix='/local/hopan/'):
    #if len(sys.argv) > 1:
    #    pkl_prefix = sys.argv[1]
    #else:
    #    pkl_prefix = '/local/hopan/irreps/'
    start = time.time()
    print('alpha: {} | parts: {}'.format(alpha, _parts))
    wreath_yor(alpha, _parts, pkl_prefix)
    print('Elapsed: {:.2f}'.format(time.time() - start))
    print('perm2 cache hits: {}'.format(perm2.HITS['hits']))

if __name__ == '__main__':
    alpha = (0, 1, 7)
    #alpha = (2, 6, 0)
    _parts = ((), (1,), (5,2))
    #_parts = ((1,1), (4,2), ())
    if len(sys.argv) > 1:
        print('looking in {}'.format(sys.argv[1]))
        test_wreath(alpha, _parts, sys.argv[1])
    else:
        print('using default prefix')
        test_wreath(alpha, _parts)
    check_memory()
