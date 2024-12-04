import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional, List, Tuple, cast

from swell import options
from swell.agents.rewrite.issue import IssueSummarizer
from swell.base.console import BoxedConsoleBase
from swell.base.rag import GeneratorBase
from swell.cora import RepoAgent
from swell.options import ArgumentError
from swell.repair import repair
from swell.repo.repo import Repository
from swell.utils import cmdline


class EvalScript:
    def __init__(
        self, eval_script: str, eval_args: Optional[str], console: BoxedConsoleBase
    ):
        self.eval_script = eval_script
        self.eval_args = eval_args or ""
        self.console = console

    def __call__(
        self,
        issue_id: str,
        patch_str: str,
        patched_repo: Repository,
        original_repo: Repository,
        *args,
        **kwargs,
    ) -> bool:
        try:
            cmdline.check_call(
                f"{self.eval_script} "
                f"{issue_id} {patch_str} "
                f"{original_repo.repo_path} {patched_repo.repo_path} "
                f"{self.eval_args}",
                timeout=5 * 60,
            )
            return True
        except subprocess.CalledProcessError as e:
            ecode = e.returncode
            emsg = e.stderr
            if emsg:
                emsg = str(emsg, encoding="utf-8").strip()
                self.console.printb(
                    f"The patche does not pass all tests (exit_code={ecode}) with the following errors raised: {emsg}"
                )
            else:
                self.console.printb(
                    f"The patche does not pass all tests (exit_code={ecode})."
                )
            return False


class _Generator(GeneratorBase):
    def __init__(
        self,
        eval_script: Optional[str],
        eval_args: Optional[str],
    ):
        super().__init__()
        self.eval_script = eval_script
        self.eval_args = eval_args

    def generate(self, issue: str, snip_ctx: List[str], **kwargs) -> any:
        assert self.agent, "RepoAgent hasn't been injected. Please invoke inject_agent() before calling this method"
        agent = cast(RepoAgent, self.agent)
        issue_id = kwargs["issue_id"]
        num_retries = kwargs["num_retries"]
        repa = repair.IssueRepa(
            agent.repo,
            use_llm=agent.use_llm,
            debug_mode=agent.debug_mode,
        )
        console = agent.console
        if self.eval_script:
            console.printb(
                f"Generating a plausible patch that passed the evaluation script: {self.eval_script}"
            )
            patch = repa.try_repair(
                issue,
                issue_id,
                snip_ctx,
                EvalScript(self.eval_script, self.eval_args, console),
                num_retries=num_retries,
                num_proc=agent.num_proc,
            )
        else:
            console.printb("Generating a plausible patch (without evaluation script)")
            patch = repa.gen_patch(issue, snip_ctx)
        if patch:
            console.printb(f"The generated patch is: ```diff\n{patch}\n```")
        else:
            console.printb("No available patches are generated.")
        return patch


def parse_eval_script(args) -> Tuple[Optional[str], Optional[str]]:
    eval_script = args.eval_script or None
    if eval_script:
        eval_script_path = Path(eval_script)
        if not eval_script_path.exists():
            raise ArgumentError(f"The evaluation script does not exist: {eval_script}")
        if not eval_script_path.is_file():
            raise ArgumentError(f"The evaluation script is not a file: {eval_script}")
    eval_args = args.eval_args or None
    if eval_args and not eval_script:
        raise ArgumentError(
            "Evaluation args are provided yet the evaluation script is not"
        )
    return eval_script, eval_args


def parse_args():
    parser = ArgumentParser()
    options.make_common_options(parser)
    parser.add_argument(
        "--issue-id",
        "-i",
        required=True,
        type=str,
        help="The ID of the issue, this is used by the evaluation script for referring to the issue.",
    )
    parser.add_argument(
        "--eval-script",
        "-e",
        default="",
        type=str,
        help="Path to a script for evaluating if the patched repository could resolve the issue."
        "The first argument of the script should be the ID of the issue."
        "The second argument of the script is a string of the patch in the format of unified diff."
        "The third argument of the script is an absolute path to the original repository."
        "The fourth argument of the script is an absolute path to the patched repository."
        'All the rest arguments should be passed via "--eval-args"',
    )
    parser.add_argument(
        "--eval-args",
        default="",
        type=str,
        help="Additional arguments passed to the evaluation script",
    )
    parser.add_argument(
        "--max-retries",
        "-M",
        default=20,
        type=int,
        help="The max number of allowed attempts for evaluating the generated patch.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    repo = options.parse_repo(args)
    issue, incl = options.parse_query(args)
    issue_id = args.issue_id

    llm = options.parse_llms(args)

    procs, threads = options.parse_perf(args)

    eval_script, eval_args = parse_eval_script(args)

    gen = _Generator(eval_script=eval_script, eval_args=eval_args)
    swell = RepoAgent(
        name="SWELL",
        repo=repo,
        includes=incl,
        use_llm=llm,
        rewriter=IssueSummarizer(repo, use_llm=llm),
        generator=_Generator(eval_script=eval_script, eval_args=eval_args),
        num_proc=procs,
        num_thread=threads,
        files_as_context=False,
        debug_mode=args.verbose,
    )
    gen.inject_agent(swell)

    swell.run(
        query=issue,
        generation_args={"issue_id": issue_id, "num_retries": args.max_retries},
    )


if __name__ == "__main__":
    main()
