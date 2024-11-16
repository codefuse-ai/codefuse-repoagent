from typing import Tuple, Type, List

from cofa.agents.base import AgentBase
from cofa.llms.base import LLMBase

JSON_SCHEMA = """\
{{
{props}
}}\
"""


class SimpleAgent(AgentBase):
    def __init__(
        self, llm: LLMBase, returns: List[Tuple[str, Type, str]], *args, **kwargs
    ):
        super().__init__(
            llm=llm,
            json_schema=JSON_SCHEMA.format(
                props="\n".join([f'    "{prop}": {desc}' for prop, _, desc in returns])
            ),
            *args,
            **kwargs,
        )
        self.returns = returns

    def _check_response_format(self, response: dict, *args, **kwargs):
        for ret in self.returns:
            if ret[0] not in response:
                return False, f"'{ret[0]}' is missing in the JSON object"
        return True, None

    def _check_response_semantics(self, response: dict, *args, **kwargs):
        for r in self.returns:
            if isinstance(type(response[r[0]]), r[1]):
                return False, f"{r[0]} should be with type {r[1]}"
        return True, None

    def _parse_response(self, response: dict, *args, **kwargs):
        return {r[0]: response[r[0]] for r in self.returns}
