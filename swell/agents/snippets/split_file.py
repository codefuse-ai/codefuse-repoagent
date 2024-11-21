from typing import Tuple, Generator

from swell.agents.snippets.base import SnipFinderBase, SnipRelDetmBase
from swell.repo.repo import Repository
from swell.utils.parallel import parallel


class EnumSnipFinder(SnipFinderBase):
    def __init__(self, repo: Repository, determ: SnipRelDetmBase):
        super().__init__(repo, determ)

    def find(
        self,
        query: str,
        file_path: str,
        num_threads: int = 4,
        snippet_size: int = 100,
        *args,
        **kwargs,
    ) -> Generator[Tuple[str, str], None, None]:
        need_disable_enable_debugging = num_threads > 1 and self.determ.is_debugging()

        if need_disable_enable_debugging:
            self.determ.disable_debugging()

        snippets = self.repo.get_all_snippets_of_file_with_size(
            file_path, snippet_size=snippet_size
        )

        results = parallel(
            [(self._determ_relevance, (query, snip_path)) for snip_path in snippets],
            n_jobs=num_threads,
            backend="threading",
        )

        if need_disable_enable_debugging:
            self.determ.enable_debugging()

        yield from [
            (snip_path, rel_reason)
            for snip_path, (is_relevant, rel_reason) in results
            if is_relevant
        ]

    def _determ_relevance(self, query: str, snip_path: str):
        return snip_path, self.determ.determine(
            query,
            snip_path,
            self.repo.get_snippet_content(
                snip_path, surroundings=0, add_lines=True, add_separators=True
            ),
        )
