import pytest
from hypothesis import given, strategies as st

from jama.change import File

max_len = 30
add = st.tuples(st.just("add"), st.floats(0, 1), st.integers(0, max_len))
delete = st.tuples(st.just("delete"), st.floats(0, 1), st.floats(0, 1))
change = st.one_of(add, delete)


# @given(st.integers(0, max_len), st.lists(change))
# def test_change(initial, changes):
#     files = [File(initial_graph, initial)]
#     for ct, pos, len in changes:
#         pass


def test_add():
    a = File.from_size(3)
    assert a.graph == [0, 1, 2]
    b = a.add(0, 0)
    assert b.graph == [0, 1, 2]
    b = a.add(0, 1)
    assert b.graph == [3, 0, 1, 2]
    b = a.add(0, 2)
    assert b.graph == [3, 4, 0, 1, 2]
    b = a.add(1, 0)
    assert b.graph == [0, 1, 2]
    b = a.add(1, 1)
    assert b.graph == [0, 3, 1, 2]
    b = a.add(1, 2)
    assert b.graph == [0, 3, 4, 1, 2]
    b = a.add(1, 2)
    assert b.graph == [0, 3, 4, 1, 2]
    b = a.add(2, 1)
    assert b.graph == [0, 1, 3, 2]
    b = a.add(3, 1)
    assert b.graph == [0, 1, 2, 3]
    with pytest.raises(IndexError):
        b = a.add(4, 1)
    with pytest.raises(IndexError):
        b = a.add(5, 1)
    with pytest.raises(IndexError):
        b = a.add(-1, 1)


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
    c = b.add(0, 1)
    assert c.graph == [3, 0]
