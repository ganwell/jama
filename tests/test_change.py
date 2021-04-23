import pytest

import jama.change as cmod


def test_file_repr():
    file_ = cmod.FileRepr.from_user_repr([0])
    assert file_.node_list == [cmod.FileNodes.content]
    assert file_.to_user_repr() == [0]
    file_ = cmod.FileRepr.from_user_repr([0, 1])
    assert file_.node_list == [cmod.FileNodes.content, cmod.FileNodes.content + 1]
    assert file_.to_user_repr() == [0, 1]
    file_ = cmod.FileRepr.from_user_repr([1])
    assert file_.node_list == [cmod.FileNodes.content + 1]
    assert file_.to_user_repr() == [1]


def test_file_repr_edit():
    file_ = cmod.FileReprEdit.from_user_repr([0])
    assert file_.node_list == [cmod.FileNodes.content]
    assert file_.max_uid == cmod.FileNodes.content
    assert file_.max_uid == file_.node_list[0]
    file_ = cmod.FileReprEdit.from_size(2)
    assert file_.max_uid == file_.node_list[1]
    assert file_.max_uid == cmod.FileNodes.content + 1


def test_state_from_file():
    fn = cmod.FileNodes
    ct = fn.content
    a = cmod.FileReprEdit.from_size(2)
    b = cmod.State.from_file(a)
    assert b.nodes == [True, True, True, True]
    assert b.to_user_nodes() == [True, True]
    assert b.edges == {
        (fn.start + ct, 0 + ct),
        (0 + ct, 1 + ct),
        (1 + ct, fn.end + ct),
    }
    assert set(b.to_user_edges()) == {
        (fn.start, 0),
        (0, 1),
        (1, fn.end),
    }


def test_add():
    a = cmod.FileReprEdit.from_size(3)
    assert len(a) == 3
    assert a.to_user_repr() == [0, 1, 2]
    b = a.insert(0, 0)
    assert b.to_user_repr() == [0, 1, 2]
    b = a.insert(0, 1)
    assert b.to_user_repr() == [3, 0, 1, 2]
    assert len(b) == 4
    b = a.insert(0, 2)
    assert b.to_user_repr() == [3, 4, 0, 1, 2]
    b = a.insert(1, 0)
    assert b.to_user_repr() == [0, 1, 2]
    b = a.insert(1, 1)
    assert b.to_user_repr() == [0, 3, 1, 2]
    b = a.insert(1, 2)
    assert b.to_user_repr() == [0, 3, 4, 1, 2]
    b = a.insert(1, 2)
    assert b.to_user_repr() == [0, 3, 4, 1, 2]
    b = a.insert(2, 1)
    assert b.to_user_repr() == [0, 1, 3, 2]
    b = a.insert(3, 1)
    assert b.to_user_repr() == [0, 1, 2, 3]
    with pytest.raises(IndexError):
        b = a.insert(4, 1)
    with pytest.raises(IndexError):
        b = a.insert(5, 1)
    with pytest.raises(IndexError):
        b = a.insert(-1, 1)


def test_del():
    a = cmod.FileReprEdit.from_size(3)
    assert a.to_user_repr() == [0, 1, 2]
    b = a.delete(0, 0)
    assert b.to_user_repr() == [0, 1, 2]
    b = a.delete(1, 0)
    assert b.to_user_repr() == [0, 1, 2]
    b = a.delete(0, 1)
    assert b.to_user_repr() == [1, 2]
    b = a.delete(0, 2)
    assert b.to_user_repr() == [2]
    b = a.delete(1, 2)
    assert b.to_user_repr() == [0]
    c = b.insert(0, 1)
    assert c.to_user_repr() == [3, 0]


def test_diff_add():
    fn = cmod.FileNodes
    a = cmod.FileReprEdit.from_size(3)
    b = a.insert(0, 1)
    assert b.to_user_repr() == [3, 0, 1, 2]
    assert len(b) == 4
    # c = list(cmod.Change.from_diff(a, b))
    # assert c == [cmod.Insert(fn.start, [3], 0)]
    # b = a.insert(1, 1)
    # assert b.to_user_repr() == [0, 3, 1, 2]
    # c = list(cmod.Change.from_diff(a, b))
    # assert c == [cmod.Insert(0, [3], 1)]
    # b = a.insert(2, 2)
    # assert b.to_user_repr() == [0, 1, 3, 4, 2]
    # c = list(cmod.Change.from_diff(a, b))
    # assert c == [cmod.Insert(1, [3, 4], 2)]
    # b = a.insert(3, 2)
    # assert b.to_user_repr() == [0, 1, 2, 3, 4]
    # c = list(cmod.Change.from_diff(a, b))
    # assert c == [cmod.Insert(2, [3, 4], fn.end)]
