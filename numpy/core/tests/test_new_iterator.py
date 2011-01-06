import numpy as np
from numpy import array, arange, newiter
from numpy.testing import *
import sys

import warnings

def iter_coords(i):
    ret = []
    while not i.finished:
        ret.append(i.coords)
        i.iternext()
    return ret

def iter_indices(i):
    ret = []
    while not i.finished:
        ret.append(i.index)
        i.iternext()
    return ret

def iter_iterindices(i):
    ret = []
    while not i.finished:
        ret.append(i.iterindex)
        i.iternext()
    return ret

def test_iter_refcount():
    # Make sure the iterator doesn't leak

    a = arange(6)
    dt = np.dtype('f4').newbyteorder()
    rc_a = sys.getrefcount(a)
    rc_dt = sys.getrefcount(dt)
    it = newiter(a, [],
                [['readwrite','updateifcopy']],
                casting='unsafe',
                op_dtypes=[dt])
    assert_(sys.getrefcount(a) > rc_a)
    assert_(sys.getrefcount(dt) > rc_dt)
    it = None
    assert_equal(sys.getrefcount(a), rc_a)
    assert_equal(sys.getrefcount(dt), rc_dt)

def test_iter_best_order():
    # The iterator should always find the iteration order
    # with increasing memory addresses

    # Test the ordering for 1-D to 5-D shapes
    for shape in [(5,), (3,4), (2,3,4), (2,3,4,3), (2,3,2,2,3)]:
        a = arange(np.prod(shape))
        # Test each combination of positive and negative strides
        for dirs in range(2**len(shape)):
            dirs_index = [slice(None)]*len(shape)
            for bit in range(len(shape)):
                if ((2**bit)&dirs):
                    dirs_index[bit] = slice(None,None,-1)
            dirs_index = tuple(dirs_index)

            aview = a.reshape(shape)[dirs_index]
            # C-order
            i = newiter(aview, [], [['readonly']])
            assert_equal([x for x in i], a)
            # Fortran-order
            i = newiter(aview.T, [], [['readonly']])
            assert_equal([x for x in i], a)
            # Other order
            if len(shape) > 2:
                i = newiter(aview.swapaxes(0,1), [], [['readonly']])
                assert_equal([x for x in i], a)

def test_iter_c_order():
    # Test forcing C order

    # Test the ordering for 1-D to 5-D shapes
    for shape in [(5,), (3,4), (2,3,4), (2,3,4,3), (2,3,2,2,3)]:
        a = arange(np.prod(shape))
        # Test each combination of positive and negative strides
        for dirs in range(2**len(shape)):
            dirs_index = [slice(None)]*len(shape)
            for bit in range(len(shape)):
                if ((2**bit)&dirs):
                    dirs_index[bit] = slice(None,None,-1)
            dirs_index = tuple(dirs_index)

            aview = a.reshape(shape)[dirs_index]
            # C-order
            i = newiter(aview, order='C')
            assert_equal([x for x in i], aview.ravel(order='C'))
            # Fortran-order
            i = newiter(aview.T, order='C')
            assert_equal([x for x in i], aview.T.ravel(order='C'))
            # Other order
            if len(shape) > 2:
                i = newiter(aview.swapaxes(0,1), order='C')
                assert_equal([x for x in i],
                                    aview.swapaxes(0,1).ravel(order='C'))

def test_iter_f_order():
    # Test forcing F order

    # Test the ordering for 1-D to 5-D shapes
    for shape in [(5,), (3,4), (2,3,4), (2,3,4,3), (2,3,2,2,3)]:
        a = arange(np.prod(shape))
        # Test each combination of positive and negative strides
        for dirs in range(2**len(shape)):
            dirs_index = [slice(None)]*len(shape)
            for bit in range(len(shape)):
                if ((2**bit)&dirs):
                    dirs_index[bit] = slice(None,None,-1)
            dirs_index = tuple(dirs_index)

            aview = a.reshape(shape)[dirs_index]
            # C-order
            i = newiter(aview, order='F')
            assert_equal([x for x in i], aview.ravel(order='F'))
            # Fortran-order
            i = newiter(aview.T, order='F')
            assert_equal([x for x in i], aview.T.ravel(order='F'))
            # Other order
            if len(shape) > 2:
                i = newiter(aview.swapaxes(0,1), order='F')
                assert_equal([x for x in i],
                                    aview.swapaxes(0,1).ravel(order='F'))

def test_iter_c_or_f_order():
    # Test forcing any contiguous (C or F) order

    # Test the ordering for 1-D to 5-D shapes
    for shape in [(5,), (3,4), (2,3,4), (2,3,4,3), (2,3,2,2,3)]:
        a = arange(np.prod(shape))
        # Test each combination of positive and negative strides
        for dirs in range(2**len(shape)):
            dirs_index = [slice(None)]*len(shape)
            for bit in range(len(shape)):
                if ((2**bit)&dirs):
                    dirs_index[bit] = slice(None,None,-1)
            dirs_index = tuple(dirs_index)

            aview = a.reshape(shape)[dirs_index]
            # C-order
            i = newiter(aview, order='A')
            assert_equal([x for x in i], aview.ravel(order='A'))
            # Fortran-order
            i = newiter(aview.T, order='A')
            assert_equal([x for x in i], aview.T.ravel(order='A'))
            # Other order
            if len(shape) > 2:
                i = newiter(aview.swapaxes(0,1), order='A')
                assert_equal([x for x in i],
                                    aview.swapaxes(0,1).ravel(order='A'))

