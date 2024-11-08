import re
from typing import List

from tree_sitter import Node, Range
from tree_sitter_languages import get_parser

from cofa.base.paths import FilePath, SnippetPath
from cofa.splits.ftypes import parse_ftype
from cofa.splits.splitter import Splitter


class ASTSpl(Splitter):
    """
    An AST- and char-based code splitter based on Kevin Lu's blog:
    - Chunking 2M+ files a day for Code Search using Syntax Trees
    - https://docs.sweep.dev/blogs/chunking-2m-files
    """

    def __init__(self, file: FilePath, snippet_size: int = 1500, min_size: int = 100):
        super().__init__(file)
        self._parser = get_parser(parse_ftype(file.name))
        self._snippet_size = snippet_size
        self._min_size = min_size

    def _do_split(self):
        # Split code along the AST, each splits saving their ranges
        ranges = self._split_ast()
        if len(ranges) == 0:
            return []
        elif len(ranges) == 1:
            return [SnippetPath(self.file, 0, ranges[0].end_point[0] + 1)]

        # Merge overly small ranges into one of their adjacent ranges
        merged_ranges = []
        cur_ran = Range((0, 0), (0, 0), 0, 0)
        for ran in ranges:
            cur_ran = Range(
                cur_ran.start_point, ran.end_point, cur_ran.start_byte, ran.end_byte
            )
            cur_cont = self.content[cur_ran.start_byte : cur_ran.end_byte]
            if len(re.sub(r"\s", "", cur_cont)) > self._min_size and "\n" in cur_cont:
                merged_ranges.append(cur_ran)
                cur_ran = Range(
                    ran.end_point, ran.end_point, ran.end_byte, ran.end_byte
                )
        if cur_ran.end_byte - cur_ran.start_byte > 0:
            merged_ranges.append(cur_ran)

        # Converting from their ranges to their snippets (by line numbers)
        snippets = [
            SnippetPath(self.file, spl.start_point[0], spl.end_point[0])
            for spl in merged_ranges
        ]
        snippets[-1] = SnippetPath(
            self.file, snippets[-1].start_line, snippets[-1].end_line + 1
        )  # Let the last snippet to include the very last line

        return snippets

    def _split_ast(self) -> List[Range]:
        ast = self._parser.parse(self.content.encode("utf-8"))

        # Split recursively, each splits saving their starting and ending point in a range
        ranges = self._split_node(ast.root_node)

        # AST nodes eliminates spaces, we add them back to avoid miss
        ranges[0] = Range((0, 0), ranges[0].end_point, 0, ranges[0].end_byte)
        for i in range(len(ranges) - 1):
            ranges[i] = Range(
                ranges[i].start_point,
                ranges[i + 1].start_point,
                ranges[i].start_byte,
                ranges[i + 1].start_byte,
            )
        ranges[-1] = Range(
            ranges[-1].start_point,
            ast.root_node.end_point,
            ranges[-1].start_byte,
            ast.root_node.end_byte,
        )

        return ranges

    def _split_node(self, node: Node) -> List[Range]:
        ranges: List[Range] = []
        cur_ran = Range(
            node.start_point, node.start_point, node.start_byte, node.start_byte
        )
        for child in node.children:
            # If the current snippet is too big, we add that to our list of splits and empty the bundle
            if child.end_byte - child.start_byte > self._snippet_size:
                ranges.append(cur_ran)
                cur_ran = Range(
                    child.end_point, child.end_point, child.end_byte, child.end_byte
                )
                ranges.extend(self._split_node(child))
            # If the next child node is too big, we recursively chunk the child node and add it to the list of splits
            elif (
                child.end_byte
                - child.start_byte
                + (cur_ran.end_byte - cur_ran.start_byte)
                > self._snippet_size
            ):
                ranges.append(cur_ran)
                cur_ran = Range(
                    child.start_point, child.end_point, child.start_byte, child.end_byte
                )
            # Otherwise, concatenate the current chunk with the child node
            else:
                cur_ran = Range(
                    cur_ran.start_point,
                    child.end_point,
                    cur_ran.start_byte,
                    child.end_byte,
                )
        ranges.append(cur_ran)
        return ranges
