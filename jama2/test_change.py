import pytest
from hypothesis import example, given, strategies as st

from jama import change as cmod
from jama.change import Nodes

max_size = 10
resolution = max_size * max_size * 4
over = 3


def cap(x):
    x /= resolution
    if x > 1.0:
        return 1.0
    if x < 0.0:
        return 0.0
    return x


over_range = st.integers(-over, resolution + over).map(cap)
insert = st.tuples(st.just("insert"), over_range, st.integers(0, max_size))
delete = st.tuples(st.just("delete"), over_range, over_range)
change = st.one_of(insert, delete)
change_set = st.lists(change, max_size=max_size)


_x = 0


@given(st.integers(0, max_size), st.lists(change))
@example(
    initial=2,
    changes=[("delete", 0.0, 0.5), ("insert", 0.0, 1)],
)
def test_gen_changes(initial, changes):
    cur = cmod.FileReprEdit.from_size(initial)
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
        assert len(cur) < resolution
        changes = list(cmod.Change.from_diff(prev, cur))
        all_changes.extend(changes)
        state = cmod.State.from_file(prev)
        for change in changes:
            state = change.apply(state)
        assert state.to_file().node_list == cur.node_list
    # state = cmod.State.from_file(orig)
    # for change in all_changes:
    #     state = change.apply(state)
    # try:
    #     assert state.to_file().node_list == cur.node_list
    # except cmod.ConflictError:
    #     __import__("pdb").set_trace()
    #     pass


def test_node_to_edge():
    a = cmod.node_list_to_edges([0])
    assert list(a) == [(Nodes.start, 0), (0, Nodes.end)]
    a = cmod.node_list_to_edges([0, 1])
    assert list(a) == [(Nodes.start, 0), (0, 1), (1, Nodes.end)]
    a = cmod.node_list_to_edges([1, 0])
    assert list(a) == [(Nodes.start, 1), (1, 0), (0, Nodes.end)]
    a = cmod.node_list_to_edges([1, 2, 0])
    assert list(a) == [(Nodes.start, 1), (1, 2), (2, 0), (0, Nodes.end)]


def test_state_from_file():
    a = cmod.FileReprEdit.from_size(2)
    b = cmod.State.from_file(a)
    assert b.nodes == [True, True]
    assert b.edges == {(Nodes.start, 0), (0, 1), (1, Nodes.end)}


def test_delete_apply():
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.State.from_file(a)
    assert b.nodes == [True, True, True]
    assert b.edges == {(Nodes.start, 0), (0, 1), (1, 2), (2, Nodes.end)}
    c = cmod.Delete(1)
    d = c.apply(b)
    assert d.nodes == [True, False, True]
    assert d.edges == {(Nodes.start, 0), (0, 1), (1, 2), (2, Nodes.end)}


def test_collect():
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.State.from_file(a)
    c = cmod.Delete(1)
    d = c.apply(b)
    e = cmod.collect_deleted_nodes(d.edges, d.nodes)
    assert e == {(Nodes.start, 0), (0, 2), (2, Nodes.end)}

    c = cmod.Insert(0, [3], 2)
    d = c.apply(b)
    e = cmod.Delete(2)
    f = e.apply(d)
    g = cmod.collect_deleted_nodes(f.edges, f.nodes)
    assert g == {(Nodes.start, 0), (0, 1), (0, 3), (1, Nodes.end), (3, Nodes.end)}


def test_collect_problem():
    a = cmod.FileReprEdit.from_size(2)
    b = cmod.State.from_file(a)
    c = cmod.Delete(0).apply(b)
    assert c.nodes == [False, True]
    d = cmod.Insert(Nodes.start, [2], 1).apply(c)
    assert d.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, Nodes.end),
        (Nodes.start, 2),
        (2, 1),
    }
    e = cmod.collect_deleted_nodes(d.edges, d.nodes)


def test_collect_complex():
    a = cmod.State.from_graph(
        [True, True, False, True, True],
        {
            (Nodes.start, 0),
            (Nodes.start, 1),
            (3, Nodes.end),
            (4, Nodes.end),
            (0, 2),
            (1, 2),
            (2, 3),
            (2, 4),
        },
    )
    b = cmod.collect_deleted_nodes(a.edges, a.nodes)
    assert b == {
        (Nodes.start, 0),
        (Nodes.start, 1),
        (3, Nodes.end),
        (4, Nodes.end),
        (0, 3),
        (0, 4),
        (1, 3),
        (1, 4),
    }
    pass


def test_basic_insert():
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.State.from_file(a)
    assert b.nodes == [True, True, True]
    assert b.edges == {(Nodes.start, 0), (0, 1), (1, 2), (2, Nodes.end)}

    c = cmod.Insert(1, [3], 2)
    d = c.apply(b)
    assert d.nodes == [True, True, True, True]
    assert d.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, 3),
        (3, 2),
        (2, Nodes.end),
    }

    c = cmod.Insert(Nodes.start, [3], 0)
    d = c.apply(b)
    assert d.nodes == [True, True, True, True]
    assert d.edges == {
        (0, 1),
        (1, 2),
        (Nodes.start, 3),
        (3, 0),
        (2, Nodes.end),
    }

    c = cmod.Insert(2, [3], Nodes.end)
    d = c.apply(b)
    assert d.nodes == [True, True, True, True]
    assert d.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, 2),
        (2, 3),
        (3, Nodes.end),
    }


