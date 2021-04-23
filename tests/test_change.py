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
