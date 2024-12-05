from typing import Tuple, Optional, List, Generator

from cora.agents.base import AgentBase
from cora.agents.snippets.base import SnipFinderBase, SnipRelDetmBase
from cora.llms.base import LLMBase
from cora.preview import FilePreview
from cora.repo.repo import Repository
from cora.utils.interval import merge_overlapping_intervals

SYSTEM_PROMPT = """\
You are a Snippet Finder, tasked to collect a list of snippets from the file: {file_name}. \
Your found snippets must be relevant to a "User Query" that I give you. \
Since the found snippets will be used by others to solve the user query, it is very important that you do not miss any relevant snippets.

For this task, I will give you the "User Query" and a "File Preview". \
The file preview presents an overview of the file, with some file contents being presented with "...". \
Through file preview, you determine which line ranges (e.g., 100-120) of the file (i.e., file snippet) you think might be relevant to the user query, \
or you determine the file is not relevant to the user query at all. \
In any case, you should explain in detail the reason why you decide it is relevant or not relevant. \
In addition, I will provide you with a "Snippet List" listing all snippets that you found relevant in the past and stored. \
Starting from the list, you should further find other relevant snippets.

Note,
1. There might be multiple relevant snippets, you respond only one snippet each time I query you; so please respond the snippet that is MOST relevant.
2. If you find all snippets that might be relevant to the user query are all in the snippet list, set the field "start_line" and "end_line" to -1 and give a clear "reason" to let me know.

## User Query ##

```
{user_query}
```

## File Preview ##

```
{file_preview}
```

## Snippet List ##

```
{snippet_list}
```

"""

JSON_SCHEMA = """\
{
    "start_line": "<line_number>", // must be an integer indicating the start line number of the snippet (included), or set this field to -1 if you think there ain't any relevant snippets
    "end_line": "<line_number>", // must be an integer indicating the end line number of the snippet (excluded), or set this field to -1 if you think there ain't any relevant snippets
    "reason": "the reason why you think this snippet might be relevant to the user query" // explain in detail why you deem this snippet is relevant to the user query; you should explain firstly what the user query is, then what this snippet does, and finally what their relevance is.
}\
"""

NEGATIVE_START_OR_END_LINE_MESSAGE = """\
**FAILURE**: Invalid snippet {which_line} ({line_number}).

The {which_line} argument should be greater than or equal to -1, \
where -1 indicates that the file do not contain any relevant snippet or all relevant snippet are included in the snippet list.

Please correct your {which_line} argument or choose another snippet.

## Your Response (JSON format) ##

"""

INCORRECT_START_END_RELATION_MESSAGE = """\
**FAILURE**: The start_line ({start_line}) argument must be less than (<) the end_line ({end_line}) argument.

Both of these two arguments should be greater than or equal to -1, \
where -1 indicates that the file do not contain any relevant snippet or all relevant snippet are included in the snippet list.

Please correct these two arguments or choose another snippet.

## Your Response (JSON format) ##

"""

START_END_LINE_EXCEEDED_MESSAGE = """\
**FAILURE**: The {which_line} ({line_number}) exceeds the total number of file lines ({num_file_lines}).

The {which_line} argument should be greater than or equal to -1, and less than {num_file_lines}, \
where -1 indicates that the file do not contain any relevant snippet or all relevant snippet are included in the snippet list.

Please correct the {which_line} arguments.

## Your Response (JSON format) ##

"""

SNIPPET_ALREADY_EXISTS_MESSAGE = """\
**FAILURE**: Snippet {start_line}-{end_line} ALREADY exists in the snippet list.

Please find another snippet that you think might be relevant to the user query. \
If you find all snippets that might be relevant to the user query are all in the snippet list, set the field "start_line" and "end_line" to -1 and give a clear "reason" to let me know.

## Your Response (JSON format) ##

"""

