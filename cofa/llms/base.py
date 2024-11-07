from abc import abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional, List

import pyjson5 as json5

from cofa.base.console import get_boxed_console


@dataclass
class FunctionCall:
    name: Optional[str] = None
    arguments: Optional[str] = None
    reasoning: Optional[str] = None
    pycode: Optional[str] = None

    def to_json(self):
        obj = {}

        if self.name is not None:
            obj["name"] = self.name
        if self.arguments is not None:
            obj["arguments"] = self.arguments
        if self.reasoning is not None:
            obj["reasoning"] = self.reasoning
        if self.pycode is not None:
            obj["pycode"] = self.pycode

        return obj if len(obj) != 0 else None


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "system", "function"]
    content: str = None
    name: Optional[str] = None
    function_call: Optional[FunctionCall] = None

    def to_json(self):
        obj = {"role": self.role, "content": ""}
        if self.content is not None:
            obj["content"] = self.content
        if self.name is not None:
            obj["name"] = self.name
        if self.function_call is not None:
            obj["function_call"] = self.function_call.to_json()
        return obj


class LLMBase:
    DEBUG_OUTPUT_SYSTEM_COLOR = "bright_red"
    DEBUG_OUTPUT_ASSISTANT_COLOR = "bright_yellow"
    DEBUG_OUTPUT_USER_COLOR = "light_cyan1"
    DEBUG_OUTPUT_FUNCTION_COLOR = "light_cyan1"

    def __init__(
        self, *, temperature=0, top_k=50, top_p=0.95, max_tokens=4096, debug_mode=False
    ):
        self.history = []
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.debug_mode = debug_mode
        self.console = get_boxed_console(debug_mode=debug_mode)

    def is_debug_mode(self):
        return self.debug_mode

    def enable_debug_mode(self):
        self.debug_mode = True
        self.console = get_boxed_console(debug_mode=True)

    def disable_debug_mode(self):
        self.debug_mode = False
        self.console = get_boxed_console(debug_mode=False)

    def query(self) -> str:
        r = self.do_query()
        self.append_assistant_message(r)
        return r

    def get_history(self) -> List[ChatMessage]:
        return self.history

    def clear_history(self):
        self.history = []

    def append_system_message(self, content: str):
        self.append_message(ChatMessage(role="system", content=content))

    def append_user_message(self, content: str):
        self.append_message(ChatMessage(role="user", content=content))

    def append_assistant_message(self, content: str):
        self.append_message(ChatMessage(role="assistant", content=content))

    def append_message(self, message: ChatMessage):
        color = {
            "system": LLMBase.DEBUG_OUTPUT_SYSTEM_COLOR,
            "user": LLMBase.DEBUG_OUTPUT_USER_COLOR,
            "function": LLMBase.DEBUG_OUTPUT_FUNCTION_COLOR,
            "assistant": LLMBase.DEBUG_OUTPUT_ASSISTANT_COLOR,
        }[message.role]
        if message.role == "assistant" and message.function_call is not None:
            fn_reason = message.function_call.reasoning
            fn_name = message.function_call.name
            fn_args = message.function_call.arguments
            formatted_message = f"{fn_reason}\n\nCall Function: {fn_name}(**{fn_args})"
        else:
            formatted_message = message.content
        self.console.printb(
            formatted_message, title=message.role.capitalize(), background=color
        )
        self.history.append(message)

    @staticmethod
    def parse_json_response(r, drop_newline_symbol=True):
        try:
            if "{" not in r:
                raise Exception("Missing the left, matching curly brace ({)")
            if "}" not in r:
                raise Exception("Missing the right, matching curly brace (})")
            r = r[
                r.find("{") : r.rfind("}") + 1
            ]  # Skip all preceding and succeeding contents
            # Since we are a JSON object, "\n" takes no effects unless it is within some key's value. However,
            # it can make our JSON parsing fail once it is within a value. For example:
            #     `{\n"a": "value of a", "b": "value of \n b"}`
            # The first "\n" preceding "\"a\"" is valid, but the second "\n" preceding " b" makes the JSON invalid.
            # Indeed, the second one should be "\\n". Since we do not have an approach to distinguish them,
            # we conservatively assume that "\n" do not make a major contribution for the result and discard them.
            if drop_newline_symbol:
                r = r.replace("\n", "  ")
            # We used JSON5 as LLM may generate some JS-style jsons like comments
            return json5.loads(r), None
        except Exception as e:
            return None, getattr(e, "message", str(e))

    @abstractmethod
    def do_query(self) -> str:
        pass
