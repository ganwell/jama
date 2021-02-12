import pytest
from hypothesis import example, given, strategies as st

from jama.change import Change, Delete, FileRepr, FileReprEdit, Insert, State


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


@given(st.integers(0, max_len), st.lists(change))
@example(
    initial=5,
    changes=[("insert", 0.0, 10), ("delete", 0.0, 0.06666666666666686)],
)
def test_change(initial, changes):
    cur = FileReprEdit.from_size(initial)
    orig = cur
    all_changes = []
    for ct, pos, size in changes:
        prev = cur
        if ct == "insert":
            cur = cur.insert(int(pos * len(cur)), size)
        elif ct == "delete":
            rest = 1.0 - pos
            len_cur = len(cur)
            to_delete = int(size * rest * len_cur)
            cur = cur.delete(int(pos * len_cur), to_delete)
        else:
            raise RuntimeError()
        changes = list(Change.from_diff(prev, cur))
        all_changes.extend(changes)
        state = State.from_file(prev)
        for change in changes:
            state = change.apply(state)
        assert state.to_file().graph == cur.graph
    # state = State.from_file(orig)
    # for change in all_changes:
    #     prev_state = state
    #     try:
    #         state = change.apply(state)
    #     except:
    #         __import__("pdb").set_trace()
    #         change.apply(state, True)
    #         pass


def test_state_from_file():
    a = FileReprEdit.from_size(2)
    b = State.from_file(a)
    assert b.graph == [(0, True), (1, True)]


def test_delete_apply():
    a = FileRepr([0, 1, 2])
    b = State.from_file(a)
    assert b.graph == [(0, True), (1, True), (2, True)]
    c = Delete(1)
    d = c.apply(b)
    assert d.graph == [(0, True), (1, False), (2, True)]


def test_basic_insert():
    a = FileRepr([0, 1, 2])
    b = State.from_file(a)
    assert b.graph == [(0, True), (1, True), (2, True)]
    c = Insert(1, [3], 2)
    d = c.apply(b)
    assert d.graph == [(0, True), (1, True), (3, True), (2, True)]
    c = Insert(None, [3], 0)
    d = c.apply(b)
    assert d.graph == [(3, True), (0, True), (1, True), (2, True)]
    c = Insert(2, [3], None)
    d = c.apply(b)
    assert d.graph == [(0, True), (1, True), (2, True), (3, True)]
    c = Insert(0, [3], 2)
    d = c.apply(b)
    assert d.graph == [(0, True), [[(1, True)], [(3, True)]], (2, True)]


def test_complex_insert():
    a = FileRepr([0, 1, 2])
    b = State.from_file(a)
    c = Insert(None, [3], 2)
    d = c.apply(b)
    assert d.graph == [[[(0, True), (1, True)], [(3, True)]], (2, True)]


def test_complex_del():
    a = FileRepr([0, 1, 2])
    b = State.from_file(a)
    c = Insert(None, [3], 2)
    d = c.apply(b)
    assert d.graph == [[[(0, True), (1, True)], [(3, True)]], (2, True)]
    e = Delete(0)
    f = e.apply(d)
    assert f.graph == [[[(0, False), (1, True)], [(3, True)]], (2, True)]


def test_diff_add():
    a = FileReprEdit.from_size(3)
    b = a.insert(0, 1)
    assert b.graph == [3, 0, 1, 2]
    assert len(b) == 4
    c = list(Change.from_diff(a, b))
    assert c == [Insert(None, [3], 0)]
    b = a.insert(1, 1)
    assert b.graph == [0, 3, 1, 2]
    c = list(Change.from_diff(a, b))
    assert c == [Insert(0, [3], 1)]
    b = a.insert(2, 2)
    assert b.graph == [0, 1, 3, 4, 2]
    c = list(Change.from_diff(a, b))
    assert c == [Insert(1, [3, 4], 2)]
    b = a.insert(3, 2)
    assert b.graph == [0, 1, 2, 3, 4]
    c = list(Change.from_diff(a, b))
    assert c == [Insert(2, [3, 4], None)]


def test_diff_del():
    a = FileReprEdit.from_size(3)
    assert a.graph == [0, 1, 2]
    b = a.delete(0, 1)
    assert b.graph == [1, 2]
    c = list(Change.from_diff(a, b))
    assert c == [Delete(0)]
    b = a.delete(1, 1)
    assert b.graph == [0, 2]
    c = list(Change.from_diff(a, b))
    assert c == [Delete(1)]
    b = a.delete(1, 2)
    assert b.graph == [0]
    c = list(Change.from_diff(a, b))
    assert c == [Delete(1), Delete(2)]


def test_diff_repl():
    a = FileRepr([0, 1, 2])
    b = FileRepr([0, 3, 2])
    c = list(Change.from_diff(a, b))
    assert c == [Delete(1), Insert(0, [3], 2)]
    a = FileRepr([0, 1, 2])
    b = FileRepr([0, 1, 3])
    c = list(Change.from_diff(a, b))
    assert c == [Delete(2), Insert(1, [3], None)]
    a = FileRepr([0, 1, 2])
    b = FileRepr([3, 1, 2])
    c = list(Change.from_diff(a, b))
    assert c == [Delete(0), Insert(None, [3], 1)]
    a = FileRepr([0, 1, 2])
    b = FileRepr([0, 3, 4, 2])
    c = list(Change.from_diff(a, b))
    assert c == [Delete(1), Insert(0, [3, 4], 2)]
    a = FileRepr([0, 1, 2])
    b = FileRepr([0, 3])
    c = list(Change.from_diff(a, b))
    assert c == [Delete(1), Delete(2), Insert(0, [3], None)]


def test_add():
    a = FileReprEdit.from_size(3)
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
    a = FileReprEdit.from_size(3)
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
