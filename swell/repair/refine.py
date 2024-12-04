from typing import Optional, Tuple, List

from swell.agents.base import AgentBase
from swell.base.paths import SnippetPath
from swell.llms.base import LLMBase
from swell.repo.repo import Repository
from swell.utils.interval import merge_overlapping_intervals

SYSTEM_PROMPT = """\
You are an Intelligent RELEVANT Snippet Retrieval Assistant.
Your Task is to go through the provided "File Snippet" and identify the line of Snippet that are most relevant to "User Query" and "Github Issue".

For this task, I will provide you with a "File Snippet" which is a portion of the file **{file_name}**, a "User Query" and a "Github Issue".
The "User Query" is summarized from the "Github Issue", and the "Github Issue" contains more details.
The file snippet lists the content of the snippet; \
it is a portion of a file, wrapped by "===START OF SNIPPET===" and "===END OF SNIPPET===". \
We also provide some lines of surrounding content of the snippet in its file for your reference.
The Snippet is a preview version which only contains function, class, loop, branch and return, You should Use your prior knowledge to understand the code.

Correlation criterion:
1. The code snippet directly addresses or implements functionality related to the "User Query" and the "Github Issue".
2. The code's purpose aligns with the intent of the "User Query" and the "Github Issue".

*Key Remind*:
- Some relevant codes may not seem relevant, please think carefully about the meaning of the code!!!
- You must find lines which are relevant to BOTH the "User Query" AND the "Github Issue" !!!
- IF some lines are only relevant to "User Query" or only relevant to the "Github Issue", Exclude Them !!!
- if you think the Whole "File Snippet" is not Completely relevant to "User Query", set the field "line" to null.
- If you're not sure which lines are related to "User Query" and "Github Issue", set the field "line" to null.
- List AT MOST 5 lines you pretty sure they need to be modified to solve the "User Query" and the "Github Issue".

## Github Issue ##
```
{github_issue}
```

## File Snippet ##
```
//// Snippet: {snippet_path}
{file_snippet}
```

"""

JSON_SCHEMA = """\
{
    "line": <line number or null>,                 // the relevant lines; At Most 5 lines, it should be an integer list like [1,2,3]; if there are no relevant lines you should set the field to "null"
    "reason": "the reason why you give the lines " // explain in detail, step-by-step, the relevance between the "Code Snippet" and the "User Query"
}\
"""

NOT_INTEGER_LIST_MESSAGE = """\
**FAILURE**: The relevant line ({line}) you gave is NOT an integer list or null.

The relevance score must be an integer list like [1,2,3,6,7,8] or null!


## Your Response (JSON format) ##

"""

INVALID_LINE_NUMBER_MESSAGE = """\
**FAILURE**: The relevant line  ({line}) you gave is NOT chosen from the line number I gave you .

The relevance line number must be an integer chosen from the "File Snippet" which contains the line numbers you should give.


## Your Response (JSON format) ##

"""

INVALID_JSON_OBJECT_MESSAGE = """\
**FAILURE**: Your response is not a valid JSON object: {error_message}.

You response should strictly do follow the following JSON format:

```
{json_schema}
```

Please fix the above shown issues (shown above) and respond again.

## Your Response ##

"""

SYSTEM_PROMPT_JSON_INSTRUCTION = """\
## Response Format ##

Your response MUST be in the following JSON format:

```
{json_schema}
```


## Your Response ##

"""
VIOLATED_JSON_FORMAT_MESSAGE = """\
**FAILURE**: Your responded JSON object violates the given JSON format: {error_message}.

You response should strictly do follow the following JSON format:

```
{json_schema}
```

Please fix the above shown issues (shown above) and respond again.

## Your Response ##

"""


class SnipRefiner(AgentBase):
    def __init__(
        self,
        llm: LLMBase,
        repo: Repository,
        surroundings: int = 10,
        *args,
        **kwargs,
    ):
        AgentBase.__init__(self, llm=llm, json_schema=JSON_SCHEMA, *args, **kwargs)
        self.repo = repo
        self.surroundings = surroundings

    def refine(self, issue: str, snip_path: str) -> Tuple[List[str], str]:
        snip_path = SnippetPath.from_str(snip_path)
        refined_paths, reason = self.run(
            SYSTEM_PROMPT.format(
                file_name=snip_path.file_path.name,
                snippet_path=str(snip_path),
                file_snippet=self.repo.get_snippet_content(
                    str(snip_path),
                    self.surroundings,
                    add_lines=True,
                    add_separators=True,
                ),
                github_issue=issue,
            ),
            snip_path=snip_path,
        )
        # Merge continuous and overlap snippets into one snippet
        snip_tups = merge_overlapping_intervals(
            [
                (SnippetPath.from_str(sp).start_line, SnippetPath.from_str(sp).end_line)
                for sp in refined_paths
            ],
            merge_continuous=True,
        )
        return [
            str(SnippetPath(snip_path.file_path, a, b)) for a, b in snip_tups
        ], reason

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        for field in ["line", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        # The chosen "line" should be a list
        lines = response["line"]
        if not lines or lines == "null" or lines == [None]:
            return True, None
        try:
            if not isinstance(lines, list):
                return False, NOT_INTEGER_LIST_MESSAGE.format(line=response["line"])
            lines = [int(n) for n in lines]
        except ValueError:
            return False, NOT_INTEGER_LIST_MESSAGE.format(line=response["line"])

        # Make sure the line numbers are all in the correct range
        snip_path = kwargs["snip_path"]
        start_line = snip_path.start_line - self.surroundings
        end_line = snip_path.end_line + self.surroundings

        for lno in lines:
            lno = int(lno)
            if not (start_line <= lno <= end_line):
                return False, INVALID_LINE_NUMBER_MESSAGE.format(line=response["line"])

        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        snip_path = kwargs["snip_path"]
        lines = response["line"]
        reason = response["reason"]
        file_path = snip_path.file_path

        # We return all chosen lines
        return [str(SnippetPath(file_path, lno, lno + 1)) for lno in lines], reason

    def _default_result_when_reaching_max_chat_round(self):
        return (
            None,
            "The model have reached the max number of chat round and is unable to score their relevance.",
        )
