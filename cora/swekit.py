import json
import shutil
import subprocess
import tempfile
from argparse import ArgumentParser
from pathlib import Path
from typing import Tuple, List, Optional, cast

from datasets import load_dataset

from cora import options
from cora.agent import RepoAgent
from cora.agents.rewrite.issue import IssueSummarizer
from cora.base.console import get_boxed_console
from cora.base.rag import GeneratorBase
from cora.base.repos import RepoTup
from cora.llms.factory import LLMConfig
from cora.options import ArgumentError
from cora.repair import repair
from cora.repo.repo import Repository
from cora.utils import cmdline


def eval_by_swebench(
    issue_id: str,
    patch_str: str,
    original_repo: Repository,
    patched_repo: Repository,
    *args,
    **kwargs,
) -> bool:
    instance_id = issue_id
    console = kwargs["console"]

    def _print(m_):
        console.printb(m_, title="SWE-bench")

    dataset_id = kwargs["dataset_id"]
    dataset_split = kwargs["dataset_split"]
    model_name = "swekit"

    patch_hash = hash(patch_str)
    patch_jsonl = (
        Path(patched_repo.repo_path) / f"swekit_patch_{instance_id}_{patch_hash}.jsonl"
    )
    with patch_jsonl.open("w") as fou:
        json.dump(
            {
                "model_name_or_path": model_name,
                "instance_id": instance_id,
                "model_patch": patch_str,
            },
            fou,
            ensure_ascii=False,
            indent=2,
        )
    run_id = f"swekit_{instance_id}_{patch_hash}"
    try:
        cmdline.check_call(
            "python -m swebench.harness.run_evaluation "
            f"--dataset_name {dataset_id} "
            f"--split {dataset_split} "
            f"--predictions_path {patch_jsonl} "
            f"--instance_ids {instance_id} "
            f"--max_workers 2 "
            f"--run_id {run_id}",
            timeout=5 * 60,
        )
    except Exception as e:
        _print(f"Patch evaluation failed: {e}")
        return False
    log_dir = Path(f"logs/run_evaluation/{run_id}/{model_name}/{instance_id}")
    rep_path = log_dir / "report.json"
    if not rep_path.exists():
        return False
    with rep_path.open() as fin:
        rep_res = json.load(fin)
    return rep_res[instance_id]["resolved"]


class _Generator(GeneratorBase):
    def __init__(self, dataset_id: str, dataset_split: str):
        super().__init__()
        self.dataset_id = dataset_id
        self.dataset_split = dataset_split

    def generate(self, issue: str, context: List[str], **kwargs) -> any:
        assert self.agent, "RepoAgent hasn't been injected. Please invoke inject_agent() before calling this method"
        agent = cast(RepoAgent, self.agent)
        instance_id = kwargs["instance_id"]
        num_retries = kwargs["num_retries"]
        repa = repair.IssueRepa(
            agent.repo, use_llm=agent.use_llm, debug_mode=agent.debug_mode
        )
        agent.console.printb(
            "Generating a plausible patch that can pass the SWE-bench testing"
        )
        patch = repa.try_repair(
            issue,
            issue_id=instance_id,
            snip_paths=context,
            eval_func=eval_by_swebench,
            num_retries=num_retries,
            num_proc=agent.num_proc,
            dataset_id=self.dataset_id,
            dataset_split=self.dataset_split,
            console=agent.console,
        )
        if patch:
            agent.console.printb(f"The generated patch is: ```diff\n{patch}\n```")
        else:
            agent.console.printb("No available patches are generated.")
        return patch


