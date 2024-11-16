from typing import Optional, Tuple, List

import pyjson5 as json5

from cofa.llms.base import LLMBase, ChatMessage

SYSTEM_PROMPT_JSON_INSTRUCTION = """\
## Response Format ##

Your response MUST be in the following JSON format:

```
{json_schema}
```

## Your Response ##

"""

INVALID_JSON_OBJECT_MESSAGE = """\
**FAILURE**: Your response is not a valid JSON object: {error_message}.

You response should strictly do follow the following JSON format:

```
{json_schema}
```

Please fix the above shown issues (shown above) and respond again.

## Your Response ##

"""

VIOLATED_JSON_FORMAT_MESSAGE = """\
**FAILURE**: Your responded JSON object violates the given JSON format: {error_message}.

You response should strictly do follow the following JSON format:

```
{json_schema}
```

Please fix the above shown issues (shown above) and respond again.

## Your Response ##

"""


class ReachChatRoundLimitException(Exception):
    def __init__(self, limit: int):
        super().__init__(f"The maximum allowed chat-round limit is {limit}")


class AgentBase:
    def __init__(self, llm: LLMBase, json_schema: Optional[str], *, max_chat_round=10):
        self.llm = llm
        self.json_schema = json_schema
        self.max_chat_round = max_chat_round

    def is_debugging(self) -> bool:
        return self.llm.is_debug_mode()

    def enable_debugging(self):
        self.llm.enable_debug_mode()

    def disable_debugging(self):
        self.llm.disable_debug_mode()

    def get_history(self) -> List[ChatMessage]:
        return self.llm.get_history()

    def run(self, system_prompt: str, *args, **kwargs):
        if self.json_schema:
            return self._run_with_json_schema(system_prompt, *args, **kwargs)
        else:
            return self._run_without_json_schema(system_prompt, *args, **kwargs)

    def _run_without_json_schema(self, system_prompt: str, *args, **kwargs):
        # We're a clean run, so clear all prior chats
        self.llm.clear_history()

        # TODO: Use append_system_message()?
        self.llm.append_user_message(system_prompt)

        for _ in range(self.max_chat_round):
            try:
                response = self.llm.query()
            except Exception:
                continue

            # Parse the response and return results
            return self._parse_response(response, *args, **kwargs)

        return self._default_result_when_reaching_max_chat_round()

    def _run_with_json_schema(self, system_prompt: str, *args, **kwargs):
        assert self.json_schema, "No JSON schema is given"

        # We're a clean run, so clear all prior chats
        self.llm.clear_history()

        # TODO: Use append_system_message()?
        self.llm.append_user_message(
            system_prompt
            + SYSTEM_PROMPT_JSON_INSTRUCTION.format(json_schema=self.json_schema)
        )

        for _ in range(self.max_chat_round):
            try:
                response = self.llm.query()
            except Exception:
                continue

            response, err_msg = self.parse_json_response(response)

            # TODO We need to cleanup all trial-error messages and keep our history clean

            # Not a JSON object, let's try again
            if response is None:
                self.llm.append_user_message(
                    INVALID_JSON_OBJECT_MESSAGE.format(
                        error_message=err_msg, json_schema=self.json_schema
                    )
                )
                continue

            formatted, err_msg = self._check_response_format(response, *args, **kwargs)

            # Violates JSON format, let's try again
            if not formatted:
                self.llm.append_user_message(
                    VIOLATED_JSON_FORMAT_MESSAGE.format(
                        error_message=err_msg, json_schema=self.json_schema
                    )
                )
                continue

            valid, err_prompt = self._check_response_semantics(
                response, *args, **kwargs
            )

            # Invalid response, let's try again
            if not valid:
                self.llm.append_user_message(err_prompt)
                continue

            # Parse the response and return results
            return self._parse_response(response, *args, **kwargs)

        return self._default_result_when_reaching_max_chat_round()

    def _check_response_format(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if the response follow the given JSON schema.
        Return (True, None) if the response follows.
        Otherwise, (False, error_message) if there are violations.
        """
        return True, None

    def _check_response_semantics(
        self, response: dict, *args, **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if the response is valid in terms of the agent's functionality/semantics.
        Return (True, None) if the response is valid.
        Otherwise, (False, error_prompt).
        """
        return True, None

    def _parse_response(self, response: any, *args, **kwargs) -> any:
        """
        Parse the response and return results.
        The results should be of the same type as run().
        """
        return response

    def _default_result_when_reaching_max_chat_round(self):
        """
        The default result to return when the model have reached a max chat round.
        Usually, this indicates that the model fails to output any valid result.
        So be sure to return a value that can indicate an "exit" of running the model.
        The return value should be of the same type as run().
        """
        raise ReachChatRoundLimitException(self.max_chat_round)

    @staticmethod
    def parse_json_response(
        r, drop_newline_symbol=True
    ) -> (Optional[dict], Optional[str]):
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
