from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Generator, Iterable, Optional, cast

import attr
import pyrsistent
from attr import dataclass
from pyrsistent import discard, ny, pset, pvector
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
    graph: PVector[int]

    graph = cast(PVector[int], attr.ib(converter=pvector))


@dataclass(slots=True, frozen=True)
class FileReprEdit(FileRepr):
    max_uid: int

    @classmethod
    def from_size(cls, size):
        return cls(pvector(range(size)), size)

    def __len__(self):
        return len(self.graph)

    def insert(self, offset, size):
        if offset < 0 or offset > len(self):
            raise IndexError()
        graph = self.graph
        uid = self.max_uid
        if size == 0:
            return FileReprEdit(list(graph), uid)
        graph = graph[:offset] + list(range(uid, uid + size)) + graph[offset:]
        return FileReprEdit(graph, self.max_uid + size)

    def delete(self, offset, size):
        graph = self.graph
        return FileReprEdit(graph[:offset] + graph[offset + size :], self.max_uid)


# TODO use this when it is supported
# DAG = PVector[Union["DAG", tuple[int, bool]]]
DAG = PVector[Any]


def node_list_to_edges(
    nodes: Iterable[int],
) -> Generator[tuple[Optional[int], int], None, None]:
    prev = None
    for node in nodes:
        yield ((prev, node))
        prev = node


def node_list_to_edge_set(nodes: Iterable[int]) -> PSet[tuple[Optional[int], int]]:
    return pset(node_list_to_edges(nodes))


def transform_into_state(graph: PVector[int]) -> DAG:
    return graph.transform([ny], lambda x: (x, True))


def transform_into_file(graph: PVector[DAG]) -> PVector[int]:
    return cast(
        PVector[int],
        graph.transform([lambda i, v: not v[1]], discard).transform(
            [ny], lambda x: x[0]
        ),
    )


# State is something like CRDT
@dataclass(slots=True, frozen=True)
class State(object):
    graph: PVector[DAG]
    # I think the new representation of the state is fully idempotent and no history is neede
    # at least no the history_set.
    history: PVector[Change] = cast(PVector["Change"], attr.ib(default=pvector()))
    history_set: PSet[Change] = cast(PSet["Change"], attr.ib(default=pset()))

    @classmethod
    def from_file(cls, file_: FileRepr):
        return cls(transform_into_state(file_.graph))

    def record(self, graph: PVector[DAG], change: Change):
        return State(graph, self.history.append(change), self.history_set.add(change))

    def to_file(self) -> FileRepr:
        return FileRepr(transform_into_file(self.graph))

    def is_applied(self, change: Change):
        return change in self.history_set

    def has_conflict(self) -> bool:
        raise NotImplementedError()


@dataclass(slots=True, frozen=True)
class Change(object):
    def apply(self, state: State) -> State:
        raise NotImplementedError()

    @classmethod
    def pre_suc(_, ag, left, right):
        pre = None
        suc = None
        if left:
            pre = ag[left - 1]
        if right != len(ag):
            suc = ag[right]
        return pre, suc

    @classmethod
    def from_diff(cls, a: FileRepr, b: FileRepr):
        a_graph = a.graph
        b_graph = b.graph
        for ct, a_left, a_right, b_left, b_right in get_diff(a_graph, b_graph):
            if ct == "insert":
                pre, suc = cls.pre_suc(a_graph, a_left, a_left)
                yield Insert(pre, b_graph[b_left:b_right], suc)
            elif ct == "delete":
                for line in a_graph[a_left:a_right]:
                    yield Delete(line)
            elif ct == "replace":
                for line in a_graph[a_left:a_right]:
                    yield Delete(line)
                pre, suc = cls.pre_suc(a_graph, a_left, a_right)
                yield Insert(pre, b_graph[b_left:b_right], suc)


@dataclass(slots=True, frozen=True)
class Insert(Change):
    predecessor: Optional[int]
    lines: PVector[int]
    successor: Optional[int]

    lines = cast(PVector[int], attr.ib(converter=pvector))

    def __attrs_post_init__(self):
        assert len(self.lines) > 0
        if not (self.predecessor is None and self.successor is None):
            assert self.predecessor != self.successor

    def insert(self, graph: DAG, lines: PVector[int]):
        count = 0
        s_pre = self.predecessor
        s_suc = self.successor
        pre = None
        suc = None
        for i, item in enumerate(graph):
            if isinstance(item, pyrsistent.PVector):
                r_graph, r_count = self.insert(item, lines)
                count += r_count
                graph = graph.set(i, r_graph)
                continue
            if item[0] == s_pre:
                pre = i + 1
            elif item[0] == s_suc:
                suc = i
        if s_pre is None:
            pre = 0
        if s_suc is None:
            suc = len(graph)
        if pre is None or suc is None:
            return graph, count
        repl = graph[pre:suc]
        new = transform_into_state(lines)
        if not repl:
            return graph[:pre] + new + graph[suc:], count + 1
        else:
            # TODO: this creates a binary branch. maybe we could use a marker to find pure
            # branching nodes and extend them instead of chaining binary branches.
            return (
                graph[:pre] + pvector([pvector([repl, new])]) + graph[suc:],
                count + 1,
            )

    def apply(self, state: State) -> State:
        if state.is_applied(self):
            return state
        graph, count = self.insert(state.graph, self.lines)
        if count != 1:
            raise InconsistentError()
        return state.record(graph, self)


@dataclass(slots=True, frozen=True)
class Delete(Change):
    line: int

    def delete(self, graph: DAG, line: int):
        count = 0
        for i, item in enumerate(graph):
            if isinstance(item, pyrsistent.PVector):
                r_graph, r_count = self.delete(item, line)
                count += r_count
                graph = graph.set(i, r_graph)
            elif isinstance(item, tuple):
                if item[0] == line:
                    graph = graph.set(i, (line, False))
                    count += 1
            else:
                raise InconsistentError()
        return graph, count

    def apply(self, state: State) -> State:
        if state.is_applied(self):
            return state
        graph, count = self.delete(state.graph, self.line)
        if count != 1:
            raise InconsistentError()
        return state.record(graph, self)
