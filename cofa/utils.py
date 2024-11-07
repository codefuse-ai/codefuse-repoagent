import pickle
import random
import re
import time
import traceback
from abc import abstractmethod
from typing import Protocol, Dict, List, Optional, TypeVar, Generic

import joblib
from intervaltree import IntervalTree


class CannotReachHereError(RuntimeError):
    def __init__(self, msg):
        super().__init__(msg)


# TODO: Consider using jd/tenacity
def robust_call(retry=2, sleep=10):
    def _robust_call(fn):
        def _function(*args, **kwargs):
            exception = None
            for _ in range(retry):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    exception = e
                    traceback.print_exc()
                    time.sleep(random.randint(1, sleep))
            raise exception

        return _function

    return _robust_call


def to_bool(s):
    if isinstance(s, bool):
        return s
    elif isinstance(s, str):
        return s.lower() in ["true", "y", "yes", "1"]
    else:
        return bool(s)


class EventReceiver(Protocol):
    @abstractmethod
    def __call__(self, **kwargs):
        pass


class EventEmitter:
    def __init__(self):
        self.event_receivers: Dict[str, List[EventReceiver]] = {}

    def on(self, event: str, receiver: EventReceiver):
        if event not in self.event_receivers:
            self.event_receivers[event] = []
        self.event_receivers[event].append(receiver)

    def emit(self, event, **kwargs):
        for recv in self.event_receivers.get(event, []):
            recv(**kwargs)


def save_object(obj, path):
    joblib.dump(obj, path)
    with open(path, "wb") as fou:
        joblib.dump(obj, fou)


def load_object(path):
    joblib.load(path)
    with open(path, "rb") as fin:
        return pickle.load(fin)


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


def merge_overlapping_intervals(intervals):
    iv_tree = IntervalTree.from_tuples(intervals)
    iv_tree.merge_overlaps()
    intervals = [(iv.begin, iv.end) for iv in iv_tree]
    intervals.sort()
    return intervals


_PATTERN_PHONE_NUMBER = re.compile(
    r"(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)
_PATTERN_EMAIL_ADDRESS = re.compile(r"\b[\w\-.+]+@(?:[\w-]+\.)+[\w-]{2,4}\b")
_PATTERN_PASSWORD = re.compile(
    r'["\']?password["\']?\s*[=:]\s*["\']?[\w_]+["\']?', flags=re.IGNORECASE
)


def sanitize_content(content):
    content = _PATTERN_EMAIL_ADDRESS.sub("<anonymous_email_address>", content)
    content = _PATTERN_PHONE_NUMBER.sub("<anonymous_phone_number>", content)
    content = _PATTERN_PASSWORD.sub("<password_mask>", content)
    return content