class SWEKit:
    def __init__(
        self,
        dataset_id: str,
        *,
        dataset_split: str,
        use_llm: LLMConfig,
        num_proc: int,
        num_thread: int,
        debug_mode: bool,
    ):
        self.dataset_id = dataset_id
        self.dataset_split = dataset_split
        self.dataset = None
        self.use_llm = use_llm
        self.num_proc = num_proc
        self.num_thread = num_thread
        self.debug_mode = debug_mode
        self.console = get_boxed_console(
            box_title="SWEKIT",
            box_bg_color="gray50",
            debug_mode=debug_mode,
        )

    def run(
        self,
        instance_id: str,
        num_retries: int,
        repo_path: Optional[Path] = None,
    ):
        self.console.printb("Loading SWE-bench, the instance, and the repository")

        if not self.dataset:
            self.dataset = self._load_dataset()
        if instance_id not in self.dataset:
            raise ArgumentError(
                f"No instance with ID {instance_id} exists in {self.dataset_id}"
            )

        # Get the issue and the repository according to the instance
        instance = self.dataset[instance_id]
        issue = instance["problem_statement"]
        repo_org, repo_name = instance["repo"].split("/", maxsplit=1)
        if not repo_path:
            should_download_repo = True
            repo_path = self.download_repo(
                instance["repo"], commit=instance["base_commit"]
            )
        else:
            should_download_repo = False
        repo = Repository(RepoTup(repo_org, repo_name, repo_path))
        self.console.printb(f"The repository has been loaded into: {repo_path}")

        # Create an RepoAgent to retrieve context and try resolving the issue
        agent = RepoAgent(
            name="SWEKit",
            repo=repo,
            includes=["*.py"],  # We focus on Python for SWE-bench
            use_llm=self.use_llm,
            rewriter=IssueSummarizer(repo, use_llm=self.use_llm),
            generator=_Generator(self.dataset_id, self.dataset_split),
            num_proc=self.num_proc,
            num_thread=self.num_thread,
            files_as_context=False,
            debug_mode=self.debug_mode,
        )
        patch = agent.run(
            query=issue,
            generation_args={"instance_id": instance_id, "num_retries": num_retries},
        )

        if should_download_repo:
            shutil.rmtree(repo_path)

        return patch

    def _load_dataset(self):
        return {
            x["instance_id"]: x
            for x in load_dataset(self.dataset_id, split=self.dataset_split)
        }

    @staticmethod
    def download_repo(repo: str, *, commit: str) -> str:
        url = f"https://github.com/{repo}"
        repo_path = tempfile.mkdtemp()
        try:
            cmdline.check_call(f"git clone {url} {repo_path}", timeout=5 * 60)
            cmdline.check_call(f"git -C {repo_path} checkout {commit}")
        except subprocess.CalledProcessError | subprocess.TimeoutExpired:
            raise
        return repo_path


def parse_args():
    parser = ArgumentParser()

    parser.add_argument(
        "instance",
        type=str,
        help="The instance ID of the SWE-bench issue to resolve",
    )
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        required=True,
        help='The HuggingFace ID of the SWE-bench dataset for example "princeton-nlp/SWE-bench_Lite" or '
        "the path to the directory saving the SWE-bench Lite dataset.",
    )
    parser.add_argument(
        "--repository",
        "-r",
        type=str,
        default="",
        help="Path to the buggy repository (with already being checked out to the exact buggy commit) of the issue."
        "If this option is provided, we will directly use the repository without downloading it from GitHub.",
    )

    options.make_model_options(parser)
    options.make_perf_options(parser)
    options.make_misc_options(parser)

    parser.add_argument(
        "--max-retries",
        "-M",
        default=20,
        type=int,
        help="The max number of allowed attempts for evaluating the generated patch.",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="Save the generated patch that has passed SWE-bench's evaluation into a patch file",
    )

    return parser.parse_args()


def parse_instance(args: any) -> Tuple[str, str]:
    dataset_id = args.dataset
    dataset_path = Path(dataset_id)
    if dataset_path.exists():
        if not dataset_path.is_dir():
            raise ArgumentError(f"The dataset path is not a directory: {args.dataset}.")
    else:
        pass  # We assume it is a safe HuggingFace dataset id
    return dataset_id, args.instance


def main():
    args = parse_args()

    dataset, instance = parse_instance(args)
    use_llm = options.parse_llms(args)

    procs, threads = options.parse_perf(args)

    swekit = SWEKit(
        dataset,
        dataset_split="test",
        use_llm=use_llm,
        num_proc=procs,
        num_thread=threads,
        debug_mode=args.verbose,
    )
    patch = swekit.run(
        instance,
        num_retries=args.max_retries,
        repo_path=Path(args.repository) if args.repository else None,
    )

    if args.output and patch:
        with open(args.output, "w") as fou:
            fou.write(patch)


if __name__ == "__main__":
    main()
