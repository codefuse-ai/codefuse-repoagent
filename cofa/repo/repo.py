from typing import Optional, List

from cofa.base.repos import RepoBase, RepoTup
from cofa.repo.find import FindMixin
from cofa.repo.kwe import KwEngMixin


class Repository(RepoBase, KwEngMixin, FindMixin):
    def __init__(self, repo: RepoTup, *, excludes: Optional[List[str]] = None):
        RepoBase.__init__(self, repo, excludes=excludes)
        KwEngMixin.__init__(self)
        FindMixin.__init__(self)
