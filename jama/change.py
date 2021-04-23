from enum import IntEnum
from typing import Any, Generator, Iterable, Union, cast

import attr
from attr import dataclass
from pyrsistent import ny, pset, pvector
from pyrsistent.typing import PSet, PVector
from retworkx import PyDAG  # type: ignore


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
        return cls(node_list=[x + FileNodes.content for x in node_list])

    def to_user_repr(self):
        return self.node_list.transform([ny], lambda x: x - FileNodes.content)


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
