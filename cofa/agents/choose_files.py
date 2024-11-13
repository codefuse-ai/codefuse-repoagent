from typing import Tuple, Optional, List

from cofa.agents.base import AgentBase
from cofa.llms.base import LLMBase
from cofa.repo.repo import Repository

SYSTEM_PROMPT = """\
## YOUR TASK ##

You are a powerful File Chooser with the capability to analyze and evaluate the relevance of files to the "User Query".
For this task, I will give you the "User Query" and a "File List".
- The "User Query" represents an authentic request from the customer. Please take the time to comprehend and analyze the query thoroughly.
- The "File List" lists all the similar files in a list structure which you need to choose from. All the files are from the repository: {repo_name}. You do not have the access to the actual files.
Your Task is to:
- Based on your understanding of "User Query", identify and select the CERTAINLY RELEVANT files from "File List" that need modification to effectively address the user's needs.
- Return a JSON contains a List object of the files you choose from "File List" and you think are CERTAINLY RELEVANT to the "User Query" \
 and the reason why you choose them.
Note,
1. You should ONLY INCLUDE FILES IN "File List".
2. If you are NOT SURE whether some files are relevant to "User Query", DO NOT put them into the result list.
3. Please ensure that your response should be a JSON Object which includes the chosen file list along with your reason.

## User Query ##

```
{user_query}
```

## File List ##

```
{file_list}
```

"""

JSON_SCHEMA = """\
{
    "choose_list": ["<certainly_relevant_filename_1>","<certainly_relevant_filename_2>", ...]  # choose the file from "File List" certainly relevant to the "User Query"
    "reason": "the reason why you choose them " // explain in detail,step-by-step
}\
"""

NOT_FILE_LIST_MESSAGE = """\
**FAILURE**: The chosen file list you gave is NOT a list.

You response should ONLY CHOOSE FILES IN THE "File List" i give you :

```
{file_list}
```

## Your Format ##

{json_schema}

Please fix the above shown issues (shown above) and respond again.

## Your Response (NOTE : Please ues JSON format) ##

"""

INVALID_FILE_MESSAGE = """\
**FAILURE**: Your response has files should not appear : {error_message}.

You response should ONLY CHOOSE FILES IN THE "File List" i give you :

```
{file_list}
```

Please fix the above shown issues (shown above) and respond again.

## Your Format ##

{json_schema}

## Your Response (NOTE : Please ues JSON format) ##

"""


class FileChooser(AgentBase):
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

    def choose(self, from_files: List[str]):
        assert len(from_files) != 0, "Cannot choose any files if no files are given"
        return self.run(
            SYSTEM_PROMPT.format(
                repo_name=self.repo.full_name,
                user_query=self.query,
                file_list="\n".join(from_files),
            ),
            from_files=from_files,
        )

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        for field in ["choose_list", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        from_files = kwargs["from_files"]
        choose_list, _ = response["choose_list"], response["reason"]

        if type(choose_list) is not list:
            return False, NOT_FILE_LIST_MESSAGE.format(
                file_list=from_files, json_schema=JSON_SCHEMA
            )

        for file in choose_list:
            if file not in from_files:
                return False, INVALID_FILE_MESSAGE.format(
                    error_message=file,
                    file_list=from_files,
                    file_count=len(from_files),
                    json_schema=JSON_SCHEMA,
                )

        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        return response["choose_list"], response["reason"]

    def _default_result_when_reaching_max_chat_round(self):
        return (
            None,
            "The model have reached the max number of chat round and is unable to find any further files.",
        )