SNIPPET_ALREADY_COVERED_BY_OTHERS_MESSAGE = """\
**FAILURE**: Snippet {start_line}-{end_line} ALREADY exists in the snippet list; \
in fact, it is covered by Snippet {covered_start_line}-{covered_end_line}.

Please find another snippet that you think might be relevant to the user query. \
Do never find any (sub-)snippet that is covered by snippets in the snippet list. \
If you find all snippets that might be relevant to the user query are all in the snippet list, set the field "start_line" and "end_line" to -1 and give a clear "reason" to let me know.

## Your Response (JSON format) ##

"""

SNIPPET_NOT_RELEVANT_MESSAGE = """\
After reviewing the snippet {start_line}-{end_line} in detail, we are CERTAIN that the snippet is NOT relevant to the user query because:

```
{not_relevant_reason}
```

Please find another snippet that you think might be relevant to the user query. \
If you find all snippets that might be relevant to the user query are all in the snippet list, set the field "start_line" and "end_line" to -1 and give a clear "reason" to let me know.

## Your Response (JSON format) ##

"""


class PrevSnipFinder(SnipFinderBase, AgentBase):
    def __init__(
        self,
        llm: LLMBase,
        repo: Repository,
        determ: SnipRelDetmBase,
        *args,
        **kwargs,
    ):
        SnipFinderBase.__init__(self, repo=repo, determ=determ)
        AgentBase.__init__(self, llm=llm, json_schema=JSON_SCHEMA, *args, **kwargs)

    def find(
        self, query: str, file_path: str, *args, **kwargs
    ) -> Generator[Tuple[str, str], None, None]:
        file_content = self.repo.get_file_content(file_path)
        file_lines = file_content.splitlines()
        file_preview = FilePreview.of(file_path, file_content)

        snippet_list = []

        while True:
            snippet, reason = self.run(
                SYSTEM_PROMPT.format(
                    file_name=file_path,
                    user_query=query,
                    file_preview=self.reduced_file_preview(file_preview, snippet_list),
                    snippet_list="<empty>"
                    if len(snippet_list) == 0
                    else "\n".join(
                        [f"{file_path}:{s[0]}-{s[1]}" for s in snippet_list]
                    ),
                ),
                query=query,
                file_path=file_path,
                file_content=file_content,
                file_lines=file_lines,
                file_preview=file_preview,
                existing_snippets=snippet_list,
            )

            if snippet is None:
                break

            yield snippet, reason

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        for field in ["start_line", "end_line", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        query = kwargs["query"]
        file_path = kwargs["file_path"]
        file_lines = kwargs["file_lines"]
        existing_snippets = kwargs["existing_snippets"]

        # TODO: Catch cast exception
        start_line, end_line = int(response["start_line"]), int(response["end_line"])

        # -1, -1 is valid as the model requests to stop the finder
        if start_line == -1 or end_line == -1:
            return True, None

        # Check the validity of start_line and end_line
        if start_line < 0:
            return False, NEGATIVE_START_OR_END_LINE_MESSAGE.format(
                which_line="start_line", line_number=start_line
            )

        if end_line < 0:
            return False, NEGATIVE_START_OR_END_LINE_MESSAGE.format(
                which_line="end_line", line_number=end_line
            )

        if end_line <= start_line:
            return False, INCORRECT_START_END_RELATION_MESSAGE.format(
                start_line=start_line, end_line=end_line
            )

        num_file_lines = len(file_lines)

        if start_line >= num_file_lines:
            return False, START_END_LINE_EXCEEDED_MESSAGE.format(
                which_line="start_line",
                line_number=start_line,
                num_file_lines=num_file_lines,
            )

        if end_line >= num_file_lines:
            return False, START_END_LINE_EXCEEDED_MESSAGE.format(
                which_line="end_line",
                line_number=end_line,
                num_file_lines=num_file_lines,
            )

        # Check the existence of the snippet in snippet list
        elif (start_line, end_line) in existing_snippets:
            return False, SNIPPET_ALREADY_EXISTS_MESSAGE.format(
                start_line=start_line, end_line=end_line
            )

        # Check if the new snippet are already covered by the snippet list
        covered_snippet = None
        for sa, sb in existing_snippets:
            if sa <= start_line and end_line <= sb:
                covered_snippet = (sa, sb)
                break
        if covered_snippet is not None:
            return False, SNIPPET_ALREADY_COVERED_BY_OTHERS_MESSAGE.format(
                start_line=start_line,
                end_line=end_line,
                covered_start_line=covered_snippet[0],
                covered_end_line=covered_snippet[1],
            )

        # Let's call another agent to view the snippet and check their relevance
        is_relevant, rel_reason = self.determ_relevance(
            query, file_path, file_lines, start_line, end_line
        )

        if not is_relevant:
            return False, SNIPPET_NOT_RELEVANT_MESSAGE.format(
                start_line=start_line, end_line=end_line, not_relevant_reason=rel_reason
            )

        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        file_path = kwargs["file_path"]
        existing_snippets = kwargs["existing_snippets"]

        start_line, end_line = int(response["start_line"]), int(response["end_line"])
        reason = response["reason"]

        # -1, -1 is valid as the model requests to stop the finder
        if start_line == -1 or end_line == -1:
            return None, reason

        existing_snippets.append((start_line, end_line))

        # Reshape snippet_list such that it is clean
        merged_snippet_tups = merge_overlapping_intervals(existing_snippets)
        existing_snippets.clear()
        existing_snippets.extend(merged_snippet_tups)

        return f"{file_path}:{start_line}-{end_line}", reason

    def _default_result_when_reaching_max_chat_round(self):
        return (
            None,
            "The model have reached the max number of chat round and is unable to find any further snippets.",
        )

    def determ_relevance(self, query, file_path, file_lines, start_line, end_line):
        snippet = self.file_snippet(file_lines, start_line, end_line, surroundings=0)
        return self.determ.determine(
            query, f"{file_path}:{start_line}-{end_line}", snippet
        )

    @staticmethod
    def reduced_file_preview(preview: str, existing_snippets: List[Tuple[int, int]]):
        # Reduce the preview by replacing saved snippets with dots
        if len(existing_snippets) == 0:
            return preview

        max_line_number = -1
        cached_preview_lines = []
        # Find the preceding line numbers
        for line in preview.splitlines():
            line_number, line_content = FilePreview.parse_preview_line(line)
            cached_preview_lines.append(
                (line_number, (line, line_content))
            )  # line_number might be None
            if line_number is not None and line_number > max_line_number:
                max_line_number = line_number

        # Put preview lines in an array
        preview_lines = [None for _ in range(max_line_number + 1)]
        for index, (line_number, line_tuple) in enumerate(cached_preview_lines):
            if line_number is not None:
                preview_lines[line_number] = line_tuple

        # Hide all lines in one of our snippet
        for sa, sb in existing_snippets:
            for line_number in range(sa, sb, 1):
                line_tuple = preview_lines[line_number]
                if line_tuple is not None:
                    preview_lines[line_number] = None

        reduced_preview = []
        hidden_start_number = -1
        last_line_number = 0
        last_line_content = ""
        for line_number, line in enumerate(preview_lines):
            if line is not None:
                if hidden_start_number == -1:
                    reduced_preview.append(line[0])
                    last_line_number = line_number
                    last_line_content = line[1]
                else:
                    spacing = FilePreview.spacing_for_line_number(last_line_number)
                    indentation = FilePreview.indentation_of_line(last_line_content)
                    reduced_preview.extend(
                        [
                            spacing + indentation + "...",
                            spacing
                            + indentation
                            + f"(lines {hidden_start_number}-{line_number - 1} are hidden in preview)",
                            spacing + indentation + "...\n",
                            line[0],
                        ]
                    )
                    hidden_start_number = -1
            elif hidden_start_number == -1:
                hidden_start_number = line_number

        return "\n".join(reduced_preview)

    @staticmethod
    def file_snippet(file_lines, start_line, end_line, surroundings=0):
        return Repository.extract_snippet_lines(
            file_lines, start_line, end_line, surroundings
        )
