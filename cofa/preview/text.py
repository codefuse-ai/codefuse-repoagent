from cofa.preview.base import FilePreview


# TODO: Support adoc in a separate like AdocPreview
@FilePreview.register(["txt", "adoc"])
class TextPreview(FilePreview):
    def __init__(self, file_type: str, file_name: str, file_content: str):
        super().__init__(
            file_type=file_type, file_name=file_name, file_content=file_content
        )

    def get_preview(self) -> str:
        preview = []

        file_lines = self.file_lines
        num_lines = len(self.file_lines)

        # Let's assume paragraphs are divided by "\n\n"
        start_number = 0
        while start_number < num_lines:
            end_number = start_number + 1
            while end_number < num_lines and file_lines[end_number].strip():
                end_number += 1

            para_lines = file_lines[start_number:end_number]
            num_para_lines = end_number - start_number

            if num_para_lines <= 3:
                preview.extend(
                    [
                        self.preview_line_ex(start_number + i, para_lines[i])
                        for i in range(num_para_lines)
                    ]
                )
            else:
                preview.append(self.preview_line_ex(start_number, para_lines[0]))
                spacing = self.spacing_for_line_number(start_number)
                indentation = self.indentation_of_line(para_lines[0])
                preview.append(spacing + indentation + "...")
                preview.append(
                    spacing
                    + indentation
                    + f"(lines {start_number + 1}-{end_number - 2} are hidden in preview)"
                )
                preview.append(spacing + indentation + "...\n")
                preview.append(self.preview_line_ex(end_number - 1, para_lines[-1]))

            if end_number != num_lines:
                preview.append(self.preview_line(end_number, file_lines[end_number]))

            start_number = end_number + 1

        return "\n".join(preview)

    @classmethod
    def preview_line_ex(cls, line_number, line):
        sentences = line.split(".")  # TODO Use NLTK's sent_tokenize() ??
        if sentences[-1] == "":
            sentences = sentences[:-1]
        if len(sentences) == 1 or len(sentences) == 2:
            return cls.preview_line(line_number, line)
        else:
            return cls.preview_line(
                line_number,
                sentences[0]
                + " ... (in-between sentences are hidden in preview) ... "
                + sentences[-1],
            )
