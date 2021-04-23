from __future__ import annotations

from enum import IntEnum
from typing import Any, Generator, Iterable, Union, cast

import attr
from attr import dataclass
from pyrsistent import ny, pset, pvector
from pyrsistent.typing import PSet, PVector
from retworkx import PyDAG  # type: ignore

Edge = tuple[int, int]


class FileNodes(IntEnum):
    end = -1
    start = -2
    content = 2


@dataclass(slots=True, frozen=True)
class FileRepr(object):
    node_list: PVector[int]

    node_list = cast(PVector[int], attr.ib(converter=pvector))

    @classmethod
    def from_user_repr(cls, node_list):
        return cls([x + FileNodes.content for x in node_list])

    def to_user_repr(self):
        return self.node_list.transform([ny], lambda x: x - FileNodes.content)


@dataclass(slots=True, frozen=True)
class FileReprEdit(FileRepr):
    max_uid: int

    @classmethod
    def from_size(cls, size):
        frepr = FileReprEdit.from_user_repr(pvector(range(size)))
        return cls(frepr.node_list, size + FileNodes.content - 1)

    @classmethod
    def from_user_repr(cls, node_list):
        max_uid = 0
        node_new = []
        for x in node_list:
            x += FileNodes.content
            max_uid = max(max_uid, x)
            node_new.append(x)
        return cls(node_new, max_uid)

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


# State is something like a CRDT
@dataclass(slots=True, frozen=True)
class State(object):
    nodes: PVector[bool]
    edges: PSet[Edge]
    max_node: int
    history: PVector[Change]

    @staticmethod
    def _node_list_to_edges(
        nodes: Iterable[int],
    ) -> Iterable[Edge]:
        content = FileNodes.content
        prev = FileNodes.start + content
        for node in nodes:
            yield (prev, node)
            prev = node
        yield (prev, FileNodes.end + content)

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

        for i in range(FileNodes.content):
            nodes = nodes.set(i, True)
        for i in node_list:
            nodes = nodes.set(i, True)
        return cls(
            nodes, pset(State._node_list_to_edges(node_list)), max_node, pvector()
        )

    def to_user_edges(self) -> Iterable[Edge]:
        c = FileNodes.content
        for e in self.edges:
            yield (e[0] - c, e[1] - c)

    def to_user_nodes(self) -> Iterable[bool]:
        return self.nodes[: FileNodes.content]

    # def to_file(self) -> FileRepr:
    #     edges = collect_deleted_nodes(self.edges, self.nodes)
    #     edges = get_outgoing(edges)
    #     node_list = edges_to_node_list(edges)
    #     return FileRepr(pvector(node_list))

    # def has_conflict(self) -> bool:
    #     raise NotImplementedError()

    # def delete(self, change: Delete) -> State:
    #     return State(
    #         self.nodes.set(change.line, False),
    #         self.edges,
    #         self.max_node,
    #         self.history.append(change),
    #     )


@dataclass(slots=True, frozen=True)
class Change(object):
    pass
