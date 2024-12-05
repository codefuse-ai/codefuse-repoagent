from typing import Tuple, Optional

from cora.agents.base import AgentBase
from cora.llms.base import LLMBase
from cora.repo.repo import Repository

# TODO: Extract entities first, then try guessing their definition files
SYSTEM_PROMPT = """\
You are a File Name Extractor, tasked to extract all possible **file names** embedded in a "User Query". \
Since your extracted file names will be used by others to solve the user query, it is very important that you do not miss any possible file names.

For this task, I will present you the "User Query", \
which is a question or a request proposed by a user for the repository: {repo_name}. \
To solve the user query, one may need to comprehend the user query and then access or even update some mentioned or not mentioned files in the repository. \
So it is important that we should find all the specific files. \
Your task is to comprehend analyze the user query in detail, and try finding all possible file names embedded in the user query.

Note,
1. There might be multiple file names embedded in the query, you should find all of them.
2. If you cannot find all any file names in the user query, leave the field "files" as an empty array ([]) and give a clear "reason" to let me know.

## User Query ##

```
{user_query}
```

"""

JSON_SCHEMA = """\
{
    "thoughts": "your comprehension to the user query", // your comprehension to the user query; this should be in very detail and should help you find all possible file names.
    "files": ["<file_name_1>", "<file_name_2>", ...], // all possible file names; or leave this field as an empty array if you cannot find any file names from the user query.
    "reason": "the reason why you think the names you found are file names embedded in the query" // explain step by step and one file name by one file name.
}\
"""


class EntDefnFinder(AgentBase):
    def __init__(
        self,
        query: str,
        repo: Repository,
        llm: LLMBase,
        *args,
        **kwargs,
    ):
        super().__init__(llm=llm, json_schema=JSON_SCHEMA, *args, **kwargs)
        self.query = query
        self.repo = repo

    def find(self):
        return self.run(
            SYSTEM_PROMPT.format(
                repo_name=self.repo.full_name,
                user_query=self.query,
            )
        )

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        for field in ["thoughts", "files", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        names = response["files"]
        reason = response["thoughts"] + "\n" + response["reason"]

        if not names:
            return [], reason

        return names, reason

    def _default_result_when_reaching_max_chat_round(self):
        return (
            [],
            "The model have reached the max number of chat round and is unable to find any files in the query.",
        )
