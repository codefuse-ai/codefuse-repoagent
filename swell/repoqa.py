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

```
{context}
```

## User Query ##

\"\"\"
{query}
\"\"\"

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


G1_SYSTEM_PROMPT = """\
You are an expert AI assistant that explains your reasoning step by step. \
For each step, provide a title that describes what you're doing in that step, \
along with the content. Decide if you need another step or if you're ready to give the final answer. \
Respond in JSON format with 'title', 'content', and 'next_action' (either 'continue' or 'final_answer') keys. \
USE AS MANY REASONING STEPS AS POSSIBLE. AT LEAST 3. BE AWARE OF YOUR LIMITATIONS AS AN LLM AND \
WHAT YOU CAN AND CANNOT DO. IN YOUR REASONING, INCLUDE EXPLORATION OF ALTERNATIVE ANSWERS. \
CONSIDER YOU MAY BE WRONG, AND IF YOU ARE WRONG IN YOUR REASONING, WHERE IT WOULD BE. \
FULLY TEST ALL OTHER POSSIBILITIES. YOU CAN BE WRONG. WHEN YOU SAY YOU ARE RE-EXAMINING, ACTUALLY RE-EXAMINE, \
AND USE ANOTHER APPROACH TO DO SO. DO NOT JUST SAY YOU ARE RE-EXAMINING. \
USE AT LEAST 3 METHODS TO DERIVE THE ANSWER. USE BEST PRACTICES.

Example of a valid JSON response:

```json
{
    "title": "Identifying Key Information",
    "content": "To begin solving this problem, we need to carefully examine the given information and identify the crucial elements that will guide our solution process. This involves...",
    "next_action": "continue"
}```
"""

G1_USER_PROMPT = """\
Below is my query that you're about to explain and answer (my query is against the codebase "{repo}"):

\"\"\"
{query}
\"\"\"

Below are some code segments that I obtained from the codebase and that might be helpful to explain and answer my query:

```
{context}
```

"""

G1_ASSISTANT_PROMPT = """\
Thank you! I will now think step by step following my instructions, \
starting at the beginning after decomposing the problem.\
"""

G1_FINAL_PROMPT = """\
Please provide the final answer based solely on your reasoning above. \
Do not use JSON formatting. Only provide the text response without any titles or preambles. \
Retain any formatting as instructed by the original prompt, such as exact formatting for \
free response or multiple choice.\
"""


class G1:
    """This resembles to https://github.com/bklieger-groq/g1"""

    def __init__(self, use_llm: LLMConfig, max_chat_round: int = 25):
        self.llm = LLMFactory.create(use_llm)
        self.max_chat_round = max_chat_round

    def respond(self, query: str, *, context: str, repo: str) -> str:
        self.llm.clear_history()
        self.llm.append_system_message(G1_SYSTEM_PROMPT)
        self.llm.append_user_message(
            G1_USER_PROMPT.format(query=query, context=context, repo=repo)
        )
        self.llm.append_assistant_message(G1_ASSISTANT_PROMPT)

        resp = ""

        for _ in range(self.max_chat_round):
            try:
                step, error = AgentBase.parse_json_response(self.llm.query())
                if error:
                    self.llm.history.pop()
            except Exception:
                continue

            resp += f"## {step['title']}\n\n"
            resp += f"{step['content']}\n\n"

            if step["next_action"] == "final_answer":
                break

        self.llm.append_user_message(G1_FINAL_PROMPT)
        resp += "## Final Answer\n\n"
        resp += self.llm.query()

        return resp


class _Generator(GeneratorBase):
    def __init__(self, use_g1: bool = False):
        super().__init__()
        self.use_g1 = use_g1

    def generate(self, query: str, context: List[str], **kwargs) -> str:
        assert self.agent, "RepoAgent hasn't been injected. Please invoke inject_agent() before calling this method"
        agent = cast(RepoAgent, self.agent)
        gen_cls = G1 if self.use_g1 else RespGen
        resp = gen_cls(agent.use_llm).respond(
            query,
            context="\n\n".join(
                [
                    f"/// {sp}\n"
                    f"{agent.repo.get_snippet_content(sp, add_lines=True, add_separators=False)}"
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
    parser.add_argument(
        "--enable-g1",
        "-g1",
        action="store_true",
        help="Leverage G1 to answer the user query step by step",
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
        generator=_Generator(use_g1=args.enable_g1),
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
