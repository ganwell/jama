from typing import Union

from attr import dataclass


@dataclass
class File:
    graph: list[Union[int, tuple[int]]]
    max_uid: int

    @classmethod
    def from_size(cls, size):
        return cls(list(range(size)), size)

    def __len__(self):
        return len(self.graph)

    def add(self, offset, size):
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
