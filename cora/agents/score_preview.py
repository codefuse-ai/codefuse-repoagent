from typing import Tuple, Optional, List

from cora.agents.base import AgentBase
from cora.llms.base import LLMBase
from cora.preview import FilePreview
from cora.repo.repo import Repository

SYSTEM_PROMPT = """\
## YOUR TASK ##

You are a powerful File Relevance Decider with the capability to analyze and evaluate the relevance of files to the "User Query". \
Your task is to determine the relevance of the file to the "User Query" and give a relevance score according to your determination.

For this task, I will give you the "User Query" and a preview of a file which contains function names and class names. \
The file {file_name} is from the repository: {repo_name}.
Additionally, I will give you a file list which contains some filenames which maybe related to the "User Query". The filelist maybe help you decide the relevance score.

A file is relevant to a user query if the file can be an important part to address the user query \
(though it might not address the user query directly). \
You should determine their relevance by the following steps:
1. Think carefully what files are required to address the user query;
2. Analyze if the file  is part of those files and what the  provides or what the file  does;
3. Check if the file can provide some useful information to address the user query directly or indirectly;
4. Conclude if the file are relevant to the user query and give a relevance score.

The relevance score (an integer chosen from [0, 1, 2, 3]) represents the relevance of the file  and the user query, where
- Score 0: The file is totally irrelevant to the user query; it does not help anything to address the user query.
- Score 1: The file is weakly relevant to the user query, but the user query can be addressed even without it.
- Score 2: The file is relevant to the user query; the user query can only be partially addressed without it.
- Score 3: The file is strongly relevant to the user query, and the user query relies on it can never be addressed without it.

## User Query ##

```
{user_query}
```

## File Preview ##

```
{file_name}

{file_preview}
```

## File List ##
```
{file_list}
```

"""

JSON_SCHEMA = """\
{
    "score": <score>, // the relevance score; it should be an integer chosen from [0, 1, 2, 3]
    "reason": "the reason why you give the relevance score" // explain in detail, step-by-step, the relevance between the file and the user query
}\
"""

NON_INTEGER_SCORE_MESSAGE = """\
**FAILURE**: The relevance score ({score}) you gave is NOT an integer.

The relevance score must be an integer chosen from [0, 1, 2, 3], where:
- Score 0: The file is totally irrelevant to the user query; it does not help anything to address the user query.
- Score 1: The file is weakly relevant to the user query, but the user query can be addressed even without it.
- Score 2: The file is relevant to the user query; the user query can only be partially addressed without it.
- Score 3: The file is strongly relevant to the user query, and the user query relies on it can never be addressed without it.

## Your Response (JSON format) ##

"""

INVALID_SCORE_VALUE_MESSAGE = """\
**FAILURE**: The relevance score ({score}) you gave is NOT chosen from [0, 1, 2, 3].

The relevance score must be an integer chosen from [0, 1, 2, 3], where:
- Score 0: The file is totally irrelevant to the user query; it does not help anything to address the user query.
- Score 1: The file is weakly relevant to the user query, but the user query can be addressed even without it.
- Score 2: The file is fairly relevant to the user query; the user query can only be partially addressed without it.
- Score 3: The file is strongly relevant to the user query, and the user query relies on it can never be addressed without it.

## Your Response (JSON format) ##

"""

SCORE_IRRELEVANCE = 0
SCORE_WEAK_RELEVANCE = 1
SCORE_FAIR_RELEVANCE = 2
SCORE_STRONG_RELEVANCE = 3


class PreviewScorer(AgentBase):
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

    def score(self, file: str, other_files: List[str]) -> Tuple[int, str]:
        return self.run(
            SYSTEM_PROMPT.format(
                repo_name=self.repo.repo_name,
                user_query=self.query,
                file_name=file,
                file_preview=FilePreview.of(file, self.repo.get_file_content(file)),
                file_list="<empty>"
                if len(other_files) == 0
                else "\n".join(other_files),
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
        if type(response["reason"]) is not str:
            return False, None
        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        return int(response["score"]), response["reason"]

    def _default_result_when_reaching_max_chat_round(self):
        return (
            SCORE_IRRELEVANCE,
            "The model have reached the max number of chat round and is unable to find any further files.",
        )
