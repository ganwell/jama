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
DAG = Any


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
    @classmethod
    def from_diff(cls, a: File, b: File):
        ag = a.graph
        bg = b.graph
        for ct, l, m, x, y in get_diff(ag, bg):
            if ct == "insert":
                pre = None
                suc = None
                if l:
                    pre = ag[l - 1]
                if l != len(ag):
                    suc = ag[l]
                yield Insert(pre, bg[x:y], suc)
            elif ct == "delete":
                for line in ag[l:m]:
                    yield Delete(line)
            elif ct == "replace":
                for line in ag[l:m]:
                    yield Delete(line)
                pre = None
                suc = None
                if l:
                    pre = ag[l - 1]
                if m != len(ag):
                    suc = ag[m]
                yield Insert(pre, bg[x:y], suc)


@dataclass(slots=True)
class Insert(Change):
    predecessor: Optional[int]
    lines: list[int]
    successor: Optional[int]


@dataclass(slots=True)
class Delete(Change):
    line: int
