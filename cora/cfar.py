from argparse import ArgumentParser
from pathlib import Path
from typing import List, Optional

from cora import options, results
from cora.agents.rewrite.base import RewriterBase
from cora.agents.rewrite.dont import DontRewrite
from cora.agents.rewrite.issue import IssueSummarizer
from cora.base.console import get_boxed_console
from cora.config import CoraConfig
from cora.llms.factory import LLMConfig
from cora.repo.repo import Repository
from cora.retrv import retrv


def retrieve(
    query: str,
    repo: Repository,
    *,
    use_llm: LLMConfig,
    rewriter: Optional[RewriterBase] = None,
    files_only: bool = False,
    num_proc: int = 1,
    includes: Optional[List[str]] = None,
    debug_mode: bool = False,
    log_dir: Optional[Path] = None,
) -> List[str]:
    console = get_boxed_console(
        box_title="CFAR",
        box_bg_color=retrv.DEBUG_OUTPUT_LOGGING_COLOR,
        debug_mode=debug_mode,
    )

    console.printb(
        f"Loaded repository {repo.repo_org}/{repo.repo_name} from {repo.repo_path} ..."
    )

    console.printb(f"Retrieving relevant context for query:\n```\n{query}\n```")
    retriever = retrv.Retriever(
        repo,
        use_llm=use_llm,
        includes=includes,
        debug_mode=debug_mode,
        rewriter=rewriter,
    )

    if log_dir:
        retriever.add_callback(results.CfarResult(log_dir / "cfar_res.json"))

    snip_ctx = retriever.retrieve(
        query,
        files_only=files_only,
        num_proc=num_proc,
    )
    console.printb(
        "The retrieved context is:\n" + ("\n".join(["- " + sp for sp in snip_ctx]))
    )

    return snip_ctx


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
    CoraConfig.SCR_ENUM_FNDR_NUM_THREADS = threads
    log_dir, verbose = options.parse_logging(args)

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
        log_dir=log_dir,
        debug_mode=verbose,
    )


if __name__ == "__main__":
    main()
