from difflib import SequenceMatcher
from typing import Union

from attr import dataclass


def get_diff(a, b):
    return SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()


@dataclass(slots=True)
class File:
    graph: list[Union[int, tuple[int]]]
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
            return File(list(graph), uid)
        graph = graph[:offset] + list(range(uid, uid + size)) + graph[offset:]
        return File(graph, self.max_uid + size)

    def delete(self, offset, size):
        graph = self.graph
        return File(graph[:offset] + graph[offset + size :], self.max_uid)


@dataclass(slots=True)
class Change:
    @classmethod
    def from_diff(cls, a: File, b: File):
        return get_diff(a.graph, b.graph)
