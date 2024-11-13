from typing import List, Optional

import retr.retriever as cfar
from cofa.agents.rewrite.base import RewriterBase
from cofa.base.console import get_boxed_console
from cofa.base.repos import RepoTup
from cofa.llms.factory import LLMConfig
from cofa.repo.repo import Repository


def retrieve(
    query: str,
    repo: RepoTup,
    *,
    use_llm: LLMConfig,
    rewriter: Optional[RewriterBase] = None,
    files_only: bool = False,
    num_proc: int = 1,
    excluded_patterns: Optional[List[str]] = None,
    included_patterns: Optional[List[str]] = None,
) -> List[str]:
    console = get_boxed_console(
        box_title=cfar.DEBUG_OUTPUT_LOGGING_TITLE,
        box_bg_color=cfar.DEBUG_OUTPUT_LOGGING_COLOR,
        debug_mode=True,
    )

    console.printb(f"Loading repository {repo.org}/{repo.name} from {repo.path} ...")
    repo = Repository(repo, excludes=excluded_patterns)

    console.printb(f"""Retrieving relevant context for query:\n```\n{query}\n```""")
    retr = cfar.Retriever(
        repo,
        use_llm=use_llm,
        includes=included_patterns,
        debug_mode=True,
        rewriter=rewriter,
    )

    return retr.retrieve(
        query,
        files_only=files_only,
        num_proc=num_proc,
    )
