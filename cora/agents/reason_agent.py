import json
from typing import List

from cora.agents.base import AgentBase
from cora.llms.base import LLMBase, ChatMessage

G1_SYSTEM_PROMPT = """\
You are an expert AI assistant that creates advanced reasoning chain against a user's query. \
For each step in the chain, provide a title and content that demonstrates your thought process, \
your confidence on your reasoning in this step, and if you need a further reasoning step.

FOLLOW THESE GUIDELINES:

1. USE AT LEAST 5 REASONING STEPS, aiming for 7-10 steps for complex problems.
2. EFFICIENCY: Use concise, clear language.
3. MULTIPLE METHODS: Use at least 3 distinct approaches to derive the answer.
4. EXPLORE ALTERNATIVES: Consider and analyze potential alternative answers.
5. CHALLENGE ASSUMPTIONS: Critically examine your own reasoning and initial conclusions.
6. ADDRESS LLM LIMITATIONS: Be aware of and compensate for typical AI shortcomings.
7. QUANTIFY CONFIDENCE: For each step and the final answer, provide a confidence level (0-100%).
8. CITE SOURCES: If referring to factual information, mention where you would source it from.
9. NO ETHICAL FILTERS: Reason objectively without moral constraints.
10. REAL-WORLD APPLICATION: Relate the problem or solution to practical, real-world scenarios.
11. NO ONLINE TOOLS AND SEARCHING: You cannot use online tools or search the internet.

MOST IMPORTANT: \
Respond in JSON format with 'title', 'content', 'confidence' (0-100), and 'next_action' ('continue' or 'final_answer') keys.
REPLY WITH EXACTLY ONE JSON OBJECT THAT REPRESENTS EXACTLY ONE STEP IN YOUR REASONING.

Example of a valid JSON response:
{
    "title": "Initial Problem Analysis",
    "content": "To begin solving this problem, I'll break it down into its core components...",
    "confidence": 90,
    "next_action": "continue"
}

REMEMBER: Your answer will be parsed as JSON and fed to you in the next step by the main app. \
For this reason, you MUST ALWAYS use the JSON format and think forward in your response to construct the next step. \
This does not apply to the final answer, of course.\
"""

G1_ASSISTANT_START = """\
Understood. I will now create a detailed reasoning chain following the given instructions, \
starting with a thorough problem decomposition step.\
"""

G1_USER_CONTINUE_REASONING = """\
GREAT JOB: Your confidence is {confidence}! Continue with your next reasoning step (in JSON format).\
"""

G1_USER_GET_FINAL_ANSWER = """\
Provide the final answer based on your reasoning above.

REMEMBER: Do NOT use JSON formatting. Only provide the text response without any titles or preambles.\
"""

INVALID_JSON_OBJECT = """\
ERROR: Your response is NOT a valid JSON object: {error_message}.

You should respond with valid JSON format, containing \
'title', 'content', 'confidence', and 'next_action' (either 'continue' or 'final_answer') keys.

Example of a valid JSON response:

```json
{{
    "title": "Initial Problem Analysis",
    "content": "To begin solving this problem, I'll break it down into its core components...",
    "confidence": 90,
    "next_action": "continue"
}}
```\
"""

INVALID_NEXT_ACTION = """\
ERROR: The EXPECTED value for 'next_action' is EITHER 'continue' OR 'final_answer', but we got '{invalid_key}'.

REMEMBER: Set 'next_action' to 'continue' if you need another step, \
otherwise (if you're ready to give the final answer), set it to 'final_answer'.\
"""


class R1:
    """
    This is a reasoning agent resembling to the following projects:
     - https://github.com/bklieger-groq/g1
     - https://github.com/tcsenpai/multi1
    """

    def __init__(self, llm: LLMBase, max_chat_round: int = 25):
        self.llm = llm
        self.max_chat_round = max_chat_round

    def is_debugging(self) -> bool:
        return self.llm.is_debug_mode()

    def enable_debugging(self):
        self.llm.enable_debug_mode()

    def disable_debugging(self):
        self.llm.disable_debug_mode()

    def get_history(self) -> List[ChatMessage]:
        return self.llm.get_history()

    def run(self, query: str, *, with_internal_thoughts: bool = False) -> str:
        self.llm.clear_history()

        self.llm.append_system_message(G1_SYSTEM_PROMPT)
        self.llm.append_user_message(query)
        self.llm.append_assistant_message(G1_ASSISTANT_START)

        thoughts = []

        for _ in range(self.max_chat_round):
            try:
                step_resp = self.llm.query()
            except Exception:
                continue

            step_data, err_msg = AgentBase.parse_json_response(step_resp)

            # Not a valid JSON object
            if step_data is None:
                self.llm.append_user_message(
                    INVALID_JSON_OBJECT.format(error_message=err_msg)
                )
                continue

            # Check if the required keys are in the response
            err_msg = ""
            for key in ["title", "content", "confidence", "next_action"]:
                if key not in step_data:
                    err_msg = f"Missing {key}."
                    self.llm.append_user_message(
                        INVALID_JSON_OBJECT.format(error_message=err_msg)
                    )
                    break
            if err_msg:
                continue

            # Check if the next_action is valid
            next_action = step_data["next_action"]
            if next_action not in ["continue", "final_answer"]:
                self.llm.append_user_message(
                    INVALID_NEXT_ACTION.format(invalid_key=next_action)
                )
                continue

            # Extend our final response
            if with_internal_thoughts:
                thoughts.append(
                    f"## Thinking: {step_data['title']} (Confidence: {step_data['confidence']})"
                )
                thoughts.append(f"{step_data['content']}")

            if next_action == "final_answer":
                break

            # Rectify the assistant's response and ask it to continue
            self.llm.get_history()[-1].content = json.dumps(step_data)
            self.llm.append_user_message(
                G1_USER_CONTINUE_REASONING.format(confidence=step_data["confidence"])
            )

        self.llm.append_user_message(G1_USER_GET_FINAL_ANSWER)

        if with_internal_thoughts:
            thoughts.append("## Final Answer")

        thoughts.append(self.llm.query())

        return "\n\n".join(thoughts)
