import re

import tree_sitter_languages
from tree_sitter import Node, Parser

from swell.preview.base import FilePreview


def _extract_words(string):
    # extract the most common words from a code snippet
    words = re.findall(r"\w+", string)
    return list(dict.fromkeys(words))


@FilePreview.register(
    [
        # See https://github.com/grantjenks/py-tree-sitter-languages/blob/main/tests/test_tree_sitter_languages.py
        "bash",
        "c",
        "c_sharp",
        "commonlisp",
        "cpp",
        "css",
        "dockerfile",
        "dot",
        "elisp",
        "elixir",
        "elm",
        "erlang",
        "fortran",
        "go",
        "gomod",
        "haskell",
        "hcl",
        "html",
        "java",
        "javascript",
        "json",
        "julia",
        "kotlin",
        "lua",
        "make",
        "markdown",
        "objc",
        "ocaml",
        "perl",
        "php",
        "r",
        "rst",
        "ruby",
        "rust",
        "scala",
        "sql",
        "sqlite",
        "toml",
        "typescript",
        "yaml",
    ]
)
class CodePreview(FilePreview):
    def __init__(self, file_type: str, file_name: str, file_content: str):
        super().__init__(
            file_type=file_type, file_name=file_name, file_content=file_content
        )
        parser = Parser()
        parser.set_language(tree_sitter_languages.get_language(file_type))
        self.file_tree = parser.parse(bytes(file_content, "utf8"))
        self.min_line = 5
        self.max_line = 50
        self.num_kept_lines = 2
        self.num_kept_terms = 5

    def get_preview(self):
        file_lines = self.file_lines

        last_line_number = -1

        def traverse_node(node: Node):
            nonlocal last_line_number
            preview_lines = []
            for child in node.children:
                start_number, _ = child.start_point
                end_number, _ = child.end_point
                # This means [start_number, last_line_number] were already processed
                if start_number <= last_line_number:
                    start_number = last_line_number + 1
                # This means the child node was already fully processed
                if start_number > end_number:
                    continue
                # Continue from last previewed line
                for line_number in range(last_line_number + 1, start_number):
                    line = file_lines[line_number]
                    preview_lines.append(self.preview_line(line_number, line))
                    last_line_number = line_number
                # The child node is too large; let's get into its children.
                if end_number - start_number > self.max_line:
                    preview_lines.extend(traverse_node(child))
                # The child node is small enough; let's present all its content.
                elif end_number - start_number < self.min_line:
                    node_lines = file_lines[start_number : end_number + 1]
                    text = "\n".join(
                        [
                            self.preview_line(start_number + i, line)
                            for i, line in enumerate(node_lines)
                        ]
                    )
                    preview_lines.append(text)
                # The child line is within min_line--max_line; let's present its head/tail and hide its body
                else:
                    node_lines = file_lines[start_number : end_number + 1]
                    num_kept_lines = self.num_kept_lines
                    # Keep the starting num_kept_lines
                    preview_lines.extend(
                        [
                            self.preview_line(start_number + i, line)
                            for i, line in enumerate(node_lines[:num_kept_lines])
                        ]
                    )
                    # Hide the middle lines and leave a short message
                    num_extracted_terms = self.num_kept_terms
                    first_n_terms = ", ".join(
                        _extract_words(
                            "\n".join(node_lines[num_kept_lines:-num_kept_lines])
                        )[:num_extracted_terms]
                    )
                    spacing = self.spacing_for_line_number(
                        start_number + num_kept_lines - 1
                    )
                    indentation = self.indentation_of_line(
                        node_lines[num_kept_lines - 1]
                    )
                    preview_lines.extend(
                        [
                            spacing + indentation + "...",
                            spacing
                            + indentation
                            + f"(lines {start_number + num_kept_lines}-{end_number - num_kept_lines} contains terms: {first_n_terms}",
                            spacing + indentation + "...\n",
                        ]
                    )
                    # Keep the ending num_kept_lines
                    preview_lines.extend(
                        [
                            self.preview_line(
                                start_number + (end_number - start_number - 1) + i, line
                            )
                            for i, line in enumerate(node_lines[-num_kept_lines:])
                        ]
                    )
                last_line_number = end_number
            return preview_lines

        return "\n".join(traverse_node(self.file_tree.root_node))
