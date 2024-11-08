import fnmatch
import glob
import os
import random
from abc import abstractmethod
from collections import namedtuple
from pathlib import Path
from typing import List, Optional, Tuple

import rapidfuzz

from cofa.base.paths import SnippetPath, FilePath
from cofa.config import CofaConfig
from cofa.splits.factory import SplFactory
from cofa.utils import sanitize_content, CannotReachHereError

RepoTup = namedtuple("RepoTup", ("org", "name", "path"))


class RepoBase:
    def __init__(
        self,
        repo: RepoTup,
        *,
        # This should be shell patterns as in the fnmatch module
        excluded_patterns: Optional[List[str]] = None,
    ):
        self.repo_org = repo.org
        self.repo_name = repo.name
        self.repo_path = str(FilePath(repo.path).resolve())
        self.excluded_patterns = excluded_patterns or []
        self._snippets = None

    @property
    def full_name(self) -> str:
        return f"{self.repo_org}/{self.repo_name}"

    def render_file_tree(
        self, included_file_patterns: Optional[List[str]] = None
    ) -> str:
        from cofa.base.ftree import FileTree

        def should_include(fp: str):
            if included_file_patterns:
                return any(
                    fnmatch.fnmatch(fp, pattern) for pattern in included_file_patterns
                )
            else:
                return True

        def format_file_tree(curr_dir: FilePath, depth: int):
            dir_tree_str = ""

            children_files = list(curr_dir.iterdir())
            children_files.sort()

            for child_file in children_files:
                child_file = child_file.resolve()
                relative_path = str(child_file)[len(self.repo_path) + 1 :]
                if self.should_exclude(relative_path):
                    continue
                if child_file.is_file() and not should_include(relative_path):
                    continue
                indentation = " " * FileTree.LINE_INDENT_NUM_SPACES * depth
                if child_file.is_dir():
                    dir_tree_str += f"{indentation}{relative_path}{FileTree.DIRECTORY_LINE_ENDINGS}\n"
                    dir_tree_str += format_file_tree(child_file, depth=depth + 1)
                else:
                    dir_tree_str += f"{indentation}{child_file.name}\n"
            return dir_tree_str

        return format_file_tree(FilePath(self.repo_path), depth=0)

    def get_file_list(self) -> List[str]:
        files = [
            file_path[len(self.repo_path) + 1 :]
            for file_path in glob.iglob(f"{self.repo_path}/**", recursive=True)
            if os.path.isfile(file_path)
        ]
        files = [file_path for file_path in files if not self.should_exclude(file_path)]
        return files

    def has_file(self, file_path: str) -> bool:
        return file_path in self.get_file_list()

    def get_directory_list(
        self, incl_repo_dir: bool = False, innermost: bool = False
    ) -> List[str]:
        if innermost:  # Only return innermost directories, without intermediate ones
            dirs = {f[: f.rindex("/") + 1] for f in self.get_file_list() if "/" in f}
        else:  # Return all existing directories
            dirs = {
                dir_path[len(self.repo_path) + 1 :] + "/"
                for dir_path in glob.iglob(f"{self.repo_path}/**", recursive=True)
                if os.path.isdir(dir_path)
            }
            dirs = {dir_path for dir_path in dirs if not self.should_exclude(dir_path)}
        if incl_repo_dir:  # Add the project directory into the results
            dirs.add("/")
        return [dir_ for dir_ in dirs]

    def has_directory(self, dir_path: str) -> bool:
        if not dir_path.endswith("/"):
            dir_path += "/"
        return dir_path in self.get_directory_list(incl_repo_dir=True)

    def get_snippet_list(self) -> List[str]:
        self._ensure_repository_chunked()
        return [str(s) for s in self._snippets]

    def get_snippet_tuple_list(self) -> List[Tuple[str, int, int]]:
        self._ensure_repository_chunked()
        return [(s.file_path, s.start_line, s.end_line) for s in self._snippets]

    def get_file_snippet_list(self, file_path: str) -> List[str]:
        return [str(s) for s in self._snippets if str(s.file_path) == file_path]

    def get_file_snippet_tuple_list(self, file_path: str) -> List[Tuple[int, int]]:
        return [
            (s.start_line, s.end_line)
            for s in self._snippets
            if str(s.file_path) == file_path
        ]

    def resize_file_snippets(self, file_path: str, snippet_size: int = -1) -> List[str]:
        self._ensure_repository_chunked()
        if snippet_size <= 0:
            return self.get_file_snippet_list(file_path)
        # Merge consecutive snippets unless their size is snippet_size
        snippet_tuples, last_tuple = [], None
        for curr_tuple in self.get_file_snippet_tuple_list(file_path):
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
        return [f"{file_path}:{t[0]}-{t[1]}" for t in snippet_tuples]

    def get_file_content(
        self, file_path: str, add_lines: bool = False, san_cont: bool = False
    ) -> str:
        san_cont = san_cont or CofaConfig.sanitize_content_in_repository()
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

    def find_similar_files(
        self,
        file_path: str,
        limit: int = 10,
        return_abs_paths: bool = False,
        included_patterns: Optional[List[str]] = None,
    ) -> List[str]:
        return self._find_similar_paths(
            file_path,
            self.get_file_list(),
            limit=limit,
            return_abs_paths=return_abs_paths,
            included_patterns=included_patterns,
        )

    def find_similar_directories(
        self,
        directory_path: str,
        limit: int = 10,
        return_abs_paths: bool = False,
        included_patterns: List[str] = None,
    ) -> List[str]:
        return self._find_similar_paths(
            directory_path,
            self.get_directory_list(),
            limit=limit,
            return_abs_paths=return_abs_paths,
            included_patterns=included_patterns,
        )

    def get_rand_file(self) -> str:
        dir_list = self.get_file_list()
        return dir_list[random.randint(0, len(dir_list) - 1)]

    def get_rand_directory(self):
        dir_list = self.get_directory_list()
        return dir_list[random.randint(0, len(dir_list) - 1)]

    @abstractmethod
    def get_file_snippets(
        self, file_path: str, snippet_size: int = -1
    ) -> List[str]: ...

    @abstractmethod
    def search_snippets(
        self, query: str, engine: str = None, limit: int = 10, *args, **kwargs
    ) -> List[str]: ...

    def search_files(self, query, engine: str = None, limit: int = 10, *args, **kwargs):
        # Let's assume the top 32*limit snippets must contain top limit files
        files = []
        for s in self.search_snippets(
            query, engine=engine, limit=32 * limit, *args, **kwargs
        ):
            if len(files) == limit:
                return files
            f = str(SnippetPath.from_str(s).file_path)
            if f not in files:
                files.append(f)
        return files

    def should_exclude(self, file_path: str):
        return any(
            fnmatch.fnmatch(file_path, pattern) for pattern in self.excluded_patterns
        ) or CofaConfig.should_exclude(os.path.join(self.repo_path, file_path))

    def _find_similar_paths(
        self,
        to_path: str,
        from_path_list: List[str],
        limit: int = 10,
        return_abs_paths: bool = False,
        included_patterns: Optional[List[str]] = None,
    ) -> List[str]:
        path_name = FilePath(to_path).name
        if included_patterns:
            from_path_list = [
                path
                for path in from_path_list
                if any(fnmatch.fnmatch(path, pattern) for pattern in included_patterns)
            ]
        similar_paths = RepoBase._find_similar_names(
            path_name, from_path_list, limit=limit
        )
        if return_abs_paths:
            return [os.path.join(self.repo_path, path) for path in similar_paths]
        else:
            return similar_paths

    @staticmethod
    def _find_similar_names(name: str, name_list: List[str], limit: int = 10):
        sorted_full_scores = sorted(
            name_list,
            key=lambda n: rapidfuzz.fuzz.ratio(name, n) + (101 if name in n else 0),
            reverse=True,
        )
        sorted_part_scores = sorted(
            name_list, key=lambda n: rapidfuzz.fuzz.partial_ratio(name, n), reverse=True
        )
        sorted_final_scores = sorted_full_scores[:limit]
        for s in sorted_part_scores[:limit]:
            if s not in sorted_final_scores:
                sorted_final_scores.append(s)
        return sorted_final_scores

    def _ensure_repository_chunked(self):
        if self._snippets:
            return
        self._snippets = []
        for file in self.get_file_list():
            self._snippets.extend(SplFactory.create(FilePath(file)).split())
