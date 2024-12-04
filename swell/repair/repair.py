import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, Optional, List

from swell.base.console import get_boxed_console
from swell.base.repos import RepoTup
from swell.llms.factory import LLMFactory, LLMConfig
from swell.repair.patch import PatchGen
from swell.repair.refine import SnipRefiner
from swell.repo.repo import Repository
from swell.utils import cmdline
from swell.utils.parallel import parallel

DEBUG_OUTPUT_LOGGING_COLOR = "grey50"
DEBUG_OUTPUT_LOGGING_TITLE = "Repairer"


class PatchEval(Protocol):
    def __call__(
        self,
        issue_id: str,
        patch_str: str,
        original_repo: Repository,
        patched_repo: Repository,
        *args,
        **kwargs,
    ) -> bool: ...


class IssueRepa:
    def __init__(self, repo: Repository, use_llm: LLMConfig, debug_mode: bool = False):
        super().__init__()
        self.repo = repo
        self.use_llm = use_llm
        self.console = get_boxed_console(
            box_title=DEBUG_OUTPUT_LOGGING_TITLE,
            box_bg_color=DEBUG_OUTPUT_LOGGING_COLOR,
            debug_mode=debug_mode,
        )
        self.debug_mode = debug_mode

    def gen_patch(self, issue: str, snip_paths: List[str]) -> Optional[str]:
        self.console.printb(
            "Try generating a plausible patch with below snippet context:\n"
            + "\n".join([f"- {s}" for s in snip_paths])
        )
        pat_gen = PatchGen(
            self.repo,
            llm=LLMFactory.create(self.use_llm),
            debug_mode=self.debug_mode,
        )
        patches = pat_gen.generate(
            issue_text=issue, snip_paths=snip_paths, max_patches=1, context_window=10
        )
        if not patches:
            self.console.printb("Failed. No plausible patches could be generated!")
            return None
        return patches[0]

    def eval_patch(
        self,
        issue_id: str,
        patch_str: str,
        eval_func: PatchEval,
        *args,
        **kwargs,
    ) -> bool:
        tempdir = Path(tempfile.mkdtemp())
        patch_file = tempdir / "patch.diff"
        patched_repo = Repository(
            RepoTup(
                self.repo.repo_org,
                self.repo.repo_name,
                str(tempdir / Path(self.repo.repo_path).name),
            ),
            excludes=self.repo.excludes,
        )
        self.console.printb(
            f"Applying the following plausible patch to the repository {self.repo.repo_path}:\n```diff\n{patch_str}\n```"
        )
        patch_file.write_text(patch_str, encoding="utf-8")
        shutil.copytree(
            self.repo.repo_path, patched_repo.repo_path, dirs_exist_ok=False
        )
        try:
            cmdline.check_call(f"patch -p0 -d {patched_repo.repo_path} -i {patch_file}")
        except subprocess.CalledProcessError as e:
            self.console.printb(f"The generated patch is invalid: {e.stderr}")
            return False
        self.console.printb(
            f"The patched repository is placed at: {patched_repo.repo_path}"
        )
        self.console.printb("Evaluating if the patched repository could pass all tests")
        passed = eval_func(
            issue_id=issue_id,
            patch_str=patch_str,
            original_repo=self.repo,
            patched_repo=patched_repo,
            *args,
            **kwargs,
        )
        if not passed:
            self.console.printb("Failed! The plausible patch failed on some tests!")
        else:
            self.console.printb("Succeeded! The plausible patch passed all tests!")
        shutil.rmtree(tempdir)  # Let's remove the temp directory
        return passed

    def gen_then_eval(
        self,
        issue: str,
        issue_id: str,
        snip_paths: List[str],
        eval_func: PatchEval,
        *args,
        **kwargs,
    ):
        patch = self.gen_patch(issue, snip_paths=snip_paths)
        if not patch:
            return None, False
        passed = self.eval_patch(
            issue_id=issue_id, patch_str=patch, eval_func=eval_func, *args, **kwargs
        )
        return patch, passed

    def try_repair(
        self,
        issue: str,
        issue_id: str,
        snip_paths: List[str],
        eval_func: PatchEval,
        num_retries: int = 20,
        num_proc: int = 1,
        *args,
        **kwargs,
    ) -> Optional[str]:
        refined_paths: List[str] = []
        for retry in range(num_retries):
            patch, passed = self.gen_then_eval(
                issue,
                issue_id=issue_id,
                snip_paths=snip_paths,
                eval_func=eval_func,
                *args,
                **kwargs,
            )

            # We have generated a patch that passed all tests
            if patch and passed:
                return patch
            # No patches are generated, let's just retry for a second time
            elif patch is None:
                continue

            # We generated a patch, but it failed on some tests
            self.console.printb(
                "Refine the snippet context into more in-detail context"
            )

            refined_paths = refined_paths or self._refine_snippet_context(
                issue=issue, snip_paths=snip_paths, num_proc=num_proc
            )
            patch, passed = self.gen_then_eval(
                issue,
                issue_id=issue_id,
                snip_paths=refined_paths,
                eval_func=eval_func,
                *args,
                **kwargs,
            )

            # We have generated a patch that passed all tests
            if patch and passed:
                return patch

            # Let's retry from scratch ....

        self.console.printb(
            "We have generated some patches, but none of them have passed all tests."
        )

        return None

    def _refine_snippet_context(self, issue: str, snip_paths: List[str], num_proc: int):
        results = parallel(
            [
                (self._refine_snippet_path, (issue, sp, num_proc > 1))
                for sp in snip_paths
            ],
            n_jobs=num_proc,
            backend="threading",
        )
        refined_paths = []
        for r in results:
            refined_paths.extend(r)
        return refined_paths

    def _refine_snippet_path(self, issue: str, snip_path: str, disable_debugging: bool):
        self.console.printb(f"Choose relevant lines in snippets: {snip_path}")
        refiner = SnipRefiner(
            LLMFactory.create(self.use_llm), repo=self.repo, surroundings=7
        )
        if disable_debugging:
            refiner.disable_debugging()
        refined_paths, reason = refiner.refine(issue, snip_path)
        self.console.printb(
            f"Snippet path {snip_path} has been refined into:\n"
            + ("\n".join(["- " + p for p in refined_paths]) or "Nothing")
        )
        return refined_paths
