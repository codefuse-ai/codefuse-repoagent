import glob
import os
import random
from collections import namedtuple
from pathlib import Path
from typing import List, Optional, Tuple

from cora.base.paths import SnippetPath, FilePath
from cora.config import CoraConfig
from cora.splits.factory import SplFactory
from cora.utils.misc import CannotReachHereError
from cora.utils.pattern import match_any_pattern
from cora.utils.sanitize import sanitize_content

RepoTup = namedtuple("RepoTup", ("org", "name", "path"))


class RepoBase:
    def __init__(
        self,
        repo: RepoTup,
        *,
        # This should be shell patterns as in the fnmatch module
        excludes: Optional[List[str]] = None,
    ):
        self.repo_org = repo.org
        self.repo_name = repo.name
        self.repo_path = str(FilePath(repo.path).resolve())
        self.excludes = excludes or []
        self._snippets: List[SnippetPath] = []

    @property
    def full_name(self) -> str:
        return f"{self.repo_org}/{self.repo_name}"

    def render_file_tree(self, includes: Optional[List[str]] = None) -> str:
        from cora.base.ftree import FileTree

        def should_include_file(fp: str):
            return not includes or match_any_pattern(fp, includes)

        def format_file_tree(curr_dir: FilePath, depth: int):
            dir_tree_str = ""

            children_files = list(curr_dir.iterdir())
            children_files.sort()

            for child_file in children_files:
                child_file = child_file.resolve()
                relative_path = str(child_file)[len(self.repo_path) + 1 :]
                if self.should_exclude(relative_path):
                    continue
                if child_file.is_file() and not should_include_file(relative_path):
                    continue
                indentation = " " * FileTree.LINE_INDENT_NUM_SPACES * depth
                if child_file.is_dir():
                    dir_tree_str += f"{indentation}{relative_path}{FileTree.DIRECTORY_LINE_ENDINGS}\n"
                    dir_tree_str += format_file_tree(child_file, depth=depth + 1)
                else:
                    dir_tree_str += f"{indentation}{child_file.name}\n"
            return dir_tree_str

        return format_file_tree(FilePath(self.repo_path), depth=0)

    def get_all_files(self) -> List[str]:
        files = [
            file_path[len(self.repo_path) + 1 :]
            for file_path in glob.iglob(f"{self.repo_path}/**", recursive=True)
            if os.path.isfile(file_path)
        ]
        files = [file_path for file_path in files if not self.should_exclude(file_path)]
        return files

    def has_file(self, file_path: str) -> bool:
        return file_path in self.get_all_files()

    def get_all_directories(self, incl_repo_dir: bool = False) -> List[str]:
        dirs = {
            dir_path[len(self.repo_path) + 1 :] + "/"
            for dir_path in glob.iglob(f"{self.repo_path}/**", recursive=True)
            if os.path.isdir(dir_path)
        }
        dirs = {dir_path for dir_path in dirs if not self.should_exclude(dir_path)}
        # Add the project directory into the results
        if incl_repo_dir:
            dirs.add("/")
        return [dir_ for dir_ in dirs]

    def has_directory(self, dir_path: str) -> bool:
        if not dir_path.endswith("/"):
            dir_path += "/"
        return dir_path in self.get_all_directories(incl_repo_dir=True)

    def get_all_snippets(self) -> List[str]:
        self.ensure_repository_chunked()
        return [str(s) for s in self._snippets]

    def get_all_snippet_tuples(self) -> List[Tuple[str, int, int]]:
        self.ensure_repository_chunked()
        return [(str(s.file_path), s.start_line, s.end_line) for s in self._snippets]

    def get_all_snippets_of_file(self, file_path: str) -> List[str]:
        self.ensure_repository_chunked()
        return [str(s) for s in self._snippets if str(s.file_path) == file_path]

    def get_all_snippet_tuples_of_file(self, file_path: str) -> List[Tuple[int, int]]:
        self.ensure_repository_chunked()
        return [
            (s.start_line, s.end_line)
            for s in self._snippets
            if str(s.file_path) == file_path
        ]

    def get_all_snippets_of_file_with_size(
        self, file_path: str, snippet_size: int = -1
    ) -> List[str]:
        self.ensure_repository_chunked()
        if snippet_size <= 0:
            return self.get_all_snippets_of_file(file_path)
        # Merge consecutive snippets unless their size is snippet_size
        snippet_tuples, last_tuple = [], None
        for curr_tuple in self.get_all_snippet_tuples_of_file(file_path):
            if last_tuple is None:
                last_tuple = curr_tuple
                continue
            if last_tuple[1] != curr_tuple[0]:
                raise CannotReachHereError(
                    f"The current snippet does not directly follow the last snippet: "
                    f"last_tuple.end={last_tuple[2]} while curr_tuple.start={curr_tuple[1]} !"
                )
            curr_size = curr_tuple[1] - curr_tuple[0]
            last_size = last_tuple[1] - last_tuple[0]
            if last_size + curr_size <= snippet_size:
                last_tuple = (last_tuple[0], curr_tuple[1])
            else:
                snippet_tuples.append(last_tuple)
                last_tuple = curr_tuple
        if last_tuple:
            snippet_tuples.append(last_tuple)
        return [
            str(SnippetPath(FilePath(file_path), t[0], t[1])) for t in snippet_tuples
        ]

    def get_file_content(
        self, file_path: str, add_lines: bool = False, san_cont: bool = False
    ) -> str:
        san_cont = san_cont or CoraConfig.sanitize_content_in_repository()
        file_path = Path(self.repo_path) / file_path
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_path} does not exist.")
        file_cont = file_path.read_text(encoding="utf-8", errors="replace")
        if san_cont:
            file_cont = sanitize_content(file_cont)
        if add_lines:
            file_cont = "\n".join(
                str(i) + " | " + s for i, s in enumerate(file_cont.splitlines())
            )
        return file_cont

    def get_snippet_content(
        self,
        snippet_path: str,
        surroundings: int = 0,
        add_lines: bool = False,
        add_separators: bool = True,
        san_cont: bool = False,
    ) -> str:
        snippet_path = SnippetPath.from_str(snippet_path)
        return RepoBase.extract_snippet_lines(
            self.get_file_content(
                str(snippet_path.file_path), add_lines=add_lines, san_cont=san_cont
            ).splitlines(),
            snippet_path.start_line,
            snippet_path.end_line,
            surroundings,
            add_separators=add_separators,
        )

    @staticmethod
    def extract_snippet_lines(
        file_lines, start_line, end_line, surroundings, add_separators=True
    ):
        snippet = ""

        start_index = max(0, start_line - surroundings)
        for i, line in enumerate(file_lines[start_index:start_line]):
            snippet += f"{line}\n"

        if add_separators:
            snippet += "===START OF SNIPPET===\n"
        for i, line in enumerate(file_lines[start_line:end_line]):
            snippet += f"{line}\n"
        if add_separators:
            snippet += "===END OF SNIPPET===\n"

        end_index = min(len(file_lines), end_line + surroundings)
        for i, line in enumerate(file_lines[end_line:end_index]):
            snippet += f"{line}\n"

        return snippet

    def get_rand_file(self) -> str:
        dir_list = self.get_all_files()
        return dir_list[random.randint(0, len(dir_list) - 1)]

    def get_rand_directory(self):
        dir_list = self.get_all_directories()
        return dir_list[random.randint(0, len(dir_list) - 1)]

    def should_exclude(self, file_path: str):
        return match_any_pattern(file_path, self.excludes) or CoraConfig.should_exclude(
            os.path.join(self.repo_path, file_path)
        )

    def ensure_repository_chunked(self):
        if self._snippets:
            return
        self._snippets = []
        for file in self.get_all_files():
            self._snippets.extend(
                [
                    SnippetPath(
                        s.file_path.relative_to(self.repo_path),
                        s.start_line,
                        s.end_line,
                    )
                    for s in SplFactory.create(FilePath(self.repo_path) / file).split()
                ]
            )
