from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any, Optional

from attr import dataclass
from pyrsistent import ny, pvector
from pyrsistent.typing import PVector


class InconsistentError(Exception):
    pass


def get_diff(a, b):
    return SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()


@dataclass(slots=True)
class File(object):
    graph: PVector[int]

    @classmethod
    def from_iterable(cls, iterable: Iterable):
        return cls(pvector(iterable))


@dataclass(slots=True)
class FileEdit(File):
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
            return FileEdit(list(graph), uid)
        graph = graph[:offset] + list(range(uid, uid + size)) + graph[offset:]
        return FileEdit(graph, self.max_uid + size)

    def delete(self, offset, size):
        graph = self.graph
        return FileEdit(graph[:offset] + graph[offset + size :], self.max_uid)


# TODO use this when it is supported
# DAG = Union[tuple[int, bool], PVector["DAG"]]
DAG = PVector[Any]


@dataclass(slots=True)
class State(object):
    graph: PVector[DAG]

    @classmethod
    def from_file(cls, file_: File):
        return cls(file_.graph.transform([ny], lambda x: (x, True)))

    def has_conflict(self) -> bool:
        raise NotImplementedError()


@dataclass(slots=True)
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
    def from_diff(cls, a: File, b: File):
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


@dataclass(slots=True)
class Insert(Change):
    predecessor: Optional[int]
    lines: PVector[int]
    successor: Optional[int]


@dataclass(slots=True)
class Delete(Change):
    line: int

    def delete(self, graph: DAG, line: int, count: int):
        for i, item in enumerate(graph):
            if isinstance(item, list):
                count += self.delete(graph, line, count)
            elif isinstance(item, tuple):
                if item[0] == line:
                    graph = graph.set(i, (line, False))
                    count += 1
            else:
                raise InconsistentError()
        return graph, count

    def apply(self, state: State) -> State:
        graph = state.graph
        graph, count = self.delete(graph, self.line, 0)
        if count > 1:
            raise InconsistentError()
        return State(graph)
