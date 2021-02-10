import pytest
from hypothesis import given, strategies as st

from jama.change import Change, File, Insert


def cap(x):
    if x > 1.0:
        return 1.0
    if x < 0.0:
        return 0.0
    return x


max_len = 30
over_range = st.floats(-0.001, 1.001).map(cap)
insert = st.tuples(st.just("insert"), over_range, st.integers(0, max_len))
delete = st.tuples(st.just("delete"), over_range, over_range)
change = st.one_of(insert, delete)


# @given(st.integers(0, max_len), st.lists(change))
# def test_change(initial, changes):
#     cur = File.from_size(initial)
#     for ct, pos, size in changes:
#         if ct == "insert":
#             cur = cur.insert(int(pos * len(cur)), size)
#         elif ct == "delete":
#             rest = 1.0 - pos
#             len_cur = len(cur)
#             to_delete = int(size * rest * len_cur)
#             cur = cur.delete(int(pos * len_cur), to_delete)
#         else:
#             raise RuntimeError()
#         files.append(cur)


def test_diff():
    a = File.from_size(3)
    b = a.insert(0, 1)
    assert b.graph == [3, 0, 1, 2]
    assert len(b) == 4
    c = list(Change.from_diff(a, b))
    assert c == [Insert(None, [3])]


def test_add():
    a = File.from_size(3)
    assert len(a) == 3
    assert a.graph == [0, 1, 2]
    b = a.insert(0, 0)
    assert b.graph == [0, 1, 2]
    b = a.insert(0, 1)
    assert b.graph == [3, 0, 1, 2]
    assert len(b) == 4
    b = a.insert(0, 2)
    assert b.graph == [3, 4, 0, 1, 2]
    b = a.insert(1, 0)
    assert b.graph == [0, 1, 2]
    b = a.insert(1, 1)
    assert b.graph == [0, 3, 1, 2]
    b = a.insert(1, 2)
    assert b.graph == [0, 3, 4, 1, 2]
    b = a.insert(1, 2)
    assert b.graph == [0, 3, 4, 1, 2]
    b = a.insert(2, 1)
    assert b.graph == [0, 1, 3, 2]
    b = a.insert(3, 1)
    assert b.graph == [0, 1, 2, 3]
    with pytest.raises(IndexError):
        b = a.insert(4, 1)
    with pytest.raises(IndexError):
        b = a.insert(5, 1)
    with pytest.raises(IndexError):
        b = a.insert(-1, 1)


def test_del():
    a = File.from_size(3)
    assert a.graph == [0, 1, 2]
    b = a.delete(0, 0)
    assert b.graph == [0, 1, 2]
    b = a.delete(1, 0)
    assert b.graph == [0, 1, 2]
    b = a.delete(0, 1)
    assert b.graph == [1, 2]
    b = a.delete(0, 2)
    assert b.graph == [2]
    b = a.delete(1, 2)
    assert b.graph == [0]
    c = b.insert(0, 1)
    assert c.graph == [3, 0]