def test_insert_with_hole():
    a = cmod.FileRepr([0, 2, 3])
    b = cmod.State.from_file(a)
    assert b.nodes == [True, False, True, True]
    assert b.edges == {(Nodes.start, 0), (0, 2), (2, 3), (3, Nodes.end)}

    c = cmod.Insert(1, [3], 2)
    with pytest.raises(AssertionError):
        d = c.apply(b)

    # TODO This is inconsistent. Fix it with a consistency check. I don't want to blow
    # up the complexity for this
    c = cmod.Insert(1, [4], 2)
    d = c.apply(b)
    assert d.nodes == [True, False, True, True, True]
    assert d.edges == {
        (Nodes.start, 0),
        (0, 2),
        (1, 4),
        (4, 2),
        (2, 3),
        (3, Nodes.end),
    }


def test_complex_insert():
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.State.from_file(a)
    assert b.nodes == [True, True, True]
    assert b.edges == {(Nodes.start, 0), (0, 1), (1, 2), (2, Nodes.end)}

    c = cmod.Insert(0, [3], 2)
    d = c.apply(b)
    assert d.nodes == [True, True, True, True]
    assert d.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, 2),
        (0, 3),
        (3, 2),
        (2, Nodes.end),
    }

    c = cmod.Insert(Nodes.start, [3], 2)
    d = c.apply(b)
    assert d.nodes == [True, True, True, True]
    assert d.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, 2),
        (Nodes.start, 3),
        (3, 2),
        (2, Nodes.end),
    }


def test_complex_del():
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.State.from_file(a)
    c = cmod.Insert(Nodes.start, [3], 2)
    d = c.apply(b)
    assert d.nodes == [True, True, True, True]
    assert d.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, 2),
        (Nodes.start, 3),
        (3, 2),
        (2, Nodes.end),
    }
    e = cmod.Delete(0)
    f = e.apply(d)
    assert f.nodes == [False, True, True, True]
    assert f.edges == {
        (Nodes.start, 0),
        (0, 1),
        (1, 2),
        (Nodes.start, 3),
        (3, 2),
        (2, Nodes.end),
    }


def test_diff_add():
    a = cmod.FileReprEdit.from_size(3)
    b = a.insert(0, 1)
    assert b.node_list == [3, 0, 1, 2]
    assert len(b) == 4
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Insert(Nodes.start, [3], 0)]
    b = a.insert(1, 1)
    assert b.node_list == [0, 3, 1, 2]
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Insert(0, [3], 1)]
    b = a.insert(2, 2)
    assert b.node_list == [0, 1, 3, 4, 2]
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Insert(1, [3, 4], 2)]
    b = a.insert(3, 2)
    assert b.node_list == [0, 1, 2, 3, 4]
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Insert(2, [3, 4], Nodes.end)]


def test_diff_del():
    a = cmod.FileReprEdit.from_size(3)
    assert a.node_list == [0, 1, 2]
    b = a.delete(0, 1)
    assert b.node_list == [1, 2]
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(0)]
    b = a.delete(1, 1)
    assert b.node_list == [0, 2]
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(1)]
    b = a.delete(1, 2)
    assert b.node_list == [0]
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(1), cmod.Delete(2)]


def test_diff_repl():
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.FileRepr([0, 3, 2])
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(1), cmod.Insert(0, [3], 2)]
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.FileRepr([0, 1, 3])
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(2), cmod.Insert(1, [3], Nodes.end)]
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.FileRepr([3, 1, 2])
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(0), cmod.Insert(Nodes.start, [3], 1)]
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.FileRepr([0, 3, 4, 2])
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(1), cmod.Insert(0, [3, 4], 2)]
    a = cmod.FileRepr([0, 1, 2])
    b = cmod.FileRepr([0, 3])
    c = list(cmod.Change.from_diff(a, b))
    assert c == [cmod.Delete(1), cmod.Delete(2), cmod.Insert(0, [3], Nodes.end)]


def test_add():
    a = cmod.FileReprEdit.from_size(3)
    assert len(a) == 3
    assert a.node_list == [0, 1, 2]
    b = a.insert(0, 0)
    assert b.node_list == [0, 1, 2]
    b = a.insert(0, 1)
    assert b.node_list == [3, 0, 1, 2]
    assert len(b) == 4
    b = a.insert(0, 2)
    assert b.node_list == [3, 4, 0, 1, 2]
    b = a.insert(1, 0)
    assert b.node_list == [0, 1, 2]
    b = a.insert(1, 1)
    assert b.node_list == [0, 3, 1, 2]
    b = a.insert(1, 2)
    assert b.node_list == [0, 3, 4, 1, 2]
    b = a.insert(1, 2)
    assert b.node_list == [0, 3, 4, 1, 2]
    b = a.insert(2, 1)
    assert b.node_list == [0, 1, 3, 2]
    b = a.insert(3, 1)
    assert b.node_list == [0, 1, 2, 3]
    with pytest.raises(IndexError):
        b = a.insert(4, 1)
    with pytest.raises(IndexError):
        b = a.insert(5, 1)
    with pytest.raises(IndexError):
        b = a.insert(-1, 1)


def test_del():
    a = cmod.FileReprEdit.from_size(3)
    assert a.node_list == [0, 1, 2]
    b = a.delete(0, 0)
    assert b.node_list == [0, 1, 2]
    b = a.delete(1, 0)
    assert b.node_list == [0, 1, 2]
    b = a.delete(0, 1)
    assert b.node_list == [1, 2]
    b = a.delete(0, 2)
    assert b.node_list == [2]
    b = a.delete(1, 2)
    assert b.node_list == [0]
    c = b.insert(0, 1)
    assert c.node_list == [3, 0]
