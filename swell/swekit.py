import json
import shutil
import subprocess
import tempfile
from argparse import ArgumentParser
from pathlib import Path
from typing import Tuple, Optional

from datasets import load_dataset

from swell import options
from swell.agents.rewrite.issue import IssueSummarizer
from swell.base.console import get_boxed_console
from swell.base.repos import RepoTup
from swell.config import SwellConfig
from swell.llms.factory import LLMConfig
from swell.options import ArgumentError
from swell.repair import repair
from swell.repo.repo import Repository
from swell.retrv import retrv
from swell.utils import cmdline


def eval_by_swebench(
    instance_id: str,
    patch_str: str,
    _: Repository,
    patched_repo: Repository,
    *args,
    **kwargs,
) -> bool:
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


def load_instance(
    instance_id: str, *, dataset_id: str, split: str
) -> Tuple[dict, dict]:
    raw_dataset = load_dataset(dataset_id, split=split)
    dataset = {x["instance_id"]: x for x in raw_dataset}
    if instance_id not in dataset:
        raise ArgumentError(f"No instance with ID {instance_id} exists in {dataset_id}")
    return dataset, dataset[instance_id]


def download_repo(repo: str, *, commit: str) -> str:
    url = f"https://github.com/{repo}"
    repo_path = tempfile.mkdtemp()
    try:
        cmdline.check_call(f"git clone {url} {repo_path}", timeout=5 * 60)
        cmdline.check_call(f"git -C {repo_path} checkout {commit}")
    except subprocess.CalledProcessError | subprocess.TimeoutExpired:
        raise
    return repo_path


def fix_instance(
    instance_id: str,
    *,
    dataset_id: str,
    use_llm: LLMConfig,
    num_retries: int,
    num_proc: int,
    debug_mode: bool,
    dataset_split: str = "test",
    repo_path: Optional[Path] = None,
) -> Optional[str]:
    # # Setup required configs
    # SwellConfig.FTE_STRATEGY = ...
    # SwellConfig.QSM_STRATEGY = ...

    console = get_boxed_console(
        box_title="SWEKIT",
        box_bg_color=repair.DEBUG_OUTPUT_LOGGING_COLOR,
        debug_mode=True,
    )

    # Get the issue and the repository according to the instance
    console.printb("Loading SWE-bench, the instance, and the repository")
    _, instance = load_instance(instance_id, dataset_id=dataset_id, split=dataset_split)
    issue = instance["problem_statement"]
    repo_org, repo_name = instance["repo"].split("/", maxsplit=1)
    if not repo_path:
        should_download_repo = True
        repo_path = download_repo(instance["repo"], commit=instance["base_commit"])
    else:
        should_download_repo = False
    repo = Repository(RepoTup(repo_org, repo_name, repo_path))
    console.printb(f"The repository has been loaded into: {repo_path}")

    console.printb(
        f"""Retrieving relevant context for the instance ({instance_id}):\n```\n{issue}\n```"""
    )
    retr = retrv.Retriever(
        repo,
        use_llm=use_llm,
        includes=["*.py"],  # We focus on Python for SWE-bench
        rewriter=IssueSummarizer(repo, use_llm=use_llm),
        debug_mode=debug_mode,
    )

    snip_ctx = retr.retrieve(query=issue, files_only=False, num_proc=num_proc)
    console.printb(
        "The retrieved context is:\n" + ("\n".join(["- " + sp for sp in snip_ctx]))
    )

    repa = repair.IssueRepa(repo, use_llm=use_llm, debug_mode=debug_mode)
    console.printb("Generating a plausible patch that can pass the SWE-bench testing")
    patch = repa.try_repair(
        issue,
        issue_id=instance_id,
        snip_paths=snip_ctx,
        eval_func=eval_by_swebench,
        num_retries=num_retries,
        num_proc=num_proc,
        dataset_id=dataset_id,
        dataset_split=dataset_split,
    )
    if patch:
        console.printb(f"The generated patch is: ```diff\n{patch}\n```")
    else:
        console.printb("No available patches are generated.")

    if should_download_repo:
        shutil.rmtree(repo_path)

    return patch


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
    SwellConfig.SCR_ENUM_FNDR_NUM_THREADS = threads

    patch = fix_instance(
        instance,
        dataset_id=dataset,
        dataset_split="test",
        use_llm=use_llm,
        num_proc=procs,
        num_retries=args.max_retries,
        debug_mode=args.verbose,
        repo_path=Path(args.repository) if args.repository else None,
    )

    if args.output and patch:
        with open(args.output, "w") as fou:
            fou.write(patch)


if __name__ == "__main__":
    main()
