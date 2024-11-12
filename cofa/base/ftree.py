import fnmatch
from typing import List

from cofa.base.repos import RepoBase
from cofa.utils.tree import TreeNode

"""
This script is adapted from Sweep's tree_utils.py
"""


class FileLine:
    def __init__(self, num_indent, text, parent=None, is_dir=False):
        self.num_indent = num_indent
        # TODO: Use name only and update full_path()
        self.text = text
        self.parent = parent
        self.is_dir = is_dir
        self.is_shown = True

    def full_path(self):
        if self.is_dir:
            return self.text
        elif self.parent:
            return self.parent.full_path() + self.text
        else:
            return self.text

    def __eq__(self, other):
        if not isinstance(other, FileLine):
            return False
        return self.full_path() == other.full_path()

    def __str__(self):
        return self.full_path()

    def __repr__(self):
        return self.full_path()


class FileTree:
    LINE_INDENT_NUM_SPACES = 2
    DIRECTORY_LINE_ENDINGS = "/"

    @staticmethod
    def from_repository(repository: RepoBase):
        file_tree = FileTree()
        file_tree._parse_tree(repository.render_file_tree())
        return file_tree

    def __init__(self):
        # TODO: Refactor using tree, rather than list
        self._complete_lines: List[FileLine] = []

    def _shown_lines(self):
        return [line for line in self._complete_lines if line.is_shown]

    @staticmethod
    def _show_line(line):
        line.is_shown = True

    @staticmethod
    def _hide_line(line):
        line.is_shown = False

    def _parse_tree(self, input_str: str):
        stack: List[FileLine] = []

        for line in input_str.strip().split("\n"):
            num_spaces = len(line) - len(line.lstrip())
            num_indent = num_spaces // FileTree.LINE_INDENT_NUM_SPACES
            line = line.strip()

            while stack and stack[-1].num_indent >= num_indent:
                stack.pop()

            is_directory = line.endswith(FileTree.DIRECTORY_LINE_ENDINGS)
            parent = stack[-1] if stack else None
            # TODO: Remove such requirements
            tree_line = FileLine(num_indent, line, parent, is_dir=is_directory)

            if is_directory:
                stack.append(tree_line)

            self._complete_lines.append(tree_line)

    def current_size(self):
        return len(self._shown_lines())

    def complete_size(self):
        return len(self._complete_lines)

    def find_files(self, pattern: str, is_dir: bool = False):
        return [
            line.full_path()
            for line in self._shown_lines()
            if (not is_dir or line.is_dir)
            and fnmatch.fnmatch(line.full_path(), pattern)
        ]

    def include_file(self, file):
        for line in self._shown_lines():
            if not line.is_dir and file == line.full_path():
                return True
        return False

    def include_directory(self, directory):
        for line in self._shown_lines():
            if line.is_dir and directory == line.full_path():
                return True
        return False

    def reset(self):
        for line in self._complete_lines:
            self._show_line(line)

    def _show_only(self, lines_to_show):
        for line in self._complete_lines:
            self._hide_line(line)
        for line in lines_to_show:
            self._show_line(line)

    def _hide_only(self, lines_to_hide):
        for line in self._complete_lines:
            self._show_line(line)
        for line in lines_to_hide:
            self._hide_line(line)

    def keep_only(self, included_files_or_dirs):
        """
        Keep files that:
        - either are exact files in included_files_or_dirs
        - or are (direct or indirect) children of directories in included_files_or_dirs
        """
        if FileTree.DIRECTORY_LINE_ENDINGS in included_files_or_dirs:
            return self.reset()
        shown_lines, new_lines = self._shown_lines(), []
        for line in shown_lines:
            full_path = line.full_path()
            # The current line is a child of any directory that are to be included
            if any(
                full_path.startswith(included_path)
                for included_path in included_files_or_dirs
            ):
                # Include the current line and all its parents
                parent_list = []
                curr_parent = line.parent
                while curr_parent and curr_parent not in new_lines:
                    parent_list.append(curr_parent)
                    curr_parent = curr_parent.parent
                new_lines.extend(parent_list[::-1])
                new_lines.append(line)
            # The current line's direct parent is to be included
            elif line.parent and line.parent.full_path() in included_files_or_dirs:
                # Include the current line
                new_lines.append(line)
        self._show_only(new_lines)

    def expand_directory(self, directory):
        """
        Expand directory such that all its *direct* children are shown
        """
        return self.expand_directories([directory])

    def expand_directories(self, dirs_to_expand):
        """
        Expand all directories in dirs_to_expand such that all their *direct* children are shown
        """

        def parent_dirs(path):
            return [path[: i + 1] for i in range(len(path)) if path[i] == "/"]

        dir_parents = []
        for dir_ in dirs_to_expand:
            # If it's not an extension and it doesn't end in /, add /
            if not dir_.endswith(FileTree.DIRECTORY_LINE_ENDINGS):
                dir_ += FileTree.DIRECTORY_LINE_ENDINGS
            dir_parents.extend(parent_dirs(dir_))
        dirs_to_expand = list(set(dirs_to_expand))
        expanded_lines = []
        for line in self._complete_lines:
            # The line is in the root directory, and we are expanding the root directory
            if not line.parent and FileTree.DIRECTORY_LINE_ENDINGS in dirs_to_expand:
                expanded_lines.append(line)
            # The line is included by one of the directory in dirs_to_expand
            elif line.parent and any(
                line.parent.full_path().startswith(dir_) for dir_ in dirs_to_expand
            ):
                expanded_lines.append(line)
            # The line is a parent of one of the directory in dirs_to_expand
            elif line.full_path() in dir_parents:
                expanded_lines.append(line)
            # The line is one of the directory in dirs_to_expand
            elif line.full_path() in dirs_to_expand:
                # We must ensure that our parents are to be expanded
                if not line.parent or line.parent.full_path() in dirs_to_expand:
                    expanded_lines.append(line)
            # The line is shown currently
            elif line.is_shown:
                expanded_lines.append(line)
        self._show_only(expanded_lines)

    def collapse_directory(self, directory):
        return self.collapse_directories([directory])

    def collapse_directories(self, dirs_to_collapse):
        """
        Collapse all directories in dirs_to_collapse and hide them from the file tree
        """
        dirs_to_collapse = {
            (
                dir_
                if dir_.endswith(FileTree.DIRECTORY_LINE_ENDINGS)
                else dir_ + FileTree.DIRECTORY_LINE_ENDINGS
            )
            for dir_ in dirs_to_collapse
        }
        curr_line_no = 0
        shown_lines, collapsed_lines = self._shown_lines(), []
        while curr_line_no < len(shown_lines):
            curr_line = shown_lines[curr_line_no]
            # The line is either a file or should not be collapsed
            if not curr_line.is_dir or curr_line.full_path() not in dirs_to_collapse:
                collapsed_lines.append(curr_line)
                curr_line_no += 1
                continue
            # Skip current line and its children and find its or its parent's next sibling line
            next_line_no = curr_line_no + 1
            while next_line_no < len(shown_lines):
                next_line = shown_lines[next_line_no]
                if (
                    next_line.num_indent <= curr_line.num_indent
                ):  # Found its or its parent's next sibling
                    break
                next_line_no += 1
            # We will hide current line, so we do not append it to collapsed lines
            curr_line_no = next_line_no
        self._show_only(collapsed_lines)

    def collapse_innermost_directories_until(self, size: int):
        if self.current_size() <= size:
            return

        def hide_node(n):
            self._hide_line(n.data)

        tree_root = self._as_tree(self._shown_lines())
        im_dir_nodes = []
        while self.current_size() > size:
            if len(im_dir_nodes) == 0:
                # Let's collapse the innermost directory with the least number of children
                im_dir_nodes = set()
                for node in tree_root.leaves():
                    if node.data.is_dir:  # It's a directory, add it
                        im_dir_nodes.add(node)
                    elif node.parent:  # It's a file, add its parent
                        im_dir_nodes.add(node.parent)
                im_dir_nodes = [n for n in im_dir_nodes]
                # The number of indentations prioritizes the number of children
                im_dir_nodes.sort(
                    key=lambda n: n.data.num_indent * 1000000 - len(n.children)
                )
            chosen_node = im_dir_nodes.pop()
            chosen_node.accept(hide_node)
            chosen_node.detach()

    def collapse_empty_directories(self):
        tree_root = self._as_tree(self._shown_lines())
        empty_directories = []
        while True:
            # Empty directories are those: leaf directories without any children
            curr_empty_dirs = [
                node
                for node in tree_root.leaves()
                if node.data.is_dir and node.data not in empty_directories
            ]
            if len(curr_empty_dirs) == 0:
                break
            empty_directories.extend(node.data for node in curr_empty_dirs)
            for node in curr_empty_dirs:
                node.detach()
        for line in empty_directories:
            self._hide_line(line)

    @staticmethod
    def _as_tree(all_lines):
        tree_root = TreeNode(FileLine(-1, "/", None, is_dir=True))
        stack: List[TreeNode] = [tree_root]
        for curr_line in all_lines:
            while curr_line.num_indent <= stack[-1].data.num_indent:
                stack.pop()
            curr_node = TreeNode(curr_line, stack[-1])
            stack.append(curr_node)
        return tree_root

    def to_str(self, skip_files: bool = False):
        tree_str_items = []
        for line in self._shown_lines():
            if skip_files and not line.is_dir:
                continue
            line_text = (
                line.text.split("/")[-2] + FileTree.DIRECTORY_LINE_ENDINGS
                if line.is_dir
                else line.text
            )
            tree_str_items.append(("  " * line.num_indent) + line_text)
        return "\n".join(tree_str_items)

    def __str__(self):
        return self.to_str(skip_files=False)
