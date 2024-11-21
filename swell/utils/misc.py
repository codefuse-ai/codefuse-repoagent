import pickle
import random
import time
import traceback
from collections import OrderedDict

import joblib


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


def save_object(obj, path):
    joblib.dump(obj, path)
    with open(path, "wb") as fou:
        joblib.dump(obj, fou)


def load_object(path):
    joblib.load(path)
    with open(path, "rb") as fin:
        return pickle.load(fin)


def ordered_set(array: list) -> set:
    return OrderedDict.fromkeys([x for x in array])
