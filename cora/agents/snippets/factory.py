from typing import List, Optional, Dict, Type

from cora.agents.snippets.base import SnipFinderBase, SnipRelDetmBase
from cora.agents.snippets.judge_snip import SnipJudge
from cora.agents.snippets.prev_file import PrevSnipFinder
from cora.agents.snippets.score_snip import SnipScorer, SCORE_WEAK_RELEVANCE
from cora.agents.snippets.split_file import EnumSnipFinder
from cora.base.console import BoxedConsoleBase
from cora.base.paths import SnippetPath, FilePath
from cora.config import CoraConfig
from cora.llms.factory import LLMConfig, LLMFactory
from cora.repo.repo import Repository
from cora.utils.interval import merge_overlapping_intervals
from cora.utils.misc import CannotReachHereError


class _SFW:
    def __init__(self, finder: SnipFinderBase, console=None):
        self.finder = finder
        self.console = console

    def enable_debugging(self):
        self.finder.enable_debugging()

    def disable_debugging(self):
        self.finder.disable_debugging()

    def find(self, query: str, file_path: str, *args, **kwargs) -> List[str]:
        snippets = []
        for snippet, reason in self.finder.find(query, file_path, *args, **kwargs):
            if not snippet:
                continue
            self._printb(f"Found {snippet}: {reason}")
            snippets.append(snippet)
        snippet_tuples = []
        for snippet in snippets:
            snippet_path = SnippetPath.from_str(snippet)
            snippet_tuples.append((snippet_path.start_line, snippet_path.end_line))
        merged_tuples = merge_overlapping_intervals(
            snippet_tuples, merge_continuous=True
        )
        return [str(SnippetPath(FilePath(file_path), a, b)) for a, b in merged_tuples]

    def _printb(self, *args, **kwargs):
        if self.console:
            self.console.printb(*args, **kwargs)


class SnipFinderFactory:
    @classmethod
    def create(
        cls,
        name: str,
        repo: Repository,
        *,
        use_llm: LLMConfig,
        use_determ: str,
        determ_args: Optional[Dict] = None,
        console: Optional[BoxedConsoleBase] = None,
    ):
        try:
            ctor = {
                CoraConfig.SCR_SNIPPET_FINDER_NAME_ENUM_FNDR: EnumSnipFinder,
                CoraConfig.SCR_SNIPPET_FINDER_NAME_PREV_FNDR: PrevSnipFinder,
            }[name]
        except KeyError:
            raise CannotReachHereError(f"Unsupported snippet finder: {name}")
        return cls._create_sfw(
            ctor,
            repo,
            use_llm=use_llm,
            use_determ=use_determ,
            determ_args=determ_args,
            console=console,
        )

    @classmethod
    def _create_sfw(
        cls,
        ctor: Type["SnipFinderBase"],
        repo: Repository,
        *,
        use_llm: LLMConfig,
        use_determ: str,
        determ_args: Optional[Dict] = None,
        console: Optional[BoxedConsoleBase] = None,
    ) -> _SFW:
        determ = cls._create_determ(use_determ, use_llm=use_llm, **(determ_args or {}))
        if ctor == PrevSnipFinder:
            finder = PrevSnipFinder(
                llm=LLMFactory.create(use_llm), repo=repo, determ=determ
            )
        elif ctor == EnumSnipFinder:
            finder = EnumSnipFinder(repo=repo, determ=determ)
        else:
            raise CannotReachHereError(f"Unsupported snippet finder: {ctor}")
        return _SFW(finder=finder, console=console)

    @staticmethod
    def _create_determ(determ: str, use_llm: LLMConfig, **kwargs) -> SnipRelDetmBase:
        try:
            return {
                CoraConfig.SCR_SNIPPET_DETERM_NAME_SNIP_SCORER: SnipScorer(
                    LLMFactory.create(use_llm),
                    threshold=kwargs.get("threshold", SCORE_WEAK_RELEVANCE),
                ),
                CoraConfig.SCR_SNIPPET_DETERM_NAME_SNIP_JUDGE: SnipJudge(
                    LLMFactory.create(use_llm),
                ),
            }[determ]
        except KeyError:
            raise CannotReachHereError(f"Unsupported snippet determiner: {determ}")
