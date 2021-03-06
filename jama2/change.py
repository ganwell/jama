from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Generator, Iterable, Union, cast

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


class ConflictError(Exception):
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
        return cls(pvector(range(size)), size - 1)

    def __len__(self):
        return len(self.node_list)

    def insert(self, offset, size):
        if offset < 0 or offset > len(self):
            raise IndexError()
        node_list = self.node_list
        uid = self.max_uid + 1
        if size == 0:
            return FileReprEdit(list(node_list), uid)
        node_list = (
            node_list[:offset] + list(range(uid, uid + size)) + node_list[offset:]
        )
        return FileReprEdit(node_list, uid + size - 1)

    def delete(self, offset, size):
        node_list = self.node_list
        return FileReprEdit(
            node_list[:offset] + node_list[offset + size :],
            self.max_uid,
        )


class Nodes(Enum):
    end = 0
    start = 1
    normal = 2


Node = Union[Nodes, int]
Edge = tuple[Node, Node]
NodeDict = defaultdict[Node, set[Node]]
# TODO this should be a special case of some general delete parallel path removal
short_circuit = (Nodes.start, Nodes.end)


def get_outgoing(edges: PSet[Edge]) -> NodeDict:
    outgoing = defaultdict(set)
    for from_, to in edges:
        outgoing[from_].add(to)
    return outgoing


def get_incoming(edges: PSet[Edge]) -> NodeDict:
    incoming = defaultdict(set)
    for from_, to in edges:
        incoming[to].add(from_)
    return incoming


def get_incoming_and_outgoing(edges: PSet[Edge]) -> tuple[NodeDict, NodeDict]:
    outgoing = defaultdict(set)
    incoming = defaultdict(set)
    for from_, to in edges:
        outgoing[from_].add(to)
        incoming[to].add(from_)
    return incoming, outgoing


def edges_to_node_list(edges: NodeDict) -> Generator[int, None, None]:
    # TODO improve because NodeDict now contains a set
    # TODO this is ugly
    cur: Any = Nodes.start
    edge_set = edges.get(cur)
    edge_set.discard(Nodes.end)
    while True:
        if not edge_set:
            break
        else:
            edge_list = list(edge_set)
            if edge_list[0] is Nodes.end:
                break
            elif len(edge_list) > 1:
                raise ConflictError()
            else:
                cur = edge_list[0]
                if cur != Nodes.end:
                    yield cur
        edge_set = edges.get(cur)


def collect_deleted_nodes(edges: PSet[Edge], nodes: PVector[bool]) -> set[Edge]:
    edges = set(edges)
    incoming, outgoing = get_incoming_and_outgoing(edges)
    for node, value in enumerate(nodes):
        if not value:
            removes: list[Edge] = []
            inserts: list[Edge] = []
            for i_node in incoming[node]:
                removes.append((i_node, node))
            for o_node in outgoing[node]:
                removes.append((node, o_node))
            for i_node in incoming[node]:
                for o_node in outgoing[node]:
                    inserts.append((i_node, o_node))
            for from_, to in inserts:
                out_list = outgoing[from_]
                out_list.discard(node)
                out_list.add(to)

                in_list = incoming[to]
                in_list.discard(node)
                in_list.add(from_)
            incoming.pop(node)
            outgoing.pop(node)
            edges.update(inserts)
            edges = edges.difference(removes)
    return edges


def node_list_to_edges(
    nodes: Iterable[Node],
    start: Node = Nodes.start,
    end: Node = Nodes.end,
) -> Generator[Edge, None, None]:
    prev = start
    for node in nodes:
        yield (prev, node)
        prev = node
    yield (prev, end)


# State is something like a CRDT
@dataclass(slots=True, frozen=True)
class State(object):
    nodes: PVector[bool]
    edges: PSet[Edge]
    max_node: int
    history: PVector[Change]

    @classmethod
    def from_graph(cls, nodes: Iterable[bool], edges: Iterable[Edge]):
        # TODO add consistency check
        nodes = pvector(nodes)
        return cls(nodes, pset(edges), len(nodes) - 1, pvector())

    @classmethod
    def from_file(cls, file_: FileRepr):
        node_list = file_.node_list
        max_node = -1
        if node_list:
            max_node = max(node_list)
            nodes = pvector([False] * (max_node + 1))
        else:
            nodes = pvector()
        for i in node_list:
            nodes = nodes.set(i, True)
        return cls(nodes, pset(node_list_to_edges(node_list)), max_node, pvector())

    def to_file(self) -> FileRepr:
        edges = collect_deleted_nodes(self.edges, self.nodes)
        edges = get_outgoing(edges)
        node_list = edges_to_node_list(edges)
        return FileRepr(pvector(node_list))

    def has_conflict(self) -> bool:
        raise NotImplementedError()

    def delete(self, change: Delete) -> State:
        return State(
            self.nodes.set(change.line, False),
            self.edges,
            self.max_node,
            self.history.append(change),
        )

    def insert(self, change: Insert) -> State:
        nodes = self.nodes
        lines = change.lines
        assert min(lines) > self.max_node
        max_node = max(lines)
        nodes = nodes.extend([False] * (max_node - self.max_node))
        assert max_node <= len(nodes)
        for line in lines:
            nodes = nodes.set(line, True)
        inserts = list(
            node_list_to_edges(
                lines,
                change.predecessor,
                change.successor,
            )
        )
        edges = self.edges
        try:
            edges = edges.remove((change.predecessor, change.successor))
        except KeyError:
            pass
        edges = edges.update(inserts)
        return State(nodes, edges, max_node, self.history.append(change))


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

    def __attrs_post_init__(self):
        assert self.line != Nodes.end
        assert self.line != Nodes.start

    def apply(self, state: State) -> State:
        return state.delete(self)
