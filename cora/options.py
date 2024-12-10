import json
from argparse import ArgumentParser, Action
from pathlib import Path
from typing import Tuple, List

from cora.base.console import BoxedConsoleConfigs
from cora.base.repos import RepoTup
from cora.llms.factory import LLMConfig
from cora.repo.repo import Repository


class ArgumentError(ValueError):
    pass


def _save_options(args: any, file: Path):
    with file.open("w") as fou:
        json.dump(vars(args), fou, ensure_ascii=False, indent=2)


def parse_repo(args: any) -> Repository:
    s = args.repository
    try:
        f, p = s.split(":", maxsplit=1)
        o, n = f.split("/", maxsplit=1)
    except ValueError:
        raise ArgumentError(
            'Invalid argument for "repository". It should be formatted '
            'in "org/name:path" such as "torvalds/linux:/path/to/my/linux/mirror".'
        )
    repo_path = Path(p)
    if not repo_path.exists():
        raise ArgumentError(
            f"The repository does not exist; please check the repository's path: {p}."
        )
    if not repo_path.is_dir():
        raise ArgumentError(
            f"The repository is not a directory; please check the repository's path: {p}."
        )
    return Repository(RepoTup(org=o, name=n, path=p), excludes=(args.excludes or []))


def parse_query(args: any) -> Tuple[str, List[str]]:
    path = Path(args.query)
    if path.exists() and path.is_file():
        query = path.read_text(encoding="utf-8", errors="replace")
    else:
        query = args.query
    includes = args.includes or []
    return query, includes


def parse_llms(args: any) -> LLMConfig:
    try:
        p, m = args.model.split(":", maxsplit=1)
    except ValueError:
        raise ArgumentError(
            'Invalid argument for "--model". It should be in the format '
            'of "provider:model" such as "openai:gpt-4o", "ollama:qwen2:0.5b-instruct".'
        )
    return LLMConfig(
        provider=p,
        llm_name=m,
        debug_mode=args.verbose,
        temperature=args.model_temperature,
        top_k=args.model_top_k,
        top_p=args.model_top_p,
        max_tokens=args.model_max_tokens,
    )


def parse_perf(args: any) -> Tuple[int, int]:
    return args.num_procs, args.num_threads


def parse_logging(args: any):
    if args.log_dir:
        log_dir = Path(args.log_dir)
        if log_dir.exists():
            raise ArgumentError(f"The logging directory already exists: {log_dir}")
        log_dir.mkdir(exist_ok=False, parents=False)
        _save_options(args, file=(log_dir / "commands.json"))
        args.verbose = True  # We enable verbose mode if log_dir is present
        BoxedConsoleConfigs.out_dir = str(log_dir.resolve())
        BoxedConsoleConfigs.print_to_console = True
    else:
        log_dir = None
    return log_dir, args.verbose


def make_repo_options(parser: ArgumentParser) -> List[Action]:
    return [
        parser.add_argument(
            "repository",
            help='The repository in the format of "org/name:path" '
            'such as "torvalds/linux:/path/to/my/linux/mirror"',
        ),
        parser.add_argument(
            "--excludes",
            type=str,
            action="append",
            help="Files (UNIX shell-style patterns) in the repository to "
            "exclude in the whole process; this can be specified multiple times",
        ),
    ]


def make_query_options(parser: ArgumentParser) -> List[Action]:
    return [
        parser.add_argument(
            "--query",
            "-q",
            required=True,
            type=str,
            help="The user query against the repository; "
            "either a simple string or a path to a UTF-8 file saving the query",
        ),
        parser.add_argument(
            "--includes",
            type=str,
            action="append",
            help="Files (UNIX shell-style patterns) to consider when retrieving "
            "relevant context for the user query; this can be specified multiple times",
        ),
    ]


def make_model_options(parser: ArgumentParser) -> List[Action]:
    return [
        parser.add_argument(
            "--model",
            "-m",
            required=True,
            type=str,
            help='The assistive LM in the format of "provider:model" such as '
            '"openai:gpt-4o", "ollama:qwen2:0.5b-instruct"',
        ),
        parser.add_argument(
            "--model-temperature",
            "-T",
            default=0.8,
            type=float,
            help="Parameter temperature controlling the LM's generation",
        ),
        parser.add_argument(
            "--model-top-k",
            "-K",
            default=50,
            type=int,
            help="Parameter top-k controlling the LM's generation",
        ),
        parser.add_argument(
            "--model-top-p",
            "-P",
            default=0.95,
            type=float,
            help="Parameter top-p controlling the LM's generation",
        ),
        parser.add_argument(
            "--model-max-tokens",
            "-L",
            default=1024,
            type=int,
            help="Parameter max-tokens controlling the LM's maximum number of tokens to generate",
        ),
    ]


def make_perf_options(parser: ArgumentParser) -> List[Action]:
    return [
        parser.add_argument(
            "--num-procs",
            "-j",
            default=1,
            type=int,
            help="The maximum number of processes to use in parallel",
        ),
        parser.add_argument(
            "--num-threads",
            "-t",
            default=1,
            type=int,
            help="The maximum number of threads to use in parallel in the each process",
        ),
    ]


def make_logging_options(parser: ArgumentParser) -> List[Action]:
    return [
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging (this includes all interactions with the LM)",
        ),
        parser.add_argument(
            "--log-dir",
            type=str,
            default="",
            help="Store trajectories and logs into the assigned directory; "
            "This option also implies --verbose",
        ),
    ]


def make_common_options(parser: ArgumentParser) -> List[Action]:
    return [
        # Options related to the repository
        *make_repo_options(parser),
        # Options related to the user query
        *make_query_options(parser),
        # Options related to the LM (language model)
        *make_model_options(parser),
        # Options related to performance
        *make_perf_options(parser),
        # Logging options
        *make_logging_options(parser),
    ]
