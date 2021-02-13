from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
from typing import Generator, Iterable, Union, cast

import attr
from attr import dataclass
from pyrsistent import pset, pvector
from pyrsistent.typing import PSet, PVector

# Rules
# =====
#
# The algorithm tracks lines and not their content. Of course the changes can be replayed
# on the actual content to get a result.
#
# 0. Every line in a file has a unique id (0, 1, 2)
# 1. A line cannot be changed or removed: only inserted and hidden
# 2. Lines inserted get incremented uids
# 4. A line that is inserted can "replace" existing lines
#    -> This creates a paralell path in the graph (again no information remove)
# 5. Line can be inserted between hidden line
#
# This means no information is ever removed from the state. A state can be in conflict,
# which is represented by its graph. If the file is not in conflict it can be traversed
# to create a new flat file. The changes that cause the conflic are identified and can
# be reverted.

# Example
# =======
#
# v = visible
# h = hidden
#
# We call hide Delete because that is the action hide prepresents.
#
# [(0, v), (1, v), (2, v)] -> Delete(1) -> [(0, v), (1, h), (2, v)] ->
# Insert(0, [3], 2) -> [(0, v), [(1, h), (3, v)], (2, v)]
#
# is the same as
# [(0, v), (1, v), (2, v)] -> Insert(0, [3], 2) -> [(0, v), [(1, v), 3, v], (2, v)]
# Delete(1) ->  [(0, v), [(1, h), (3, v)], (2, v)]
#
# both read as: (0, 3, 2)
#
# at least some changes are commutative. I hope that most non-conflicting changes are commutative.

# TODO: Incremental purging might reduce complexity, but probably kills a lot of
# commutation opertunities


class InconsistentError(Exception):
    pass


def get_diff(a, b):
    return SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()


@dataclass(slots=True, frozen=True)
class FileRepr(object):
    node_list: PVector[int]

    node_list = cast(PVector[int], attr.ib(converter=pvector))


@dataclass(slots=True, frozen=True)
class FileReprEdit(FileRepr):
    max_uid: int

    @classmethod
    def from_size(cls, size):
        return cls(pvector(range(size)), size)

    def __len__(self):
        return len(self.node_list)

    def insert(self, offset, size):
        if offset < 0 or offset > len(self):
            raise IndexError()
        node_list = self.node_list
        uid = self.max_uid
        if size == 0:
            return FileReprEdit(list(node_list), uid)
        node_list = (
            node_list[:offset] + list(range(uid, uid + size)) + node_list[offset:]
        )
        return FileReprEdit(node_list, self.max_uid + size)

    def delete(self, offset, size):
        node_list = self.node_list
        return FileReprEdit(
            node_list[:offset] + node_list[offset + size :],
            self.max_uid,
        )


class Nodes(Enum):
    start = -1
    end = -2


Node = Union[Nodes, int]


def node_list_to_edges(
    nodes: Iterable[Node],
    start: Node = Nodes.start,
    end: Node = Nodes.end,
) -> Generator[tuple[Node, Node], None, None]:
    prev = start
    for node in nodes:
        yield (prev, node)
        prev = node
    yield (prev, end)


def node_list_to_edge_set(
    nodes: Iterable[Node],
    start: Node = Nodes.start,
    end: Node = Nodes.end,
) -> PSet[tuple[Node, Node]]:
    return pset(node_list_to_edges(nodes, start, end))


# State is something like a CRDT
@dataclass(slots=True, frozen=True)
class State(object):
    nodes: PVector[bool]
    edges: PSet[tuple[Node, Node]]
    history: PVector[Change]

    @classmethod
    def from_file(cls, file_: FileRepr):
        node_list = file_.node_list
        nodes = pvector([True] * len(node_list))
        return cls(nodes, node_list_to_edge_set(node_list), pvector())

    def to_file(self) -> FileRepr:
        pass

    def has_conflict(self) -> bool:
        raise NotImplementedError()

    def delete(self, change: Delete) -> State:
        return State(
            self.nodes.set(change.line, False),
            self.edges,
            self.history.append(change),
        )

    def insert(self, change: Insert) -> State:
        insert_set = node_list_to_edge_set(
            change.lines,
            change.predecessor,
            change.successor,
        )
        return State(
            self.nodes,
            self.edges.update(insert_set),
            self.history.append(change),
        )


@dataclass(slots=True, frozen=True)
class Change(object):
    def apply(self, state: State) -> State:
        raise NotImplementedError()

    @classmethod
    def pre_suc(_, ag, left, right):
        pre = Nodes.start
        suc = Nodes.end
        if left:
            pre = ag[left - 1]
        if right != len(ag):
            suc = ag[right]
        return pre, suc

    @classmethod
    def from_diff(cls, a: FileRepr, b: FileRepr):
        a_node_list = a.node_list
        b_node_list = b.node_list
        for (
            ct,
            a_left,
            a_right,
            b_left,
            b_right,
        ) in get_diff(a_node_list, b_node_list):
            if ct == "insert":
                pre, suc = cls.pre_suc(
                    a_node_list,
                    a_left,
                    a_left,
                )
                yield Insert(
                    pre,
                    b_node_list[b_left:b_right],
                    suc,
                )
            elif ct == "delete":
                for line in a_node_list[a_left:a_right]:
                    yield Delete(line)
            elif ct == "replace":
                for line in a_node_list[a_left:a_right]:
                    yield Delete(line)
                pre, suc = cls.pre_suc(
                    a_node_list,
                    a_left,
                    a_right,
                )
                yield Insert(
                    pre,
                    b_node_list[b_left:b_right],
                    suc,
                )


@dataclass(slots=True, frozen=True)
class Insert(Change):
    predecessor: int
    lines: PVector[int]
    successor: int

    lines = cast(PVector[int], attr.ib(converter=pvector))

    def __attrs_post_init__(self):
        assert len(self.lines) > 0
        assert self.predecessor != Nodes.end
        assert self.successor != Nodes.start
        assert self.predecessor != self.successor

    def apply(self, state: State) -> State:
        return state.insert(self)


@dataclass(slots=True, frozen=True)
class Delete(Change):
    line: int

    def apply(self, state: State) -> State:
        return state.delete(self)
