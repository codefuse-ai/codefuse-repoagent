from dataclasses import asdict
from typing import Optional, List

from swell.agents.rewrite.base import RewriterBase
from swell.base.console import get_boxed_console
from swell.base.rag import RAGBase, GeneratorBase
from swell.config import SwellConfig
from swell.llms.factory import LLMConfig
from swell.repo.repo import Repository
from swell.retrv import retrv


class RepoAgent(RAGBase):
    def __init__(
        self,
        repo: Repository,
        *,
        use_llm: LLMConfig,
        rewriter: RewriterBase,
        generator: GeneratorBase,
        includes: Optional[List[str]] = None,
        num_proc: int = 1,
        num_thread: int = 1,
        name: str = "RepoAgent",
        files_as_context: bool = False,
        debug_mode: bool = False,
    ):
        super().__init__(
            name=name,
            retriever=retrv.Retriever(
                repo,
                use_llm=LLMConfig(
                    **{
                        **asdict(use_llm),
                        "temperature": 0,  # Enable greedy decoding
                    }
                ),
                includes=includes,
                rewriter=rewriter,
                debug_mode=debug_mode,
            ),
            generator=generator,
        )
        self.repo = repo
        self.includes = includes
        self.use_llm = use_llm
        self.num_proc = num_proc
        self.num_thread = num_thread
        self.files_as_context = files_as_context
        self.debug_mode = debug_mode
        self.console = get_boxed_console(
            box_title=self.name,
            box_bg_color="grey50",
            debug_mode=debug_mode,
        )
        self.console.printb(
            f"Loaded repository {self.repo.repo_org}/{self.repo.repo_name} from {self.repo.repo_path} ..."
        )

    def before_retrieving(self, query: str, **kwargs):
        self.console.printb(
            f"Retrieving relevant context for the user query:\n```\n{query}\n```"
        )
        # Setup required configs
        SwellConfig.SCR_ENUM_FNDR_NUM_THREADS = self.num_thread
        # SwellConfig.FTE_STRATEGY = ...
        # SwellConfig.QSM_STRATEGY = ...

    def after_retrieving(self, query: str, context: List[str], **kwargs):
        self.console.printb(
            "The retrieved context is:\n" + ("\n".join(["- " + s for s in context]))
        )

    def run(
        self,
        query: str,
        retrieving_args: Optional[dict] = None,
        generation_args: Optional[dict] = None,
    ) -> any:
        return super().run(
            query,
            retrieving_args={
                **(retrieving_args or {}),
                "files_only": self.files_as_context,
                "num_proc": self.num_proc,
            },
            generation_args=generation_args,
        )
