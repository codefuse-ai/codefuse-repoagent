from argparse import ArgumentParser
from typing import List, cast

from swell import options
from swell.agents.base import AgentBase
from swell.agents.rewrite.dont import DontRewrite
from swell.agents.rewrite.issue import IssueSummarizer
from swell.base.rag import GeneratorBase
from swell.cora import RepoAgent
from swell.llms.factory import LLMConfig, LLMFactory

SYSTEM_PROMPT = """\
## Context ##

{context}

## User Query ##

{query}

## Response Plan ##

1. Read and understand the context provided from the codebase: {repo}.
2. Analyze the user's query to determine the specific information they are seeking.
3. Formulate a response that directly addresses the user's question by referencing the relevant parts of the provided context.
4. Outline the steps or information needed to answer the query in a clear and logical sequence.

## Answer ##

"""


class RespGen(AgentBase):
    def __init__(self, use_llm: LLMConfig):
        super().__init__(LLMFactory.create(use_llm), json_schema=None)

    def respond(self, query: str, *, context: str, repo: str) -> str:
        return self.run(
            system_prompt=SYSTEM_PROMPT.format(query=query, context=context, repo=repo)
        )


class _Generator(GeneratorBase):
    def generate(self, query: str, context: List[str], **kwargs) -> str:
        assert self.agent, "RepoAgent hasn't been injected. Please invoke inject_agent() before calling this method"
        agent = cast(RepoAgent, self.agent)
        resp = RespGen(agent.use_llm).respond(
            query,
            context="\n\n".join(
                [
                    f"/// {sp}\n"
                    f"{agent.repo.get_snippet_content(sp, add_lines=True, add_separators=True)}"
                    for sp in context
                ]
            ),
            repo=agent.repo.full_name,
        )
        agent.console.printb("Response: " + resp)
        return resp


def parse_args():
    parser = ArgumentParser()
    options.make_common_options(parser)
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

    if args.query_as_issue:
        rewriter = IssueSummarizer(repo, use_llm=llm)
    else:
        rewriter = DontRewrite(repo)

    agent = RepoAgent(
        repo=repo,
        use_llm=llm,
        rewriter=rewriter,
        generator=_Generator(),
        includes=incl,
        num_proc=procs,
        num_thread=threads,
        name="RepoQA",
        files_as_context=False,
        debug_mode=args.verbose,
    )
    agent.run(query=query)


if __name__ == "__main__":
    main()
