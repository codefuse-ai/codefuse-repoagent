from typing import Optional, Tuple

from cofa.agents.base import AgentBase
from cofa.agents.snippets.base import SnipRelDetmBase
from cofa.base.paths import SnippetPath
from cofa.llms.base import LLMBase

SYSTEM_PROMPT = """\
You are a Snippet Relevance Scorer, tasked to determine if a given "File Snippet" is relevant to a given "User Query", \
and give a relevance score according to your determination. \
And the file snippet is considered to be relevant to the user query if it can be used to address the user query.

For this task, I will provide you with a "File Snippet" which is a portion of the file **{file_name}**, and a "User Query". \
The file snippet lists the content of the snippet; \
it is a portion of a file, wrapped by "===START OF SNIPPET===" and "===END OF SNIPPET===". \
We also provide some lines of surrounding content of the snippet in its file for your reference.

A file snippet is relevant to a user query if the file snippet can be an important part to address the user query \
(though it might not address the user query directly). \
You should determine their relevance by the following steps:
1. Think carefully what files are required to address the user query;
2. Analyze if the file snippet is part of those files and what the snippet provides or what the file snippet does;
3. Check if the file snippet can provide some useful information to address the user query directly or indirectly;
4. Conclude if the file snippet are relevant to the user query and give a relevance score.

The relevance score (an integer chosen from [0, 1, 2, 3]) represents the relevance of the file snippet and the user query, where
- Score 0: The file snippet is totally irrelevant to the user query; it does not help anything to address the user query.
- Score 1: The file snippet is weakly relevant to the user query, but the user query can be addressed even without it.
- Score 2: The file snippet is relevant to the user query; the user query can only be partially addressed without it.
- Score 3: The file snippet is strongly relevant to the user query, and the user query relies on it can never be addressed without it.

## User Query ##

```
{user_query}
```

## File Snippet ##

```
//// Snippet: {snippet_path}
{file_snippet}
```

"""

JSON_SCHEMA = """\
{
    "score": <score>, // the relevance score; it should be an integer chosen from [0, 1, 2, 3]
    "reason": "the reason why you give the relevance score" // explain in detail, step-by-step, the relevance between the file snippet and the user query
}\
"""

NON_INTEGER_SCORE_MESSAGE = """\
**FAILURE**: The relevance score ({score}) you gave is NOT an integer.

The relevance score must be an integer chosen from [0, 1, 2, 3], where:
- Score 0: The file snippet is totally irrelevant to the user query; it does not help anything to address the user query.
- Score 1: The file snippet is weakly relevant to the user query, but the user query can be addressed even without it.
- Score 2: The file snippet is relevant to the user query; the user query can only be partially addressed without it.
- Score 3: The file snippet is strongly relevant to the user query, and the user query relies on it can never be addressed without it.

## Your Response (JSON format) ##

"""

INVALID_SCORE_VALUE_MESSAGE = """\
**FAILURE**: The relevance score ({score}) you gave is NOT chosen from [0, 1, 2, 3].

The relevance score must be an integer chosen from [0, 1, 2, 3], where:
- Score 0: The file snippet is totally irrelevant to the user query; it does not help anything to address the user query.
- Score 1: The file snippet is weakly relevant to the user query, but the user query can be addressed even without it.
- Score 2: The file snippet is fairly relevant to the user query; the user query can only be partially addressed without it.
- Score 3: The file snippet is strongly relevant to the user query, and the user query relies on it can never be addressed without it.

## Your Response (JSON format) ##

"""

SCORE_IRRELEVANCE = 0
SCORE_WEAK_RELEVANCE = 1
SCORE_FAIR_RELEVANCE = 2
SCORE_STRONG_RELEVANCE = 3


class SnipScorer(SnipRelDetmBase, AgentBase):
    def __init__(
        self,
        llm: LLMBase,
        threshold: int = SCORE_WEAK_RELEVANCE,  # inclusive
        *args,
        **kwargs,
    ):
        AgentBase.__init__(self, llm=llm, json_schema=JSON_SCHEMA, *args, **kwargs)
        self.threshold = threshold

    def is_debugging(self) -> bool:
        return AgentBase.is_debugging(self)

    def enable_debugging(self):
        AgentBase.enable_debugging(self)

    def disable_debugging(self):
        AgentBase.disable_debugging(self)

    def determine(
        self, query: str, snippet_path: str, snippet_content: str, *args, **kwargs
    ) -> Tuple[bool, str]:
        score, reason = self.score(query, snippet_path, snippet_content)
        if score >= self.threshold:
            return True, (
                f"The snippet is considered relevant to the user query as: "
                f"the score of the snippet ({score}) is within our threshold ({self.threshold}). "
                f"The reason for giving the score ({score}) is: " + reason
            )
        else:
            return False, (
                f"The snippet is considered irrelevant to the user query as: "
                f"the score of the snippet ({score}) is beyond our threshold ({self.threshold}). "
                f"The reason for giving the score ({score}) is: " + reason
            )

    def score(
        self, query: str, snippet_path: str, snippet_content: str
    ) -> Tuple[int, str]:
        return self.run(
            SYSTEM_PROMPT.format(
                file_name=SnippetPath.from_str(snippet_path).file_path.name,
                user_query=query,
                snippet_path=snippet_path,
                file_snippet=snippet_content,
            )
        )

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        for field in ["score", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        try:
            score = int(response["score"])
        except ValueError:
            return False, NON_INTEGER_SCORE_MESSAGE.format(score=response["score"])
        if score not in [0, 1, 2, 3]:
            return False, INVALID_SCORE_VALUE_MESSAGE.format(score=score)
        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        return int(response["score"]), response["reason"]

    def _default_result_when_reaching_max_chat_round(self):
        return (
            SCORE_IRRELEVANCE,
            "The model have reached the max number of chat round and is unable to score their relevance.",
        )
