import ast

from cora.preview import FilePreview


class _PreviewVisitor(ast.NodeVisitor):
    def __init__(self):
        self.lines = []

    def visit_ClassDef(self, node):
        self.lines.append(f"{self.get_indent(node)}class {node.name}:")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        args = ", ".join(arg.arg for arg in node.args.args)
        self.lines.append(f"{self.get_indent(node)}def {node.name}({args}):")

    @staticmethod
    def get_indent(node):
        return " " * node.col_offset


@FilePreview.register(["python"])
class PythonPreview(FilePreview):
    def get_preview(self) -> str:
        tree = ast.parse(self.file_content, filename=self.file_name)
        visitor = _PreviewVisitor()
        visitor.visit(tree)

        return "\n".join(visitor.lines)
