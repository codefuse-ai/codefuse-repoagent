from typing import Tuple, Optional, List

from cofa.agents.base import AgentBase
from cofa.base.ftree import FileTree
from cofa.llms.base import LLMBase
from cofa.repo.repo import Repository

SYSTEM_PROMPT = """\
You are a File Finder, tasked to collect a list of files from the repository: {repo_name}. \
Your found files must be relevant to a "User Query" that I give you. \
Since the found files will be used by others to solve the user query, it is very important that you do not miss any relevant files.

For this task, I will give you the "User Query" and a "Repository Tree". \
The repository tree lists all the repository's files in a tree structure. \
I will also provide you with a "File List" listing all files that you are CERTAIN relevant in the past and stored. \
You initially start with files in the file list (it might also be an empty list) and will explore the tree to find further files that you are CERTAIN relevant to the user query. \
If a file you are CERTAIN relevant is already in the file list, do not add them into the list again; find another relevant one instead. \
You determine if a file is relevant to the user query merely by analyzing the relevance between the user query and:
1. the repository's directory structure (because the structure may imply the repository's )
2. each file's name and its position in the repository tree (because the file name somewhat indicates what the file's functionality)
3. your prior knowledge about the functionality of each special file (pom.xml, build.gradle, requirements.txt, package.json, etc.)
You do not have any access to any file's content.

Note,
1. There might be multiple relevant files, you respond only one file each time I query you; so please respond the file that is MOST relevant.
2. If you find all files you are CERTAIN relevant to the user query are all in the file list, set the field "file" to null and give a clear "reason" to let me know.

## User Query ##

```
{user_query}
```

## Repository Tree ##

```
{repository_tree}
```

## File List ##

```
{file_list}
```

"""

JSON_SCHEMA = """\
{{
    "file": "<file_path_or_null>", // must be the path of the file like "{example_file}" or set this field to null if you find all files you are CERTAIN relevant to the user query are in the File List
    "reason": "the reason why you think this file is relevant to the user query" // explain in detail why you deem this file is relevant to the user query this might due to its name is reflected in the query, some of its special functionality can solve the query, or any other reasonable explanation.
}}\
"""

FILE_NOT_EXISTS_MESSAGE = """\
**FAILURE**: File {file_path} does not exist in the repository.

Did you mean one of the following files?

{similar_file_paths}

## Your Response (JSON format) ##

"""

FILE_ALREADY_EXISTS_MESSAGE = """\
**FAILURE**: File {file_path} ALREADY exists in the file list.

Please find another file that you are CERTAIN relevant to the user query. \
If you find all files you are CERTAIN relevant to the user query are all in the file list, set the field "file" to null and give a clear "reason" to let me know.

## Your Response (JSON format) ##

"""


class FileFinder(AgentBase):
    def __init__(
        self,
        query: str,
        repo: Repository,
        tree: FileTree,
        llm: LLMBase,
        includes: Optional[List[str]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            llm=llm,
            json_schema=JSON_SCHEMA.format(example_file=repo.get_rand_file()),
            *args,
            **kwargs,
        )
        self.query = query
        self.repo = repo
        self.file_list = []
        self.tree = tree
        self.includes = includes

    def next_file(self):
        return self.run(
            SYSTEM_PROMPT.format(
                repo_name=self.repo.full_name,
                user_query=self.query,
                repository_tree=str(self.tree),
                file_list="<empty>"
                if len(self.file_list) == 0
                else "\n".join(self.file_list),
            )
        )

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        for field in ["file", "reason"]:
            if field not in response:
                return False, f"'{field}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        file_path = response["file"]

        # None is a valid response
        if file_path is None:
            return True, None

        # Check the existence of the file in the repository
        if not self.repo.has_file(file_path):
            return False, FILE_NOT_EXISTS_MESSAGE.format(
                file_path=file_path,
                similar_file_paths="\n".join(
                    [
                        f"- {path}"
                        for path in self.repo.find_similar_files(
                            file_path, includes=self.includes
                        )
                    ]
                ),
            )

        # Check the existence of the file in file list
        if file_path in self.file_list:
            return False, FILE_ALREADY_EXISTS_MESSAGE.format(file_path=file_path)

        return True, None

    def _parse_response(self, response: dict, *args, **kwargs) -> any:
        file_path, reason = response["file"], response["reason"]
        if file_path is None:
            return None, reason
        self.file_list.append(file_path)
        return file_path, reason

    def _default_result_when_reaching_max_chat_round(self):
        return (
            None,
            "The model have reached the max number of chat round and is unable to find any further files.",
        )
