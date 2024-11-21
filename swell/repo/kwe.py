from pathlib import Path
from typing import Optional, List

from swell.base.paths import SnippetPath
from swell.base.repos import RepoBase
from swell.config import SwellConfig
from swell.kwe.engine import KwEng
from swell.kwe.tokens import NGramTokenizer
from swell.utils.generic import CastSelfToThis
from swell.utils.pattern import match_any_pattern


class KwEngMixin(CastSelfToThis[RepoBase]):
    def __init__(self):
        self._kw_engine = None

    def search_snippets(
        self,
        query: str,
        limit: Optional[int] = 10,
        includes: Optional[List[str]] = None,
    ) -> List[str]:
        self.ensure_keyword_engine_loaded()
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
    ) -> List[str]:
        # Let's assume the top 32*limit snippets must contain top limit files
        files = []
        for s in self.search_snippets(
            query,
            limit=None,  # Let's search for all snippets
            includes=None,  # Let's filter files ourselves
        ):
            f = str(SnippetPath.from_str(s).file_path)
            if (f not in files) and (not includes or match_any_pattern(f, includes)):
                files.append(f)
            if limit and len(files) == limit:
                break
        return files

    def ensure_keyword_engine_loaded(self):
        if self._kw_engine:
            return
        kwe_cache_file = self._kwe_cache_file
        if kwe_cache_file.exists():
            self._kw_engine = KwEng.load_from_disk(kwe_cache_file, self.this)
        else:
            self.this.ensure_repository_chunked()
            self._kw_engine = KwEng.from_repo(self.this, NGramTokenizer())
            self._kw_engine.save_to_disk(kwe_cache_file)

    @property
    def _kwe_cache_file(self) -> Path:
        return SwellConfig.keyword_index_cache_directory() / (
            Path(self.this.repo_path).name + ".kwe"
        )
