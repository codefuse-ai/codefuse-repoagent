from argparse import ArgumentParser
from typing import List, Optional

import cofa.retr.retriever as cfar
from cofa import options
from cofa.agents.rewrite.base import RewriterBase
from cofa.agents.rewrite.dont import DontRewrite
from cofa.agents.rewrite.issue import IssueSummarizer
from cofa.base.console import get_boxed_console
from cofa.config import CofaConfig
from cofa.llms.factory import LLMConfig
from cofa.repo.repo import Repository


def retrieve(
    query: str,
    repo: Repository,
    *,
    use_llm: LLMConfig,
    rewriter: Optional[RewriterBase] = None,
    files_only: bool = False,
    num_proc: int = 1,
    includes: Optional[List[str]] = None,
) -> List[str]:
    console = get_boxed_console(
        box_title=cfar.DEBUG_OUTPUT_LOGGING_TITLE,
        box_bg_color=cfar.DEBUG_OUTPUT_LOGGING_COLOR,
        debug_mode=True,
    )

    console.printb(
        f"Loaded repository {repo.repo_org}/{repo.repo_name} from {repo.repo_path} ..."
    )

    console.printb(f"""Retrieving relevant context for query:\n```\n{query}\n```""")
    retr = cfar.Retriever(
        repo,
        use_llm=use_llm,
        includes=includes,
        debug_mode=True,
        rewriter=rewriter,
    )

    return retr.retrieve(
        query,
        files_only=files_only,
        num_proc=num_proc,
    )


def parse_args():
    parser = ArgumentParser()
    options.make_common_options(parser)
    parser.add_argument(
        "--files-only",
        "-F",
        action="store_true",
        help="Only retrieve relevant files other than snippets",
    )
    parser.add_argument(
        "--query-as-issue",
        action="store_true",
        help="Treat the user query as a GitHub issue to resolve",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    repo = options.parse_repo(args)
    query, incl = options.parse_query(args)

    llm = options.parse_llms(args)

    procs, threads = options.parse_perf(args)
    CofaConfig.SCR_ENUM_FNDR_NUM_THREADS = threads

    if args.query_as_issue:
        rewriter = IssueSummarizer(repo, use_llm=llm)
    else:
        # TODO: Add a common rewriter to summarize a query or let LLM decide if a query is an issue
        rewriter = DontRewrite(repo)

    retrieve(
        query,
        repo,
        use_llm=llm,
        num_proc=procs,
        includes=incl,
        files_only=args.files_only,
        rewriter=rewriter,
    )


if __name__ == "__main__":
    main()
