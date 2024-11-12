from pathlib import Path
from typing import Optional, List

from cofa.base.paths import SnippetPath
from cofa.base.repos import RepoBase, RepoTup
from cofa.config import CofaConfig
from cofa.kwe.engine import KwEng
from cofa.kwe.tokens import NGramTokenizer
from cofa.utils import match_any_pattern


class Repository(RepoBase):
    def __init__(self, repo: RepoTup, *, excludes: Optional[List[str]] = None):
        super().__init__(repo, excludes=excludes)
        self._kw_engine = None

    def search_snippets(
        self,
        query: str,
        limit: Optional[int] = 10,
        includes: Optional[List[str]] = None,
        *args,
        **kwargs,
    ) -> List[str]:
        self._ensure_keyword_engine_loaded()
        snippets = []
        for s in self._kw_engine.search_snippets(query, limit=None):
            if (not includes) or match_any_pattern(s, includes):
                snippets.append(s)
            if limit and len(snippets) == limit:
                break
        return snippets

    def search_files(
        self,
        query,
        limit: Optional[int] = 10,
        includes: Optional[List[str]] = None,
        *args,
        **kwargs,
    ) -> List[str]:
        # Let's assume the top 32*limit snippets must contain top limit files
        files = []
        for s in self.search_snippets(
            query,
            limit=None,  # Let's search for all snippets
            includes=None,  # Let's filter files ourselves
            *args,
            **kwargs,
        ):
            f = str(SnippetPath.from_str(s).file_path)
            if (f not in files) and (not includes or match_any_pattern(f, includes)):
                files.append(f)
            if limit and len(files) == limit:
                break
        return files

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
