from xml.etree.ElementTree import Element


class Elements:
    @staticmethod
    def start_point(elem: Element) -> int:
        # noinspection PyTypeChecker
        return elem.attrib["start_point"]

    @staticmethod
    def start_line_number(elem: Element) -> int:
        # noinspection PyTypeChecker
        return elem.attrib["start_point"][0]

    @staticmethod
    def start_column_number(elem: Element) -> int:
        # noinspection PyTypeChecker
        return elem.attrib["start_point"][1]

    @staticmethod
    def end_line_number(elem: Element) -> int:
        # noinspection PyTypeChecker
        return elem.attrib["end_point"][0]

    @staticmethod
    def end_column_number(elem: Element) -> int:
        # noinspection PyTypeChecker
        return elem.attrib["end_point"][1]
