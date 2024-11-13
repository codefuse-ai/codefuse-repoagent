from typing import List, Tuple

from joblib import Parallel, delayed


def parallel(fn_and_args: List[Tuple[any, tuple]], n_jobs: int, backend="locky") -> any:
    return Parallel(n_jobs=n_jobs, backend=backend)(
        delayed(x[0])(*x[1]) for x in fn_and_args
    )
