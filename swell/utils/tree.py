from abc import abstractmethod
from typing import Protocol, TypeVar, Generic, Optional, List


class TreeNodeVisitor(Protocol):
    @abstractmethod
    def __call__(self, node: "TreeNode"): ...


TreeData = TypeVar("TreeData")


class TreeNode(Generic[TreeData]):
    def __init__(self, data: TreeData, parent: Optional["TreeNode"] = None):
        self.data: TreeData = data
        self.parent: Optional["TreeNode"] = parent
        self.children: List["TreeNode"] = []
        if parent:
            parent.children.append(self)

    def leaves(self) -> List["TreeNode"]:
        leaves = []

        def _visit(node):
            if len(node.children) == 0:
                leaves.append(node)

        self.accept(_visit)

        return leaves

    def detach(self):
        if not self.parent:
            return
        self.parent.children.remove(self)
        self.parent = None

    def accept(self, visitor: TreeNodeVisitor):
        visitor(self)
        for child in self.children:
            child.accept(visitor)