def test_iter_best_order_coords_1d():
    # The coords should be correct with any reordering

    a = arange(4)
    # 1D order
    i = newiter(a,['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(0,),(1,),(2,),(3,)])
    # 1D reversed order
    i = newiter(a[::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(3,),(2,),(1,),(0,)])

def test_iter_best_order_coords_2d():
    # The coords should be correct with any reordering

    a = arange(6)
    # 2D C-order
    i = newiter(a.reshape(2,3),['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)])
    # 2D Fortran-order
    i = newiter(a.reshape(2,3).copy(order='F'),['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(0,0),(1,0),(0,1),(1,1),(0,2),(1,2)])
    # 2D reversed C-order
    i = newiter(a.reshape(2,3)[::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(1,0),(1,1),(1,2),(0,0),(0,1),(0,2)])
    i = newiter(a.reshape(2,3)[:,::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(0,2),(0,1),(0,0),(1,2),(1,1),(1,0)])
    i = newiter(a.reshape(2,3)[::-1,::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(1,2),(1,1),(1,0),(0,2),(0,1),(0,0)])
    # 2D reversed Fortran-order
    i = newiter(a.reshape(2,3).copy(order='F')[::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(1,0),(0,0),(1,1),(0,1),(1,2),(0,2)])
    i = newiter(a.reshape(2,3).copy(order='F')[:,::-1],
                                                   ['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(0,2),(1,2),(0,1),(1,1),(0,0),(1,0)])
    i = newiter(a.reshape(2,3).copy(order='F')[::-1,::-1],
                                                   ['coords'],[['readonly']])
    assert_equal(iter_coords(i), [(1,2),(0,2),(1,1),(0,1),(1,0),(0,0)])

def test_iter_best_order_coords_3d():
    # The coords should be correct with any reordering

    a = arange(12)
    # 3D C-order
    i = newiter(a.reshape(2,3,2),['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(0,0,0),(0,0,1),(0,1,0),(0,1,1),(0,2,0),(0,2,1),
                             (1,0,0),(1,0,1),(1,1,0),(1,1,1),(1,2,0),(1,2,1)])
    # 3D Fortran-order
    i = newiter(a.reshape(2,3,2).copy(order='F'),['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(0,0,0),(1,0,0),(0,1,0),(1,1,0),(0,2,0),(1,2,0),
                             (0,0,1),(1,0,1),(0,1,1),(1,1,1),(0,2,1),(1,2,1)])
    # 3D reversed C-order
    i = newiter(a.reshape(2,3,2)[::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(1,0,0),(1,0,1),(1,1,0),(1,1,1),(1,2,0),(1,2,1),
                             (0,0,0),(0,0,1),(0,1,0),(0,1,1),(0,2,0),(0,2,1)])
    i = newiter(a.reshape(2,3,2)[:,::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(0,2,0),(0,2,1),(0,1,0),(0,1,1),(0,0,0),(0,0,1),
                             (1,2,0),(1,2,1),(1,1,0),(1,1,1),(1,0,0),(1,0,1)])
    i = newiter(a.reshape(2,3,2)[:,:,::-1],['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(0,0,1),(0,0,0),(0,1,1),(0,1,0),(0,2,1),(0,2,0),
                             (1,0,1),(1,0,0),(1,1,1),(1,1,0),(1,2,1),(1,2,0)])
    # 3D reversed Fortran-order
    i = newiter(a.reshape(2,3,2).copy(order='F')[::-1],
                                                    ['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(1,0,0),(0,0,0),(1,1,0),(0,1,0),(1,2,0),(0,2,0),
                             (1,0,1),(0,0,1),(1,1,1),(0,1,1),(1,2,1),(0,2,1)])
    i = newiter(a.reshape(2,3,2).copy(order='F')[:,::-1],
                                                    ['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(0,2,0),(1,2,0),(0,1,0),(1,1,0),(0,0,0),(1,0,0),
                             (0,2,1),(1,2,1),(0,1,1),(1,1,1),(0,0,1),(1,0,1)])
    i = newiter(a.reshape(2,3,2).copy(order='F')[:,:,::-1],
                                                    ['coords'],[['readonly']])
    assert_equal(iter_coords(i),
                            [(0,0,1),(1,0,1),(0,1,1),(1,1,1),(0,2,1),(1,2,1),
                             (0,0,0),(1,0,0),(0,1,0),(1,1,0),(0,2,0),(1,2,0)])

def test_iter_best_order_c_index_1d():
    # The C index should be correct with any reordering

    a = arange(4)
    # 1D order
    i = newiter(a,['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [0,1,2,3])
    # 1D reversed order
    i = newiter(a[::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [3,2,1,0])

def test_iter_best_order_c_index_2d():
    # The C index should be correct with any reordering

    a = arange(6)
    # 2D C-order
    i = newiter(a.reshape(2,3),['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [0,1,2,3,4,5])
    # 2D Fortran-order
    i = newiter(a.reshape(2,3).copy(order='F'),
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [0,3,1,4,2,5])
    # 2D reversed C-order
    i = newiter(a.reshape(2,3)[::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [3,4,5,0,1,2])
    i = newiter(a.reshape(2,3)[:,::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [2,1,0,5,4,3])
    i = newiter(a.reshape(2,3)[::-1,::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [5,4,3,2,1,0])
    # 2D reversed Fortran-order
    i = newiter(a.reshape(2,3).copy(order='F')[::-1],
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [3,0,4,1,5,2])
    i = newiter(a.reshape(2,3).copy(order='F')[:,::-1],
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [2,5,1,4,0,3])
    i = newiter(a.reshape(2,3).copy(order='F')[::-1,::-1],
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i), [5,2,4,1,3,0])

def test_iter_best_order_c_index_3d():
    # The C index should be correct with any reordering

    a = arange(12)
    # 3D C-order
    i = newiter(a.reshape(2,3,2),['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [0,1,2,3,4,5,6,7,8,9,10,11])
    # 3D Fortran-order
    i = newiter(a.reshape(2,3,2).copy(order='F'),
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [0,6,2,8,4,10,1,7,3,9,5,11])
    # 3D reversed C-order
    i = newiter(a.reshape(2,3,2)[::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [6,7,8,9,10,11,0,1,2,3,4,5])
    i = newiter(a.reshape(2,3,2)[:,::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [4,5,2,3,0,1,10,11,8,9,6,7])
    i = newiter(a.reshape(2,3,2)[:,:,::-1],['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [1,0,3,2,5,4,7,6,9,8,11,10])
    # 3D reversed Fortran-order
    i = newiter(a.reshape(2,3,2).copy(order='F')[::-1],
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [6,0,8,2,10,4,7,1,9,3,11,5])
    i = newiter(a.reshape(2,3,2).copy(order='F')[:,::-1],
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [4,10,2,8,0,6,5,11,3,9,1,7])
    i = newiter(a.reshape(2,3,2).copy(order='F')[:,:,::-1],
                                    ['c_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [1,7,3,9,5,11,0,6,2,8,4,10])

def test_iter_best_order_f_index_1d():
    # The Fortran index should be correct with any reordering

    a = arange(4)
    # 1D order
    i = newiter(a,['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [0,1,2,3])
    # 1D reversed order
    i = newiter(a[::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [3,2,1,0])

def test_iter_best_order_f_index_2d():
    # The Fortran index should be correct with any reordering

    a = arange(6)
    # 2D C-order
    i = newiter(a.reshape(2,3),['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [0,2,4,1,3,5])
    # 2D Fortran-order
    i = newiter(a.reshape(2,3).copy(order='F'),
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [0,1,2,3,4,5])
    # 2D reversed C-order
    i = newiter(a.reshape(2,3)[::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [1,3,5,0,2,4])
    i = newiter(a.reshape(2,3)[:,::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [4,2,0,5,3,1])
    i = newiter(a.reshape(2,3)[::-1,::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [5,3,1,4,2,0])
    # 2D reversed Fortran-order
    i = newiter(a.reshape(2,3).copy(order='F')[::-1],
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [1,0,3,2,5,4])
    i = newiter(a.reshape(2,3).copy(order='F')[:,::-1],
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [4,5,2,3,0,1])
    i = newiter(a.reshape(2,3).copy(order='F')[::-1,::-1],
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i), [5,4,3,2,1,0])

def test_iter_best_order_f_index_3d():
    # The Fortran index should be correct with any reordering

    a = arange(12)
    # 3D C-order
    i = newiter(a.reshape(2,3,2),['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [0,6,2,8,4,10,1,7,3,9,5,11])
    # 3D Fortran-order
    i = newiter(a.reshape(2,3,2).copy(order='F'),
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [0,1,2,3,4,5,6,7,8,9,10,11])
    # 3D reversed C-order
    i = newiter(a.reshape(2,3,2)[::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [1,7,3,9,5,11,0,6,2,8,4,10])
    i = newiter(a.reshape(2,3,2)[:,::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [4,10,2,8,0,6,5,11,3,9,1,7])
    i = newiter(a.reshape(2,3,2)[:,:,::-1],['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [6,0,8,2,10,4,7,1,9,3,11,5])
    # 3D reversed Fortran-order
    i = newiter(a.reshape(2,3,2).copy(order='F')[::-1],
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [1,0,3,2,5,4,7,6,9,8,11,10])
    i = newiter(a.reshape(2,3,2).copy(order='F')[:,::-1],
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [4,5,2,3,0,1,10,11,8,9,6,7])
    i = newiter(a.reshape(2,3,2).copy(order='F')[:,:,::-1],
                                    ['f_index'],[['readonly']])
    assert_equal(iter_indices(i),
                            [6,7,8,9,10,11,0,1,2,3,4,5])

def test_iter_no_inner_full_coalesce():
    # Check no_inner iterators which coalesce into a single inner loop

    for shape in [(5,), (3,4), (2,3,4), (2,3,4,3), (2,3,2,2,3)]:
        size = np.prod(shape)
        a = arange(size)
        # Test each combination of forward and backwards indexing
        for dirs in range(2**len(shape)):
            dirs_index = [slice(None)]*len(shape)
            for bit in range(len(shape)):
                if ((2**bit)&dirs):
                    dirs_index[bit] = slice(None,None,-1)
            dirs_index = tuple(dirs_index)

            aview = a.reshape(shape)[dirs_index]
            # C-order
            i = newiter(aview, ['no_inner_iteration'], [['readonly']])
            assert_equal(i.ndim, 1)
            assert_equal(i[0].shape, (size,))
            # Fortran-order
            i = newiter(aview.T, ['no_inner_iteration'], [['readonly']])
            assert_equal(i.ndim, 1)
            assert_equal(i[0].shape, (size,))
            # Other order
            if len(shape) > 2:
                i = newiter(aview.swapaxes(0,1),
                                    ['no_inner_iteration'], [['readonly']])
                assert_equal(i.ndim, 1)
                assert_equal(i[0].shape, (size,))

def test_iter_no_inner_dim_coalescing():
    # Check no_inner iterators whose dimensions may not coalesce completely

    # Skipping the last element in a dimension prevents coalescing
    # with the next-bigger dimension
    a = arange(24).reshape(2,3,4)[:,:,:-1]
    i = newiter(a, ['no_inner_iteration'], [['readonly']])
    assert_equal(i.ndim, 2)
    assert_equal(i[0].shape, (3,))
    a = arange(24).reshape(2,3,4)[:,:-1,:]
    i = newiter(a, ['no_inner_iteration'], [['readonly']])
    assert_equal(i.ndim, 2)
    assert_equal(i[0].shape, (8,))
    a = arange(24).reshape(2,3,4)[:-1,:,:]
    i = newiter(a, ['no_inner_iteration'], [['readonly']])
    assert_equal(i.ndim, 1)
    assert_equal(i[0].shape, (12,))
    
    # Even with lots of 1-sized dimensions, should still coalesce
    a = arange(24).reshape(1,1,2,1,1,3,1,1,4,1,1)
    i = newiter(a, ['no_inner_iteration'], [['readonly']])
    assert_equal(i.ndim, 1)
    assert_equal(i[0].shape, (24,))

def test_iter_dim_coalescing():
    # Check that the correct number of dimensions are coalesced

    # Tracking coordinates disables coalescing
    a = arange(24).reshape(2,3,4)
    i = newiter(a, ['coords'], [['readonly']])
    assert_equal(i.ndim, 3)

    # A tracked index can allow coalescing if it's compatible with the array
    a3d = arange(24).reshape(2,3,4)
    i = newiter(a3d, ['c_index'], [['readonly']])
    assert_equal(i.ndim, 1)
    i = newiter(a3d.swapaxes(0,1), ['c_index'], [['readonly']])
    assert_equal(i.ndim, 3)
    i = newiter(a3d.T, ['c_index'], [['readonly']])
    assert_equal(i.ndim, 3)
    i = newiter(a3d.T, ['f_index'], [['readonly']])
    assert_equal(i.ndim, 1)
    i = newiter(a3d.T.swapaxes(0,1), ['f_index'], [['readonly']])
    assert_equal(i.ndim, 3)

    # When C or F order is forced, coalescing may still occur
    a3d = arange(24).reshape(2,3,4)
    i = newiter(a3d, order='C')
    assert_equal(i.ndim, 1)
    i = newiter(a3d.T, order='C')
    assert_equal(i.ndim, 3)
    i = newiter(a3d, order='F')
    assert_equal(i.ndim, 3)
    i = newiter(a3d.T, order='F')
    assert_equal(i.ndim, 1)
    i = newiter(a3d, order='A')
    assert_equal(i.ndim, 1)
    i = newiter(a3d.T, order='A')
    assert_equal(i.ndim, 1)

def test_iter_broadcasting():
    # Standard NumPy broadcasting rules

    # 1D with scalar
    i = newiter([arange(6), np.int32(2)], ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 6)
    assert_equal(i.shape, (6,))

    # 2D with scalar
    i = newiter([arange(6).reshape(2,3), np.int32(2)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 6)
    assert_equal(i.shape, (2,3))
    # 2D with 1D
    i = newiter([arange(6).reshape(2,3), arange(3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 6)
    assert_equal(i.shape, (2,3))
    i = newiter([arange(2).reshape(2,1), arange(3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 6)
    assert_equal(i.shape, (2,3))
    # 2D with 2D
    i = newiter([arange(2).reshape(2,1), arange(3).reshape(1,3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 6)
    assert_equal(i.shape, (2,3))

    # 3D with scalar
    i = newiter([np.int32(2), arange(24).reshape(4,2,3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    # 3D with 1D
    i = newiter([arange(3), arange(24).reshape(4,2,3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    i = newiter([arange(3), arange(8).reshape(4,2,1)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    # 3D with 2D
    i = newiter([arange(6).reshape(2,3), arange(24).reshape(4,2,3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    i = newiter([arange(2).reshape(2,1), arange(24).reshape(4,2,3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    i = newiter([arange(3).reshape(1,3), arange(8).reshape(4,2,1)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    # 3D with 3D
    i = newiter([arange(2).reshape(1,2,1), arange(3).reshape(1,1,3),
                        arange(4).reshape(4,1,1)],
                        ['coords'], [['readonly']]*3)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    i = newiter([arange(6).reshape(1,2,3), arange(4).reshape(4,1,1)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))
    i = newiter([arange(24).reshape(4,2,3), arange(12).reshape(4,1,3)],
                        ['coords'], [['readonly']]*2)
    assert_equal(i.itersize, 24)
    assert_equal(i.shape, (4,2,3))

def test_iter_broadcasting_errors():
    # Check that errors are thrown for bad broadcasting shapes

    # 1D with 1D
    assert_raises(ValueError, newiter, [arange(2), arange(3)],
                    [], [['readonly']]*2)
    # 2D with 1D
    assert_raises(ValueError, newiter,
                    [arange(6).reshape(2,3), arange(2)],
                    [], [['readonly']]*2)
    # 2D with 2D
    assert_raises(ValueError, newiter,
                    [arange(6).reshape(2,3), arange(9).reshape(3,3)],
                    [], [['readonly']]*2)
    assert_raises(ValueError, newiter,
                    [arange(6).reshape(2,3), arange(4).reshape(2,2)],
                    [], [['readonly']]*2)
    # 3D with 3D
    assert_raises(ValueError, newiter,
                    [arange(36).reshape(3,3,4), arange(24).reshape(2,3,4)],
                    [], [['readonly']]*2)
    assert_raises(ValueError, newiter,
                    [arange(8).reshape(2,4,1), arange(24).reshape(2,3,4)],
                    [], [['readonly']]*2)


def test_iter_flags_errors():
    # Check that bad combinations of flags produce errors

    a = arange(6)

    # Not enough operands
    assert_raises(ValueError, newiter, [], [], [])
    # Too many operands
    assert_raises(ValueError, newiter, [a]*100, [], [['readonly']]*100)
    # op_flags must match ops
    assert_raises(ValueError, newiter, [a]*3, [], [['readonly']]*2)
    # Cannot track both a C and an F index
    assert_raises(ValueError, newiter, a,
                ['c_index','f_index'], [['readonly']])
    # Inner iteration and coords/indices are incompatible
    assert_raises(ValueError, newiter, a,
                ['no_inner_iteration','coords'], [['readonly']])
    assert_raises(ValueError, newiter, a,
                ['no_inner_iteration','c_index'], [['readonly']])
    assert_raises(ValueError, newiter, a,
                ['no_inner_iteration','f_index'], [['readonly']])
    # Must specify exactly one of readwrite/readonly/writeonly per operand
    assert_raises(ValueError, newiter, a, [], [[]])
    assert_raises(ValueError, newiter, a, [], [['readonly','writeonly']])
    assert_raises(ValueError, newiter, a, [], [['readonly','readwrite']])
    assert_raises(ValueError, newiter, a, [], [['writeonly','readwrite']])
    assert_raises(ValueError, newiter, a,
                [], [['readonly','writeonly','readwrite']])
    # Python scalars are always readonly
    assert_raises(TypeError, newiter, 1.5, [], [['writeonly']])
    assert_raises(TypeError, newiter, 1.5, [], [['readwrite']])
    # Array scalars are always readonly
    assert_raises(TypeError, newiter, np.int32(1), [], [['writeonly']])
    assert_raises(TypeError, newiter, np.int32(1), [], [['readwrite']])
    # Check readonly array
    a.flags.writeable = False
    assert_raises(ValueError, newiter, a, [], [['writeonly']])
    assert_raises(ValueError, newiter, a, [], [['readwrite']])
    a.flags.writeable = True
    # Coords and shape available only with the coords flag
    i = newiter(arange(6), [], [['readonly']])
    assert_raises(ValueError, lambda i:i.coords, i)
    assert_raises(ValueError, lambda i:i.shape, i)
    # Index available only with an index flag
    assert_raises(ValueError, lambda i:i.index, i)
    # GotoCoords and GotoIndex incompatible with buffering or no_inner
    def assign_coords(i):
        i.coords = (0,)
    def assign_index(i):
        i.index = 0
    def assign_iterindex(i):
        i.iterindex = 0;
    def assign_iterrange(i):
        i.iterrange = (0,1);
    i = newiter(arange(6), ['no_inner_iteration'])
    assert_raises(ValueError, assign_coords, i)
    assert_raises(ValueError, assign_index, i)
    assert_raises(ValueError, assign_iterindex, i)
    assert_raises(ValueError, assign_iterrange, i)
    i = newiter(arange(6), ['buffered'])
    assert_raises(ValueError, assign_coords, i)
    assert_raises(ValueError, assign_index, i)
    assert_raises(ValueError, assign_iterrange, i)
    # Can't iterate if size is zero
    assert_raises(ValueError, newiter, np.array([]))

def test_iter_nbo_align():
    # Check that byte order and alignment changes work

    # Byte order change by requesting a specific dtype
    a = np.arange(6, dtype='f4')
    au = a.byteswap().newbyteorder()
    assert_(a.dtype.byteorder != au.dtype.byteorder)
    i = newiter(au, [], [['readwrite','updateifcopy']],
                        casting='equiv',
                        op_dtypes=[np.dtype('f4')])
    assert_equal(i.dtypes[0].byteorder, a.dtype.byteorder)
    assert_equal(i.operands[0].dtype.byteorder, a.dtype.byteorder)
    assert_equal(i.operands[0], a)
    i.operands[0][:] = 2
    i = None
    assert_equal(au, [2]*6)

    # Byte order change by requesting NBO_ALIGNED
    a = np.arange(6, dtype='f4')
    au = a.byteswap().newbyteorder()
    assert_(a.dtype.byteorder != au.dtype.byteorder)
    i = newiter(au, [], [['readwrite','updateifcopy','nbo_aligned']], casting='equiv')
    assert_equal(i.dtypes[0].byteorder, a.dtype.byteorder)
    assert_equal(i.operands[0].dtype.byteorder, a.dtype.byteorder)
    assert_equal(i.operands[0], a)
    i.operands[0][:] = 2
    i = None
    assert_equal(au, [2]*6)

    # Unaligned input
    a = np.zeros((6*4+1,), dtype='i1')[1:]
    a.dtype = 'f4'
    a[:] = np.arange(6, dtype='f4')
    assert_(not a.flags.aligned)
    # Without 'nbo_aligned', shouldn't copy
    i = newiter(a, [], [['readonly']])
    assert_(not i.operands[0].flags.aligned)
    assert_equal(i.operands[0], a);
    # With 'nbo_aligned', should make a copy
    i = newiter(a, [], [['readwrite','updateifcopy','nbo_aligned']])
    assert_(i.operands[0].flags.aligned)
    assert_equal(i.operands[0], a);
    i.operands[0][:] = 3
    i = None
    assert_equal(a, [3]*6)

def test_iter_array_cast():
    # Check that arrays are cast as requested

    # No cast 'f4' -> 'f4'
    a = np.arange(6, dtype='f4').reshape(2,3)
    i = newiter(a, [], [['readwrite']], op_dtypes=[np.dtype('f4')])
    assert_equal(i.operands[0], a)
    assert_equal(i.operands[0].dtype, np.dtype('f4'))

    # Byte-order cast '<f4' -> '>f4'
    a = np.arange(6, dtype='<f4').reshape(2,3)
    i = newiter(a, [], [['readwrite','updateifcopy']],
            casting='equiv',
            op_dtypes=[np.dtype('>f4')])
    assert_equal(i.operands[0], a)
    assert_equal(i.operands[0].dtype, np.dtype('>f4'))

    # Safe case 'f4' -> 'f8'
    a = np.arange(24, dtype='f4').reshape(2,3,4).swapaxes(1,2)
    i = newiter(a, [], [['readonly','copy']],
            casting='safe',
            op_dtypes=[np.dtype('f8')])
    assert_equal(i.operands[0], a)
    assert_equal(i.operands[0].dtype, np.dtype('f8'))
    # The memory layout of the temporary should match a (a is (48,4,16))
    assert_equal(i.operands[0].strides, (96,8,32))
    a = a[::-1,:,::-1]
    i = newiter(a, [], [['readonly','copy']],
            casting='safe',
            op_dtypes=[np.dtype('f8')])
    assert_equal(i.operands[0], a)
    assert_equal(i.operands[0].dtype, np.dtype('f8'))
    assert_equal(i.operands[0].strides, (-96,8,-32))

    # Same-kind cast 'f8' -> 'f4' -> 'f8'
    a = np.arange(24, dtype='f8').reshape(2,3,4).T
    i = newiter(a, [],
            [['readwrite','updateifcopy']],
            casting='same_kind',
            op_dtypes=[np.dtype('f4')])
    assert_equal(i.operands[0], a)
    assert_equal(i.operands[0].dtype, np.dtype('f4'))
    assert_equal(i.operands[0].strides, (4, 16, 48))
    # Check that UPDATEIFCOPY is activated
    i.operands[0][2,1,1] = -12.5
    assert_(a[2,1,1] != -12.5)
    i = None
    assert_equal(a[2,1,1], -12.5)

    # Unsafe cast 'f4' -> 'i4'
    a = np.arange(6, dtype='i4')[::-2]
    i = newiter(a, [],
            [['writeonly','updateifcopy']],
            casting='unsafe',
            op_dtypes=[np.dtype('f4')])
    assert_equal(i.operands[0].dtype, np.dtype('f4'))
    assert_equal(i.operands[0].strides, (-4,))
    i.operands[0][:] = 1
    i = None
    assert_equal(a, [1,1,1])

def test_iter_array_cast_errors():
    # Check that invalid casts are caught

    # Need to enable copying for casts to occur
    assert_raises(TypeError, newiter, arange(2,dtype='f4'), [],
                [['readonly']], op_dtypes=[np.dtype('f8')])
    # Also need to allow casting for casts to occur
    assert_raises(TypeError, newiter, arange(2,dtype='f4'), [],
                [['readonly','copy']], casting='no',
                op_dtypes=[np.dtype('f8')])
    assert_raises(TypeError, newiter, arange(2,dtype='f4'), [],
                [['readonly','copy']], casting='equiv',
                op_dtypes=[np.dtype('f8')])
    assert_raises(TypeError, newiter, arange(2,dtype='f8'), [],
                [['writeonly','updateifcopy']],
                casting='no',
                op_dtypes=[np.dtype('f4')])
    assert_raises(TypeError, newiter, arange(2,dtype='f8'), [],
                [['writeonly','updateifcopy']],
                casting='equiv',
                op_dtypes=[np.dtype('f4')])
    # '<f4' -> '>f4' should not work with casting='no'
    assert_raises(TypeError, newiter, arange(2,dtype='<f4'), [],
                [['readonly','copy']], casting='no',
                op_dtypes=[np.dtype('>f4')])
    # 'f4' -> 'f8' is a safe cast, but 'f8' -> 'f4' isn't
    assert_raises(TypeError, newiter, arange(2,dtype='f4'), [],
                [['readwrite','updateifcopy']],
                casting='safe',
                op_dtypes=[np.dtype('f8')])
    assert_raises(TypeError, newiter, arange(2,dtype='f8'), [],
                [['readwrite','updateifcopy']],
                casting='safe',
                op_dtypes=[np.dtype('f4')])
    # 'f4' -> 'i4' is neither a safe nor a same-kind cast
    assert_raises(TypeError, newiter, arange(2,dtype='f4'), [],
                [['readonly','copy']],
                casting='same_kind',
                op_dtypes=[np.dtype('i4')])
    assert_raises(TypeError, newiter, arange(2,dtype='i4'), [],
                [['writeonly','updateifcopy']],
                casting='same_kind',
                op_dtypes=[np.dtype('f4')])

def test_iter_scalar_cast():
    # Check that scalars are cast as requested

    # No cast 'f4' -> 'f4'
    i = newiter(np.float32(2.5), [], [['readonly']],
                    op_dtypes=[np.dtype('f4')])
    assert_equal(i.dtypes[0], np.dtype('f4'))
    assert_equal(i.value.dtype, np.dtype('f4'))
    assert_equal(i.value, 2.5)
    # Safe cast 'f4' -> 'f8'
    i = newiter(np.float32(2.5), [],
                    [['readonly','copy']],
                    casting='safe',
                    op_dtypes=[np.dtype('f8')])
    assert_equal(i.dtypes[0], np.dtype('f8'))
    assert_equal(i.value.dtype, np.dtype('f8'))
    assert_equal(i.value, 2.5)
    # Same-kind cast 'f8' -> 'f4'
    i = newiter(np.float64(2.5), [],
                    [['readonly','copy']],
                    casting='same_kind',
                    op_dtypes=[np.dtype('f4')])
    assert_equal(i.dtypes[0], np.dtype('f4'))
    assert_equal(i.value.dtype, np.dtype('f4'))
    assert_equal(i.value, 2.5)
    # Unsafe cast 'f8' -> 'i4'
    i = newiter(np.float64(3.0), [],
                    [['readonly','copy']],
                    casting='unsafe',
                    op_dtypes=[np.dtype('i4')])
    assert_equal(i.dtypes[0], np.dtype('i4'))
    assert_equal(i.value.dtype, np.dtype('i4'))
    assert_equal(i.value, 3)

def test_iter_scalar_cast_errors():
    # Check that invalid casts are caught

    # Need to allow casting for casts to occur
    assert_raises(TypeError, newiter, np.float32(2), [],
                [['readonly']], op_dtypes=[np.dtype('f8')])
    assert_raises(TypeError, newiter, 2.5, [],
                [['readonly']], op_dtypes=[np.dtype('f4')])
    # 'f8' -> 'f4' isn't a safe cast
    assert_raises(TypeError, newiter, np.float64(2), [],
                [['readonly']],
                casting='safe',
                op_dtypes=[np.dtype('f4')])
    # 'f4' -> 'i4' is neither a safe nor a same-kind cast
    assert_raises(TypeError, newiter, np.float32(2), [],
                [['readonly']],
                casting='same_kind',
                op_dtypes=[np.dtype('i4')])

def test_iter_common_dtype():
    # Check that the iterator finds a common data type correctly

    i = newiter([array([3],dtype='f4'),array([0],dtype='f8')],
                    ['common_dtype'],
                    [['readonly','copy']]*2,
                    casting='safe')
    assert_equal(i.dtypes[0], np.dtype('f8'));
    assert_equal(i.dtypes[1], np.dtype('f8'));
    i = newiter([array([3],dtype='i4'),array([0],dtype='f4')],
                    ['common_dtype'],
                    [['readonly','copy']]*2,
                    casting='safe')
    assert_equal(i.dtypes[0], np.dtype('f8'));
    assert_equal(i.dtypes[1], np.dtype('f8'));
    i = newiter([array([3],dtype='f4'),array(0,dtype='f8')],
                    ['common_dtype'],
                    [['readonly','copy']]*2,
                    casting='same_kind')
    assert_equal(i.dtypes[0], np.dtype('f4'));
    assert_equal(i.dtypes[1], np.dtype('f4'));
    # TODO
    # This case is weird - the scalar/array combination produces a cast
    # classified as unsafe.  I think this NumPy rule needs to be revisited.
    # For example, when the scalar is writeable, a negative value could
    # be written during iteration, invalidating the scalar kind assumed!
    i = newiter([array([3],dtype='u4'),array(0,dtype='i4')],
                    ['common_dtype'],
                    [['readonly','copy']]*2,
                    casting='unsafe')
    assert_equal(i.dtypes[0], np.dtype('u4'));
    assert_equal(i.dtypes[1], np.dtype('u4'));
    i = newiter([array([3],dtype='u4'),array(-12,dtype='i4')],
                    ['common_dtype'],
                    [['readonly','copy']]*2,
                    casting='safe')
    assert_equal(i.dtypes[0], np.dtype('i8'));
    assert_equal(i.dtypes[1], np.dtype('i8'));
    i = newiter([array([3],dtype='u4'),array(-12,dtype='i4'),
                 array([2j],dtype='c8'),array([9],dtype='f8')],
                    ['common_dtype'],
                    [['readonly','copy']]*4,
                    casting='safe')
    assert_equal(i.dtypes[0], np.dtype('c16'));
    assert_equal(i.dtypes[1], np.dtype('c16'));
    assert_equal(i.dtypes[2], np.dtype('c16'));
    assert_equal(i.dtypes[3], np.dtype('c16'));
    assert_equal(i.value, (3,-12,2j,9))

    # When allocating outputs, other outputs aren't factored in
    i = newiter([array([3],dtype='i4'),None,array([2j],dtype='c16')], [],
                    [['readonly','copy'],
                     ['writeonly','allocate'],
                     ['writeonly']],
                    casting='safe')
    assert_equal(i.dtypes[0], np.dtype('i4'));
    assert_equal(i.dtypes[1], np.dtype('i4'));
    assert_equal(i.dtypes[2], np.dtype('c16'));
    # But, if common data types are requested, they are
    i = newiter([array([3],dtype='i4'),None,array([2j],dtype='c16')],
                    ['common_dtype'],
                    [['readonly','copy'],
                     ['writeonly','allocate'],
                     ['writeonly']],
                    casting='safe')
    assert_equal(i.dtypes[0], np.dtype('c16'));
    assert_equal(i.dtypes[1], np.dtype('c16'));
    assert_equal(i.dtypes[2], np.dtype('c16'));

def test_iter_op_axes():
    # Check that custom axes work

    # Reverse the axes
    a = arange(6).reshape(2,3)
    i = newiter([a,a.T], [], [['readonly']]*2, op_axes=[[0,1],[1,0]])
    assert_(all([x==y for (x,y) in i]))
    a = arange(24).reshape(2,3,4)
    i = newiter([a.T,a], [], [['readonly']]*2, op_axes=[[2,1,0],None])
    assert_(all([x==y for (x,y) in i]))

    # Broadcast 1D to any dimension
    a = arange(1,31).reshape(2,3,5)
    b = arange(1,3)
    i = newiter([a,b], [], [['readonly']]*2, op_axes=[None,[0,-1,-1]])
    assert_equal([x*y for (x,y) in i], (a*b.reshape(2,1,1)).ravel())
    b = arange(1,4)
    i = newiter([a,b], [], [['readonly']]*2, op_axes=[None,[-1,0,-1]])
    assert_equal([x*y for (x,y) in i], (a*b.reshape(1,3,1)).ravel())
    b = arange(1,6)
    i = newiter([a,b], [], [['readonly']]*2,
                            op_axes=[None,[np.newaxis,np.newaxis,0]])
    assert_equal([x*y for (x,y) in i], (a*b.reshape(1,1,5)).ravel())

    # Inner product-style broadcasting
    a = arange(24).reshape(2,3,4)
    b = arange(40).reshape(5,2,4)
    i = newiter([a,b], ['coords'], [['readonly']]*2,
                            op_axes=[[0,1,-1,-1],[-1,-1,0,1]])
    assert_equal(i.shape, (2,3,5,2))

    # Matrix product-style broadcasting
    a = arange(12).reshape(3,4)
    b = arange(20).reshape(4,5)
    i = newiter([a,b], ['coords'], [['readonly']]*2,
                            op_axes=[[0,-1],[-1,1]])
    assert_equal(i.shape, (3,5))

def test_iter_op_axes_errors():
    # Check that custom axes throws errors for bad inputs

    # Wrong number of items in op_axes
    a = arange(6).reshape(2,3)
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[0],[1],[0]])
    # Out of bounds items in op_axes
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[2,1],[0,1]])
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[0,1],[2,-1]])
    # Duplicate items in op_axes
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[0,0],[0,1]])
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[0,1],[1,1]])

    # Different sized arrays in op_axes
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[0,1],[0,1,0]])

    # Non-broadcastable dimensions in the result
    assert_raises(ValueError, newiter, [a,a], [], [['readonly']]*2,
                                    op_axes=[[0,1],[1,0]])

def test_iter_allocate_output_simple():
    # Check that the iterator will properly allocate outputs

    # Simple case
    a = arange(6)
    i = newiter([a,None], [], [['readonly'],['writeonly','allocate']],
                        op_dtypes=[None,np.dtype('f4')])
    assert_equal(i.operands[1].shape, a.shape)
    assert_equal(i.operands[1].dtype, np.dtype('f4'))

def test_iter_allocate_output_itorder():
    # The allocated output should match the iteration order

    # C-order input, best iteration order
    a = arange(6, dtype='i4').reshape(2,3)
    i = newiter([a,None], [], [['readonly'],['writeonly','allocate']],
                        op_dtypes=[None,np.dtype('f4')])
    assert_equal(i.operands[1].shape, a.shape)
    assert_equal(i.operands[1].strides, a.strides)
    assert_equal(i.operands[1].dtype, np.dtype('f4'))
    # F-order input, best iteration order
    a = arange(24, dtype='i4').reshape(2,3,4).T
    i = newiter([a,None], [], [['readonly'],['writeonly','allocate']],
                        op_dtypes=[None,np.dtype('f4')])
    assert_equal(i.operands[1].shape, a.shape)
    assert_equal(i.operands[1].strides, a.strides)
    assert_equal(i.operands[1].dtype, np.dtype('f4'))
    # Non-contiguous input, C iteration order
    a = arange(24, dtype='i4').reshape(2,3,4).swapaxes(0,1)
    i = newiter([a,None], [],
                        [['readonly'],['writeonly','allocate']],
                        order='C',
                        op_dtypes=[None,np.dtype('f4')])
    assert_equal(i.operands[1].shape, a.shape)
    assert_equal(i.operands[1].strides, (32,16,4))
    assert_equal(i.operands[1].dtype, np.dtype('f4'))

def test_iter_allocate_output_opaxes():
    # Specifing op_axes should work

    a = arange(24, dtype='i4').reshape(2,3,4)
    i = newiter([None,a], [], [['writeonly','allocate'],['readonly']],
                        op_dtypes=[np.dtype('u4'),None],
                        op_axes=[[1,2,0],None]);
    assert_equal(i.operands[0].shape, (4,2,3))
    assert_equal(i.operands[0].strides, (4,48,16))
    assert_equal(i.operands[0].dtype, np.dtype('u4'))

def test_iter_allocate_output_types_promotion():
    # Check type promotion of automatic outputs

    i = newiter([array([3],dtype='f4'),array([0],dtype='f8'),None], [],
                    [['readonly']]*2+[['writeonly','allocate']])
    assert_equal(i.dtypes[2], np.dtype('f8'));
    i = newiter([array([3],dtype='i4'),array([0],dtype='f4'),None], [],
                    [['readonly']]*2+[['writeonly','allocate']])
    assert_equal(i.dtypes[2], np.dtype('f8'));
    i = newiter([array([3],dtype='f4'),array(0,dtype='f8'),None], [],
                    [['readonly']]*2+[['writeonly','allocate']])
    assert_equal(i.dtypes[2], np.dtype('f4'));
    i = newiter([array([3],dtype='u4'),array(0,dtype='i4'),None], [],
                    [['readonly']]*2+[['writeonly','allocate']])
    assert_equal(i.dtypes[2], np.dtype('u4'));
    i = newiter([array([3],dtype='u4'),array(-12,dtype='i4'),None], [],
                    [['readonly']]*2+[['writeonly','allocate']])
    assert_equal(i.dtypes[2], np.dtype('i8'));

def test_iter_allocate_output_types_byte_order():
    # Verify the rules for byte order changes

    # When there's just one input, the output type exactly matches
    a = array([3],dtype='u4').newbyteorder()
    i = newiter([a,None], [],
                    [['readonly'],['writeonly','allocate']])
    assert_equal(i.dtypes[0], i.dtypes[1]);
    # With two or more inputs, the output type is in native byte order
    i = newiter([a,a,None], [],
                    [['readonly'],['readonly'],['writeonly','allocate']])
    assert_(i.dtypes[0] != i.dtypes[2]);
    assert_equal(i.dtypes[0].newbyteorder('='), i.dtypes[2])

def test_iter_allocate_output_types_scalar():
    # If the inputs are all scalars, the output should be a scalar

    i = newiter([None,1,2.3,np.float32(12),np.complex128(3)],[],
                [['writeonly','allocate']] + [['readonly']]*4)
    assert_equal(i.operands[0].dtype, np.dtype('complex128'))
    assert_equal(i.operands[0].ndim, 0)

def test_iter_allocate_output_subtype():
    # Make sure that the subtype with priority wins

    # matrix vs ndarray
    a = np.matrix([[1,2], [3,4]])
    b = np.arange(4).reshape(2,2).T
    i = newiter([a,b,None], [],
                    [['readonly'],['readonly'],['writeonly','allocate']])
    assert_equal(type(a), type(i.operands[2]))
    assert_(type(b) != type(i.operands[2]))
    assert_equal(i.operands[2].shape, (2,2))

    # matrix always wants things to be 2D
    b = np.arange(4).reshape(1,2,2)
    assert_raises(RuntimeError, newiter, [a,b,None], [],
                    [['readonly'],['readonly'],['writeonly','allocate']])
    # but if subtypes are disabled, the result can still work
    i = newiter([a,b,None], [],
            [['readonly'],['readonly'],['writeonly','allocate','no_subtype']])
    assert_equal(type(b), type(i.operands[2]))
    assert_(type(a) != type(i.operands[2]))
    assert_equal(i.operands[2].shape, (1,2,2))

def test_iter_allocate_output_errors():
    # Check that the iterator will throw errors for bad output allocations

    # Need an input if no output data type is specified
    a = arange(6)
    assert_raises(TypeError, newiter, [a,None], [],
                        [['writeonly'],['writeonly','allocate']])
    # Must specify at least one input
    assert_raises(ValueError, newiter, [None,None], [],
                        [['writeonly','allocate'],
                         ['writeonly','allocate']],
                        op_dtypes=[np.dtype('f4'),np.dtype('f4')])
    # If using op_axes, must specify all the axes
    a = arange(24, dtype='i4').reshape(2,3,4)
    assert_raises(ValueError, newiter, [a,None], [],
                        [['readonly'],['writeonly','allocate']],
                        op_dtypes=[None,np.dtype('f4')],
                        op_axes=[None,[0,np.newaxis,1]])
    # If using op_axes, the axes must be within bounds
    assert_raises(ValueError, newiter, [a,None], [],
                        [['readonly'],['writeonly','allocate']],
                        op_dtypes=[None,np.dtype('f4')],
                        op_axes=[None,[0,3,1]])
    # If using op_axes, there can't be duplicates
    assert_raises(ValueError, newiter, [a,None], [],
                        [['readonly'],['writeonly','allocate']],
                        op_dtypes=[None,np.dtype('f4')],
                        op_axes=[None,[0,2,1,0]])

def test_iter_remove_coords_inner_loop():
    # Check that removing coords support works

    a = arange(24).reshape(2,3,4)

    i = newiter(a,['coords'])
    assert_equal(i.ndim, 3)
    assert_equal(i.shape, (2,3,4))
    assert_equal(i.itviews[0].shape, (2,3,4))

    # Removing coords causes all dimensions to coalesce
    before = [x for x in i]
    i.remove_coords()
    after = [x for x in i]

    assert_equal(before, after)
    assert_equal(i.ndim, 1)
    assert_raises(ValueError, lambda i:i.shape, i)
    assert_equal(i.itviews[0].shape, (24,))

    # Removing the inner loop means there's just one iteration
    i.reset()
    assert_equal(i.itersize, 24)
    assert_equal(i[0].shape, tuple())
    i.remove_inner_loop()
    assert_equal(i.itersize, 24)
    assert_equal(i[0].shape, (24,))
    assert_equal(i.value, arange(24))

def test_iter_iterindex():
    # Make sure iterindex works

    buffersize = 5
    a = arange(24).reshape(4,3,2)
    for flags in ([], ['buffered']):
        i = newiter(a, flags, buffersize=buffersize)
        assert_equal(iter_iterindices(i), range(24))
        i.iterindex = 2
        assert_equal(iter_iterindices(i), range(2,24))

        i = newiter(a, flags, order='F', buffersize=buffersize)
        assert_equal(iter_iterindices(i), range(24))
        i.iterindex = 5
        assert_equal(iter_iterindices(i), range(5,24))

        i = newiter(a[::-1], flags, order='F', buffersize=buffersize)
        assert_equal(iter_iterindices(i), range(24))
        i.iterindex = 9
        assert_equal(iter_iterindices(i), range(9,24))

        i = newiter(a[::-1,::-1], flags, order='C', buffersize=buffersize)
        assert_equal(iter_iterindices(i), range(24))
        i.iterindex = 13
        assert_equal(iter_iterindices(i), range(13,24))

        i = newiter(a[::1,::-1], flags, buffersize=buffersize)
        assert_equal(iter_iterindices(i), range(24))
        i.iterindex = 23
        assert_equal(iter_iterindices(i), range(23,24))
        i.reset()
        i.iterindex = 2
        assert_equal(iter_iterindices(i), range(2,24))

def test_iter_iterrange():
    # Make sure getting and resetting the iterrange works

    buffersize = 5
    a = arange(24, dtype='i4').reshape(4,3,2)
    a_fort = a.ravel(order='F')

    i = newiter(a, ['ranged'], ['readonly'], order='F',
                buffersize=buffersize)
    assert_equal(i.iterrange, (0,24))
    assert_equal([x[()] for x in i], a_fort)
    for r in [(0,24), (1,2), (3,24), (5,5), (0,20), (23,24)]:
        i.iterrange = r
        assert_equal(i.iterrange, r)
        assert_equal([x[()] for x in i], a_fort[r[0]:r[1]])

    i = newiter(a, ['ranged','buffered'], ['readonly'], order='F',
                op_dtypes='f8', buffersize=buffersize)
    assert_equal(i.iterrange, (0,24))
    assert_equal([x[()] for x in i], a_fort)
    for r in [(0,24), (1,2), (3,24), (5,5), (0,20), (23,24)]:
        i.iterrange = r
        assert_equal(i.iterrange, r)
        assert_equal([x[()] for x in i], a_fort[r[0]:r[1]])

    def get_array(i):
        val = np.array([], dtype='f8')
        for x in i:
            val = np.concatenate((val, x))
        return val

    i = newiter(a, ['ranged','buffered','no_inner_iteration'],
                ['readonly'], order='F',
                op_dtypes='f8', buffersize=buffersize)
    assert_equal(i.iterrange, (0,24))
    assert_equal(get_array(i), a_fort)
    for r in [(0,24), (1,2), (3,24), (5,5), (0,20), (23,24)]:
        i.iterrange = r
        assert_equal(i.iterrange, r)
        assert_equal(get_array(i), a_fort[r[0]:r[1]])

def test_iter_buffering():
    # Test buffering with several buffer sizes and types
    arrays = []
    # F-order swapped array
    arrays.append(np.arange(24,
                    dtype='c16').reshape(2,3,4).T.newbyteorder().byteswap())
    # Contiguous 1-dimensional array
    arrays.append(np.arange(10, dtype='f4'))
    # Unaligned array
    a = np.zeros((4*16+1,), dtype='i1')[1:]
    a.dtype = 'i4'
    a[:] = np.arange(16,dtype='i4')
    arrays.append(a)
    # 4-D F-order array
    arrays.append(np.arange(120,dtype='i4').reshape(5,3,2,4).T)
    for a in arrays:
        for buffersize in (1,2,3,5,8,11,16,1024):
            vals = []
            i = np.newiter(a, ['buffered','no_inner_iteration'],
                           [['readonly','nbo_aligned']],
                           order='C',
                           casting='equiv',
                           buffersize=buffersize)
            while not i.finished:
                assert_(i[0].size <= buffersize)
                vals.append(i[0].copy())
                i.iternext()
            assert_equal(np.concatenate(vals), a.ravel(order='C'))

def test_iter_write_buffering():
    # Test that buffering of writes is working

    # F-order swapped array
    a = np.arange(24).reshape(2,3,4).T.newbyteorder().byteswap()
    i = np.newiter(a, ['buffered'],
                   [['readwrite','nbo_aligned']],
                   casting='equiv',
                   order='C',
                   buffersize=16)
    x = 0
    while not i.finished:
        i[0] = x
        x += 1
        i.iternext()
    assert_equal(a.ravel(order='C'), np.arange(24))

def test_iter_buffered_cast_simple():
    # Test that buffering can handle a simple cast

    a = np.arange(10, dtype='f4')
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned']],
                   casting='same_kind',
                   op_dtypes=[np.dtype('f8')],
                   buffersize=3)
    for v in i:
        v[()] *= 2
    
    assert_equal(a, 2*np.arange(10, dtype='f4'))

def test_iter_buffered_cast_byteswapped():
    # Test that buffering can handle a cast which requires swap->cast->swap

    a = np.arange(10, dtype='f4').newbyteorder().byteswap()
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned','same_kind_casts']],
                   op_dtypes=[np.dtype('f8').newbyteorder()],
                   buffersize=3)
    for v in i:
        v[()] *= 2
    
    assert_equal(a, 2*np.arange(10, dtype='f4'))

    a = np.arange(10, dtype='f8').newbyteorder().byteswap()
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned','unsafe_casts']],
                   op_dtypes=[np.dtype('c8').newbyteorder()],
                   buffersize=3)
    for v in i:
        v[()] *= 2
    
    assert_equal(a, 2*np.arange(10, dtype='f8'))

def test_iter_buffered_cast_byteswapped():
    # Test that buffering can handle a cast which requires swap->cast->copy

    a = np.arange(10, dtype='c8').newbyteorder().byteswap()
    a += 2j
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned']],
                   casting='same_kind',
                   op_dtypes=[np.dtype('c16')],
                   buffersize=3)
    for v in i:
        v[()] *= 2
    assert_equal(a, 2*np.arange(10, dtype='c8') + 4j)

    a = np.arange(10, dtype='c8')
    a += 2j
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned']],
                   casting='same_kind',
                   op_dtypes=[np.dtype('c16').newbyteorder()],
                   buffersize=3)
    for v in i:
        v[()] *= 2
    assert_equal(a, 2*np.arange(10, dtype='c8') + 4j)

    a = np.arange(10, dtype=np.clongdouble).newbyteorder().byteswap()
    a += 2j
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned']],
                   casting='same_kind',
                   op_dtypes=[np.dtype('c16')],
                   buffersize=3)
    for v in i:
        v[()] *= 2
    assert_equal(a, 2*np.arange(10, dtype=np.clongdouble) + 4j)

    a = np.arange(10, dtype=np.longdouble).newbyteorder().byteswap()
    i = np.newiter(a, ['buffered','no_inner_iteration'],
                   [['readwrite','nbo_aligned']],
                   casting='same_kind',
                   op_dtypes=[np.dtype('f4')],
                   buffersize=7)
    for v in i:
        v[()] *= 2
    assert_equal(a, 2*np.arange(10, dtype=np.longdouble))

def test_iter_buffering_badwriteback():
    # Writing back from a buffer cannot combine elements

    # a needs write buffering, but had a broadcast dimension
    a = np.arange(6).reshape(2,3,1)
    b = np.arange(12).reshape(2,3,2)
    assert_raises(ValueError,np.newiter,[a,b],
                        ['buffered','no_inner_iteration'],
                        [['readwrite'],['writeonly']],
                        order='C')

    # But if a is readonly, it's fine
    i = np.newiter([a,b],['buffered','no_inner_iteration'],
                        [['readonly'],['writeonly']],
                        order='C')
    
    # If a has just one element, it's fine too (constant 0 stride)
    a = np.arange(1).reshape(1,1,1)
    i = np.newiter([a,b],['buffered','no_inner_iteration'],
                        [['readwrite'],['writeonly']],
                        order='C')

    # check that it fails on other dimensions too
    a = np.arange(6).reshape(1,3,2)
    assert_raises(ValueError,np.newiter,[a,b],
                        ['buffered','no_inner_iteration'],
                        [['readwrite'],['writeonly']],
                        order='C')
    a = np.arange(4).reshape(2,1,2)
    assert_raises(ValueError,np.newiter,[a,b],
                        ['buffered','no_inner_iteration'],
                        [['readwrite'],['writeonly']],
                        order='C')

def test_iter_buffering_growinner():
    # Test that the inner loop grows when no buffering is needed
    a = np.arange(30)
    i = np.newiter(a, ['buffered','growinner','no_inner_iteration'],
                           buffersize=5)
    # Should end up with just one inner loop here
    assert_equal(i[0].size, a.size)

def test_iter_no_broadcast():
    # Test that the no_broadcast flag works
    a = np.arange(24).reshape(2,3,4)
    b = np.arange(6).reshape(2,3,1)
    c = np.arange(12).reshape(3,4)

    i = np.newiter([a,b,c], [],
                    [['readonly','no_broadcast'],['readonly'],['readonly']])
    assert_raises(ValueError, np.newiter, [a,b,c], [],
                    [['readonly'],['readonly','no_broadcast'],['readonly']])
    assert_raises(ValueError, np.newiter, [a,b,c], [],
                    [['readonly'],['readonly'],['readonly','no_broadcast']])

def test_iter_nested_iters_basic():
    # Test nested iteration basic usage
    a = arange(12).reshape(2,3,2)

    i, j = np.nested_iters(a, [[0],[1,2]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1,2,3,4,5],[6,7,8,9,10,11]])

    i, j = np.nested_iters(a, [[0,1],[2]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1],[2,3],[4,5],[6,7],[8,9],[10,11]])

    i, j = np.nested_iters(a, [[0,2],[1]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,2,4],[1,3,5],[6,8,10],[7,9,11]])

def test_iter_nested_iters_reorder():
    # Test nested iteration basic usage
    a = arange(12).reshape(2,3,2)

    # In 'K' order (default), it gets reordered
    i, j = np.nested_iters(a, [[0],[2,1]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1,2,3,4,5],[6,7,8,9,10,11]])

    i, j = np.nested_iters(a, [[1,0],[2]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1],[2,3],[4,5],[6,7],[8,9],[10,11]])

    i, j = np.nested_iters(a, [[2,0],[1]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,2,4],[1,3,5],[6,8,10],[7,9,11]])

    # In 'C' order, it doesn't
    i, j = np.nested_iters(a, [[0],[2,1]], order='C')
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,2,4,1,3,5],[6,8,10,7,9,11]])

    i, j = np.nested_iters(a, [[1,0],[2]], order='C')
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1],[6,7],[2,3],[8,9],[4,5],[10,11]])

    i, j = np.nested_iters(a, [[2,0],[1]], order='C')
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,2,4],[6,8,10],[1,3,5],[7,9,11]])

def test_iter_nested_iters_flip_axes():
    # Test nested iteration with negative axes
    a = arange(12).reshape(2,3,2)[::-1,::-1,::-1]

    # In 'K' order (default), the axes all get flipped
    i, j = np.nested_iters(a, [[0],[1,2]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1,2,3,4,5],[6,7,8,9,10,11]])

    i, j = np.nested_iters(a, [[0,1],[2]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1],[2,3],[4,5],[6,7],[8,9],[10,11]])

    i, j = np.nested_iters(a, [[0,2],[1]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,2,4],[1,3,5],[6,8,10],[7,9,11]])

    # In 'C' order, flipping axes is disabled
    i, j = np.nested_iters(a, [[0],[1,2]], order='C')
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[11,10,9,8,7,6],[5,4,3,2,1,0]])

    i, j = np.nested_iters(a, [[0,1],[2]], order='C')
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[11,10],[9,8],[7,6],[5,4],[3,2],[1,0]])

    i, j = np.nested_iters(a, [[0,2],[1]], order='C')
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[11,9,7],[10,8,6],[5,3,1],[4,2,0]])

def test_iter_nested_iters_broadcast():
    # Test nested iteration with broadcasting
    a = arange(2).reshape(2,1)
    b = arange(3).reshape(1,3)

    i, j = np.nested_iters([a,b], [[0],[1]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[[0,0],[0,1],[0,2]],[[1,0],[1,1],[1,2]]])

    i, j = np.nested_iters([a,b], [[1],[0]])
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[[0,0],[1,0]],[[0,1],[1,1]],[[0,2],[1,2]]])

def test_iter_nested_iters_dtype_copy():
    # Test nested iteration with a copy to change dtype

    # copy
    a = arange(6, dtype='i4').reshape(2,3)
    i, j = np.nested_iters(a, [[0],[1]],
                        op_flags=['readonly','copy'],
                        op_dtypes='f8')
    assert_equal(j[0].dtype, np.dtype('f8'))
    vals = []
    for x in i:
        vals.append([y for y in j])
    assert_equal(vals, [[0,1,2],[3,4,5]])
    vals = None

    # updateifcopy
    a = arange(6, dtype='f4').reshape(2,3)
    i, j = np.nested_iters(a, [[0],[1]],
                        op_flags=['readwrite','updateifcopy'],
                        casting='same_kind',
                        op_dtypes='f8')
    assert_equal(j[0].dtype, np.dtype('f8'))
    for x in i:
        for y in j:
            y[()] += 1
    assert_equal(a, [[0,1,2],[3,4,5]])
    i, j, x, y = (None,)*4 # force the updateifcopy
    assert_equal(a, [[1,2,3],[4,5,6]])

def test_iter_nested_iters_dtype_buffered():
    # Test nested iteration with buffering to change dtype

    a = arange(6, dtype='f4').reshape(2,3)
    i, j = np.nested_iters(a, [[0],[1]],
                        flags=['buffered'],
                        op_flags=['readwrite'],
                        casting='same_kind',
                        op_dtypes='f8')
    assert_equal(j[0].dtype, np.dtype('f8'))
    for x in i:
        for y in j:
            y[()] += 1
    assert_equal(a, [[1,2,3],[4,5,6]])

if __name__ == "__main__":
    run_module_suite()
