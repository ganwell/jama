import jama.change as cmod


def test_file_repr():
    file = cmod.FileRepr.from_user_repr([0])
    assert file.node_list == [cmod.FileNodes.content]
    assert file.to_user_repr() == [0]
    file = cmod.FileRepr.from_user_repr([0, 1])
    assert file.node_list == [cmod.FileNodes.content, cmod.FileNodes.content + 1]
    assert file.to_user_repr() == [0, 1]
    file = cmod.FileRepr.from_user_repr([1])
    assert file.node_list == [cmod.FileNodes.content + 1]
    assert file.to_user_repr() == [1]
