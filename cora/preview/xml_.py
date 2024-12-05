from xml.etree import ElementTree

from cora.preview.base import FilePreview
from cora.preview.internal.xml_element import Elements
from cora.preview.internal.xml_parser import SlowXMLParser


@FilePreview.register(["xml"])
class XMLPreview(FilePreview):
    def __init__(self, file_type: str, file_name: str, file_content: str):
        super().__init__(
            file_type=file_type, file_name=file_name, file_content=file_content
        )
        # TODO: Comments are all lost
        self.xml_tree = ElementTree.fromstring(file_content, parser=SlowXMLParser())
        self.max_kept_depth = 5

    def get_preview(self):
        file_lines = self.file_lines
        last_line_number = -1

        def preview_lines_update_last_number(start_number, end_number, preview):
            nonlocal last_line_number
            for line_number in range(start_number, end_number, 1):
                preview.append(self.preview_line(line_number, file_lines[line_number]))
                last_line_number = line_number

        def traverse_element(element: ElementTree.Element, *, depth):
            nonlocal last_line_number
            preview = []

            # We have reached max kept depth; let's hide all our children.
            if depth + 1 == self.max_kept_depth and len(element) > 0:
                start_number = Elements.start_line_number(element) - 1
                child_start_number = Elements.start_line_number(element[0]) - 1

                if child_start_number > start_number:
                    # Continue from last previewed line until our first child
                    preview_lines_update_last_number(
                        last_line_number + 1, child_start_number, preview
                    )
                else:
                    # Our child and us are in the same line, them we should continue to us
                    preview_lines_update_last_number(
                        last_line_number + 1, start_number + 1, preview
                    )
                end_number = Elements.end_line_number(element) - 1
                child_end_number = Elements.end_line_number(element[-1]) - 1

                if child_end_number > last_line_number:
                    spacing = self.spacing_for_line_number(child_start_number)
                    indentation = self.indentation_of_line(
                        file_lines[child_start_number]
                    )
                    # TODO: Collect children's tags, texts, etc. as terms
                    preview.extend(
                        [
                            spacing + indentation + "...",
                            spacing
                            + indentation
                            + f"(lines {last_line_number + 1}-{child_end_number} are hidden in preview)",
                            spacing + indentation + "...\n",
                        ]
                    )
                    preview_lines_update_last_number(
                        child_end_number + 1, end_number + 1, preview
                    )
                else:
                    preview_lines_update_last_number(
                        last_line_number + 1, end_number + 1, preview
                    )
                return preview

            # Let's preview our children one by one
            for child in element:
                child_start_number = Elements.start_line_number(child) - 1
                child_end_number = Elements.end_line_number(child) - 1
                # This means [start_number, last_line_number] were already processed
                if child_start_number < last_line_number:
                    child_start_number = last_line_number + 1
                # This means the child node was already fully processed
                if child_start_number > child_end_number:
                    continue
                # Continue from last previewed line
                preview_lines_update_last_number(
                    last_line_number + 1, child_start_number, preview
                )
                # The child do not have any further children; let's put its content.
                if len(child) == 0:
                    preview.extend(
                        [
                            self.preview_line(line_number, file_lines[line_number])
                            for line_number in range(
                                child_start_number, child_end_number + 1, 1
                            )
                        ]
                    )
                # Otherwise, let's traverse child's children
                else:
                    preview.extend(traverse_element(child, depth=depth + 1))
                last_line_number = child_end_number

            preview_lines_update_last_number(
                last_line_number + 1,
                (Elements.end_line_number(element) - 1) + 1,
                preview,
            )

            return preview

        return "\n".join(traverse_element(self.xml_tree, depth=0))
