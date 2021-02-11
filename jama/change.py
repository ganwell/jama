from difflib import SequenceMatcher
from typing import Any, Optional

from attr import dataclass


def get_diff(a, b):
    return SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()


@dataclass(slots=True)
class File(object):
    graph: list[int]


@dataclass(slots=True)
class FileMock(File):
    max_uid: int

    @classmethod
    def from_size(cls, size):
        return cls(list(range(size)), size)

    def __len__(self):
        return len(self.graph)

    def insert(self, offset, size):
        if offset < 0 or offset > len(self):
            raise IndexError()
        graph = self.graph
        uid = self.max_uid
        if size == 0:
            return FileMock(list(graph), uid)
        graph = graph[:offset] + list(range(uid, uid + size)) + graph[offset:]
        return FileMock(graph, self.max_uid + size)

    def delete(self, offset, size):
        graph = self.graph
        return FileMock(graph[:offset] + graph[offset + size :], self.max_uid)


# TODO use this when it is supported
# DAG = Union[tuple[int, bool], list["DAG"]]
DAG = Any


@dataclass(slots=True)
class State(object):
    graph: list[DAG]

    @classmethod
    def from_file(cls, file_: File):
        raise NotImplementedError()

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


@dataclass(slots=True)
class Insert(Change):
    predecessor: Optional[int]
    lines: list[int]
    successor: Optional[int]


@dataclass(slots=True)
class Delete(Change):
    line: int
