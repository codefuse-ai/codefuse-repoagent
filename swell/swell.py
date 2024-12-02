import os
import shlex
import signal
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional, List, Tuple

from swell import options
from swell.agents.rewrite.issue import IssueSummarizer
from swell.base.console import get_boxed_console, BoxedConsoleBase
from swell.config import SwellConfig
from swell.llms.factory import LLMConfig
from swell.options import ArgumentError
from swell.repair import repair
from swell.repo.repo import Repository
from swell.retrv import retrv


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
            self.check_call(
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

    @classmethod
    def check_call(cls, cmd: str, timeout: int = 5):
        proc = cls.spawn_process(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        proc.check_returncode()

    @classmethod
    def spawn_process(cls, cmd, stdout, stderr, timeout) -> subprocess.CompletedProcess:
        # Fix: subprocess.run(cmd) series methods, when timed out, only send a SIGTERM
        # signal to cmd while does not kill cmd's subprocess. We let each command run
        # in a new process group by adding start_new_session flag, and kill the whole
        # process group such that all cmd's subprocesses are also killed when timed out.
        with subprocess.Popen(
            cmd, stdout=stdout, stderr=stderr, start_new_session=True
        ) as proc:
            try:
                output, err_msg = proc.communicate(timeout=timeout)
            except:  # Including TimeoutExpired, KeyboardInterrupt, communicate handled that.
                cls.safe_killpg(os.getpgid(proc.pid), signal.SIGKILL)
                # We don't call proc.wait() as .__exit__ does that for us.
                raise
            ecode = proc.poll()
        return subprocess.CompletedProcess(proc.args, ecode, output, err_msg)

    @staticmethod
    def safe_killpg(pid, sig):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            pass  # Ignore if there is no such process


def try_repair(
    issue: str,
    issue_id: str,
    repo: Repository,
    *,
    use_llm: LLMConfig,
    eval_script: Optional[str],
    eval_args: Optional[str],
    includes: List[str],
    num_retries: int,
    num_proc: int,
    debug_mode: bool,
):
    # # Setup required configs
    # SwellConfig.FTE_STRATEGY = ...
    # SwellConfig.QSM_STRATEGY = ...

    console = get_boxed_console(
        box_title="SWELL",
        box_bg_color=repair.DEBUG_OUTPUT_LOGGING_COLOR,
        debug_mode=True,
    )

    console.printb(
        f"Loaded repository {repo.repo_org}/{repo.repo_name} from {repo.repo_path} ..."
    )

    console.printb(f"""Retrieving relevant context for the issue:\n```\n{issue}\n```""")
    retr = retrv.Retriever(
        repo,
        use_llm=use_llm,
        includes=includes,
        rewriter=IssueSummarizer(repo, use_llm=use_llm),
        debug_mode=debug_mode,
    )

    snip_ctx = retr.retrieve(query=issue, files_only=False, num_proc=num_proc)
    console.printb(
        "The retrieved context is:\n" + ("\n".join(["- " + sp for sp in snip_ctx]))
    )

    repa = repair.IssueRepa(repo, use_llm=use_llm, debug_mode=debug_mode)
    if eval_script:
        console.printb(
            f"Generating a plausible patch that passed the evaluation script: {eval_script}"
        )
        patch = repa.try_repair(
            issue,
            issue_id,
            snip_ctx,
            EvalScript(eval_script, eval_args, console),
            num_retries=num_retries,
            num_proc=num_proc,
        )
    else:
        console.printb("Generating a plausible patch (without evaluation script)")
        patch = repa.gen_patch(issue, snip_ctx)
    if patch:
        console.printb(f"The generated patch is: ```diff\n{patch}\n```")
    else:
        console.printb("No available patches are generated.")


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
    SwellConfig.SCR_ENUM_FNDR_NUM_THREADS = threads

    eval_script, eval_args = parse_eval_script(args)

    try_repair(
        issue,
        issue_id=issue_id,
        repo=repo,
        includes=incl,
        use_llm=llm,
        eval_script=eval_script,
        eval_args=eval_args,
        num_proc=procs,
        num_retries=args.max_retries,
        debug_mode=args.verbose,
    )


if __name__ == "__main__":
    main()
