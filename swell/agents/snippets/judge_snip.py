from typing import Optional, Tuple

from swell.agents.base import AgentBase
from swell.agents.snippets.base import SnipRelDetmBase
from swell.base.paths import SnippetPath
from swell.llms.base import LLMBase
from swell.utils.misc import to_bool

SYSTEM_PROMPT = """\
You are a Relevance Determiner, tasked to analyze if a given "File Snippet" is relevant to a given "User Query".

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
4. Conclude if the file snippet are relevant to the user query.

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
    "relevant": "<true_or_false>", // if the file snippet is relevant to the user query; this field is a boolean field, either true or false
    "reason": "the reason why you think the file snippet is relevant to the user query" // explain in detail why you think this snippet is relevant to the user query; explain it step by step following the above steps
}\
"""


class SnipJudge(SnipRelDetmBase, AgentBase):
    def __init__(self, llm: LLMBase, *args, **kwargs):
        AgentBase.__init__(self, llm=llm, json_schema=JSON_SCHEMA, *args, **kwargs)

    def is_debugging(self) -> bool:
        return AgentBase.is_debugging(self)

    def enable_debugging(self):
        AgentBase.enable_debugging(self)

    def disable_debugging(self):
        AgentBase.disable_debugging(self)

    def determine(
        self, query: str, snippet_path: str, snippet_content: str, *args, **kwargs
    ):
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
        for field in ["relevant", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        return to_bool(response["relevant"]), response["reason"]

    def _default_result_when_reaching_max_chat_round(self):
        return (
            False,
            "The model have reached the max number of chat round and is unable to determine their relevance.",
        )
