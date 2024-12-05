from typing import Type, Tuple, List, Optional

from cora.agents.rewrite.base import RewriterBase
from cora.agents.simple_agent import SimpleAgent
from cora.llms.factory import LLMConfig, LLMFactory
from cora.repo.repo import Repository


class SummaryGen(RewriterBase):
    def __init__(
        self,
        repo: Repository,
        *,
        summarize_prompt: str,
        summarize_returns: List[Tuple[str, Type, str]],
        summarize_summary_key: str,
        evaluate_prompt: Optional[str],
        evaluate_returns: Optional[List[Tuple[str, Type, str]]],
        evaluate_score_key: Optional[str],
        update_prompt: Optional[str],
        update_returns: Optional[List[Tuple[str, Type, str]]],
        update_summary_key: Optional[str],
        use_llm: LLMConfig,
        max_rounds: int = 5,
    ):
        super().__init__(repo)
        self.use_llm = use_llm
        self.max_rounds = max_rounds
        self.sum_prompt = summarize_prompt
        self.sum_returns = summarize_returns
        self.eval_prompt = evaluate_prompt
        self.eval_returns = evaluate_returns
        self.upd_prompt = update_prompt
        self.upd_returns = update_returns
        self.sum_sum_key = summarize_summary_key
        self.eval_score_key = evaluate_score_key
        self.upd_sum_key = update_summary_key

    def rewrite(self, query: str) -> str:
        summary = self.summarize(query)
        if not (
            self.eval_prompt
            and self.eval_returns
            and self.eval_score_key
            and self.upd_prompt
            and self.upd_returns
            and self.upd_sum_key
        ):
            return summary
        for _ in range(self.max_rounds):
            score = self.evaluate(summary, query)
            if score >= 2:
                break
            summary = self.update(summary, query)
        return summary

    def summarize(self, query: str):
        resp = SimpleAgent(
            llm=LLMFactory.create(self.use_llm), returns=self.sum_returns
        ).run(self.sum_prompt.format(query=query, repo=self.repo.full_name))
        return resp[self.sum_sum_key]

    def evaluate(self, summary: str, query: str):
        assert (
            self.eval_prompt and self.eval_returns and self.eval_score_key
        ), "Evaluate cannot be called as no prompt/returns/keys are given"
        resp = SimpleAgent(
            llm=LLMFactory.create(self.use_llm), returns=self.eval_returns
        ).run(self.eval_prompt.format(summary=summary, query=query))
        return resp[self.eval_score_key]

    def update(self, summary: str, query: str):
        assert (
            self.upd_prompt and self.upd_returns and self.upd_sum_key
        ), "Update cannot be called as no prompt/returns/keys are given"
        resp = SimpleAgent(
            llm=LLMFactory.create(self.use_llm), returns=self.upd_returns
        ).run(
            self.upd_prompt.format(
                repo=self.repo.full_name, summary=summary, query=query
            )
        )
        return resp[self.upd_sum_key]


class SummaryGenBuilder:
    def __init__(self):
        self._sum_prompt: Optional[str] = None
        self._sum_returns: Optional[List[Tuple[str, Type, str]]] = None
        self._sum_sum_key: Optional[str] = None
        self._eval_prompt: Optional[str] = None
        self._eval_returns: Optional[List[Tuple[str, Type, str]]] = None
        self._eval_score_key: Optional[str] = None
        self._upd_prompt: Optional[str] = None
        self._upd_returns: Optional[List[Tuple[str, Type, str]]] = None
        self._upd_sum_key: Optional[str] = None

    def with_summarize_prompt(self, prompt: str) -> "SummaryGenBuilder":
        self._sum_prompt = prompt
        return self

    def with_summarize_returns(
        self, returns: List[Tuple[str, Type, str]]
    ) -> "SummaryGenBuilder":
        self._sum_returns = returns
        return self

    def with_summarize_summary_key(self, key: str) -> "SummaryGenBuilder":
        self._sum_sum_key = key
        return self

    def with_evaluate_prompt(self, prompt: str) -> "SummaryGenBuilder":
        self._eval_prompt = prompt
        return self

    def with_evaluate_returns(
        self, returns: List[Tuple[str, Type, str]]
    ) -> "SummaryGenBuilder":
        self._eval_returns = returns
        return self

    def with_evaluate_score_key(self, key: str) -> "SummaryGenBuilder":
        self._eval_score_key = key
        return self

    def with_update_prompt(self, prompt: str) -> "SummaryGenBuilder":
        self._upd_prompt = prompt
        return self

    def with_update_returns(
        self, returns: List[Tuple[str, Type, str]]
    ) -> "SummaryGenBuilder":
        self._upd_returns = returns
        return self

    def with_update_summary_key(self, key: str) -> "SummaryGenBuilder":
        self._upd_sum_key = key
        return self

    def build(self):
        assert self._sum_prompt is not None, "No summarization prompt"
        assert self._sum_sum_key is not None, "No summarization keys"
        assert self._sum_returns is not None, "No summarization returns"

        this = self

        class SummaryGenImpl(SummaryGen):
            def __init__(
                self,
                repo: Repository,
                *,
                use_llm: LLMConfig,
                max_rounds: int = 5,
            ):
                super().__init__(
                    repo=repo,
                    use_llm=use_llm,
                    max_rounds=max_rounds,
                    summarize_prompt=this._sum_prompt,
                    summarize_summary_key=this._sum_sum_key,
                    summarize_returns=this._sum_returns,
                    evaluate_prompt=this._eval_prompt,
                    evaluate_returns=this._eval_returns,
                    evaluate_score_key=this._eval_score_key,
                    update_prompt=this._upd_prompt,
                    update_returns=this._upd_returns,
                    update_summary_key=this._upd_sum_key,
                )

        return SummaryGenImpl
