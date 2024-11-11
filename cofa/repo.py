from pathlib import Path
from typing import Optional, List

from cofa.base.repos import RepoBase, RepoTup
from cofa.config import CofaConfig
from cofa.kwe.engine import KwEng
from cofa.kwe.tokens import NGramTokenizer


class Repository(RepoBase):
    def __init__(
        self,
        repo: RepoTup,
        *,
        excluded_patterns: Optional[List[str]] = None,
    ):
        super().__init__(repo, excluded_patterns=excluded_patterns)
        self._kw_engine = None

    def search_snippets(self, query, limit: int = 10, *args, **kwargs) -> List[str]:
        self._ensure_keyword_engine_loaded()
        return self._kw_engine.search_snippets(query, limit=limit)

    def _ensure_keyword_engine_loaded(self):
        if self._kw_engine:
            return
        kwe_cache_file = self._kwe_cache_file
        if kwe_cache_file.exists():
            self._kw_engine = KwEng.load_from_disk(kwe_cache_file, self)
        else:
            self._ensure_repository_chunked()
            self._kw_engine = KwEng.from_repo(self, NGramTokenizer())
            self._kw_engine.save_to_disk(kwe_cache_file)

    @property
    def _kwe_cache_file(self) -> Path:
        return CofaConfig.keyword_index_cache_directory() / (
            Path(self.repo_path).name + ".kwe"
        )
