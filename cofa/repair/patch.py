import difflib
import re
from collections import OrderedDict
from typing import Tuple, Optional, List

from cofa.agents.base import AgentBase
from cofa.base.console import get_boxed_console
from cofa.base.paths import SnippetPath
from cofa.llms.base import LLMBase
from cofa.repo.repo import Repository
from cofa.utils.misc import ordered_set

SYSTEM_PROMPT = """\
We are currently solving the following issue within our repository. Here is the issue text:
--- BEGIN ISSUE ---
{issue_text}

--- END ISSUE ---


Below are some code segments, each from a relevant file. One or more of these files may contain bugs.

--- BEGIN FILE ---
```
{snippet_context}
```
--- END FILE ---

Please first localize the bug based on the issue statement, and then generate *SEARCH/REPLACE* edits to fix the issue.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path
2. The start of search block: <<<<<<< SEARCH
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE

Here is an example:

```python
### mathweb/flask/app.py
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
Wrap the *SEARCH/REPLACE* edit in blocks ```python...```.
"""

_PATTERN_EDIT_COMMAND = r"```python\n(.*?)\n```"
_PATTERN_SEARCH_LINE = "<<< SEARCH"
_PATTERN_SEPARATOR_LINE = "======="
_PATTERN_REPLACE_LINE = ">>>>>>> REPLACE"

DEBUG_OUTPUT_LOGGING_COLOR = "grey50"
DEBUG_OUTPUT_LOGGING_TITLE = "Patcher"


class PatchGen(AgentBase):
    def __init__(
        self, repo: Repository, llm: LLMBase, debug_mode=False, *args, **kwargs
    ):
        super().__init__(llm=llm, json_schema=None, *args, **kwargs)
        self.repo = repo
        self.console = self.console = get_boxed_console(
            box_title=DEBUG_OUTPUT_LOGGING_TITLE,
            box_bg_color=DEBUG_OUTPUT_LOGGING_COLOR,
            debug_mode=debug_mode,
        )

    def generate(
        self,
        issue_text: str,
        snip_paths: List[str],
        max_patches: int = 1,
        context_window: int = 10,
    ) -> List[str]:
        file_paths = ordered_set(
            [str(SnippetPath.from_str(sp).file_path) for sp in snip_paths]
        )
        prompt = SYSTEM_PROMPT.format(
            issue_text=issue_text,
            snippet_context=self._make_context(snip_paths, surroundings=context_window),
        )
        patches = []
        for i in range(max_patches):
            self.console.printb(
                f"Try generating the {i+1}-th patch ({max_patches} patches are requested in total)"
            )
            patch = self.run(prompt, file_paths=file_paths)
            if patch is None:
                self.console.printb("Generation failed")
                continue
            self.console.printb(
                f"Succeeded! The generated patch is: ```diff\n{patch}\n```"
            )
            patches.append(patch)
        return patches

    def _parse_response(self, response, *args, **kwargs) -> Optional[str]:
        file_paths = kwargs["file_paths"]
        edit_cmds = re.findall(_PATTERN_EDIT_COMMAND, response, re.DOTALL)
        patch = ""
        for edit in edit_cmds:
            edited_file, old_cont, new_cont = self._parse_edit(edit, file_paths)
            if not edited_file:
                continue
            udiff = str(
                difflib.unified_diff(
                    old_cont,
                    new_cont,
                    fromfile=edited_file,
                    tofile=edited_file,
                )
            )
            if not udiff:
                continue
            patch = patch + "\n" + udiff
        return patch if patch else None

    def _make_context(self, snip_paths: List[str], surroundings: int):
        ctx_dict = OrderedDict()

        for sp in snip_paths:
            fp = str(SnippetPath.from_str(sp).file_path)
            if fp not in ctx_dict:
                ctx_dict[fp] = f"### {fp}\n"
            cont = self.repo.get_snippet_content(
                sp,
                surroundings=surroundings,
                add_lines=False,
                add_separators=False,
                san_cont=True,
            )
            ctx_dict[fp] += f"...\n{cont}\n...\n"

        return "".join(ctx_dict.values())

    def _parse_edit(
        self, edit: str, file_paths: List[str]
    ) -> Tuple[Optional[str], str, str]:
        # Find which file is in editing
        edited_file = None
        for name in file_paths:
            if name in edit:
                edited_file = name
                break
        if not edited_file:
            return None, "", ""

        # Find search, separator, and replace lines
        ser_lno, sep_lno, rep_lno = -1, -1, -1
        edit_lines = edit.splitlines()
        for index in range(len(edit_lines)):
            if _PATTERN_SEARCH_LINE in edit_lines[index]:
                ser_lno = index
            elif _PATTERN_SEPARATOR_LINE in edit_lines[index]:
                sep_lno = index
            elif _PATTERN_REPLACE_LINE in edit_lines[index]:
                rep_lno = index
        if not (ser_lno <= sep_lno <= rep_lno):
            return None, "", ""

        # Parse search and replace content
        search_content = "\n".join(edit_lines[ser_lno + 1 : sep_lno])
        replace_content = "\n".join(edit_lines[sep_lno + 1 : rep_lno])
        if not search_content or not replace_content:
            return None, "", ""

        # Get the old content of the edited file and compute its new content
        old_cont = self.repo.get_file_content(
            edited_file, add_lines=False, san_cont=False
        )
        if search_content not in old_cont:
            return None, "", ""
        return edited_file, old_cont, old_cont.replace(search_content, replace_content)
