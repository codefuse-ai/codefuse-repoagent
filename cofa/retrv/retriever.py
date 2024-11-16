from collections import defaultdict
from typing import Optional, Set, List, Dict, OrderedDict

from cofa.agents.choose_files import FileChooser
from cofa.agents.explore_tree import FileFinder
from cofa.agents.find_entities import EntDefnFinder
from cofa.agents.rewrite.base import RewriterBase
from cofa.agents.rewrite.dont import DontRewrite
from cofa.agents.score_preview import PreviewScorer
from cofa.agents.snippets.factory import SnipFinderFactory
from cofa.base.console import get_boxed_console
from cofa.base.ftree import FileTree
from cofa.base.paths import FilePath
from cofa.config import CofaConfig
from cofa.llms.factory import LLMFactory, LLMConfig
from cofa.repo.repo import Repository
from cofa.utils.event import EventEmitter
from cofa.utils.misc import CannotReachHereError
from cofa.utils.parallel import parallel

DEBUG_OUTPUT_LOGGING_COLOR = "grey50"
DEBUG_OUTPUT_LOGGING_TITLE = "Retriever"


class Retriever(EventEmitter):
    def __init__(
        self,
        repo: Repository,
        *,
        use_llm: LLMConfig,
        includes: Optional[List[str]] = None,
        rewriter: Optional[RewriterBase] = None,
        debug_mode: bool = False,
    ):
        super().__init__()
        self.repo = repo
        self.use_llm = use_llm
        self.incl_pats = includes
        self.rewriter = rewriter or DontRewrite(repo)
        self.console = get_boxed_console(
            box_title=DEBUG_OUTPUT_LOGGING_TITLE,
            box_bg_color=DEBUG_OUTPUT_LOGGING_COLOR,
            debug_mode=debug_mode,
        )

    def lookup_entity_definition(self, query: str, limit: int) -> List[str]:
        self.console.printb(
            "EDL: Analyzing the query to find possible entities and their definition files ..."
        )

        # Lookup plausible code entities (file names in here) from the user query
        finder = EntDefnFinder(query, self.repo, llm=LLMFactory.create(self.use_llm))
        file_names, reason = finder.find()
        file_names = file_names or []

        # Get similar files from the repository according to the file names that the LLM gave
        similar_files = []
        for fn in file_names:
            similar = self.repo.find_similar_files(fn, limit=limit)
            similar_files.extend(similar)
        self.console.printb(
            f"Found {len(similar_files)} similar files according to the file names given"
        )

        if not similar_files:
            self.console.printb("EDL: No plausible definition files are found")
            return []

        # Let LLM choose plausible files from all similar files; 30 at each turn
        defn_files, num_files_per_turn = [], 30
        for file_list in [
            similar_files[i : i + num_files_per_turn]
            for i in range(0, len(similar_files), num_files_per_turn)
        ]:
            chooser = FileChooser(query, self.repo, llm=LLMFactory.create(self.use_llm))
            chosen_files, reason = chooser.choose(file_list)
            if chosen_files:
                self.console.printb(
                    f"LLM chose {len(chosen_files)} plausible definition files:\n"
                    + ("\n".join(["- " + sp for sp in chosen_files]))
                )
                defn_files.extend([f for f in chosen_files if f not in defn_files])
            else:
                self.console.printb("LLM chose nothing")

        self.console.printb(
            f"EDL: Found {len(defn_files)} plausible definition files:\n"
            + ("\n".join(["- " + sp for sp in defn_files]) or "Nothing")
        )

        return defn_files

    def search_keyword_engine(
        self, query: str, limit: int, skipping: Optional[Set[str]] = None
    ):
        self.console.printb(
            "KWS: Searching in keyword engine to find some plausible files ..."
        )

        files = self.repo.search_files(query, limit=limit, includes=self.incl_pats)
        # Skip files that are to be skipped
        files = [f for f in files if f not in skipping]

        self.console.printb(
            f"KWS: Found {len(files)} plausible files:\n"
            + ("\n".join(["- " + f for f in files]) or "Nothing")
        )

        return files

    def explore_file_tree(
        self,
        query: str,
        starting_files: Optional[Set[str]] = None,
        going_upward: Optional[int] = None,
        max_file_tree_size: int = 1500,
        give_up_early: bool = True,
        limit: int = 2147483647,  # By default, let LLMs to find until the very last
    ):
        self.console.printb(
            "FTE: Exploring the file tree by LLMs to find dependent, plausible files ..."
        )

        file_tree = FileTree.from_repository(self.repo, includes=self.incl_pats)

        # Let's search via LLMs from a partial tree constructed from starting files
        if starting_files:
            if going_upward:
                self._reshape_file_tree_upward(
                    file_tree, starting_files=starting_files, upward=2
                )
            else:
                self._reshape_file_tree_heuristics(file_tree, keep_files=starting_files)
        if file_tree.current_size() > max_file_tree_size:
            self.console.printb(
                f"The file tree (size={file_tree.current_size()}) is too large, "
                f"larger than our capability: max_size={max_file_tree_size}."
            )
            if not give_up_early:
                # Try to shrink the file tree heuristically such that LLMs can handle it
                self._shrink_file_tree_heuristics(
                    query, file_tree, size=max_file_tree_size
                )
            if file_tree.current_size() > max_file_tree_size:
                # Give up, otherwise LLMs fail due to limited context window
                return self._give_up_ftree_exploration(
                    query=query,
                    starting_files=starting_files,
                    searched_files=[],
                    file_limit=limit,
                    going_upward=going_upward,
                )

        file_finder = FileFinder(
            query, self.repo, tree=file_tree, llm=LLMFactory.create(self.use_llm)
        )
        # Notify file finder that these files are already found
        file_finder.file_list.extend(starting_files)

        dep_files = []
        while len(dep_files) < limit:
            file, reason = file_finder.next_file()
            if file is None:
                self.console.printb(f"Quit: {reason}")
                break
            self.console.printb(f"Found file {file}: {reason}")
            dep_files.append(file)

        self.console.printb(
            f"FTE: Found {len(dep_files)} plausible, dependent files:\n"
            + ("\n".join(["- " + f for f in dep_files]) or "Nothing")
        )

        return dep_files

    def score_files_by_preview(
        self, query: str, file_list: List[str], num_proc: int = 1
    ) -> Dict[int, List[str]]:
        self.console.printb("FPS: Scoring each file by its preview ...")
        num_proc = 1 if num_proc <= 1 else num_proc

        results = parallel(
            [
                (self.score_file_by_preview, (query, file, file_list, num_proc > 1))
                for file in file_list
            ],
            n_jobs=num_proc,
            backend="threading",
        )

        score_dict = defaultdict(list)
        for file, res in zip(file_list, results):
            score_dict[res[0]].append((file, res[1]))

        return score_dict

    def score_file_by_preview(
        self, query: str, file: str, file_list: List[str], disable_debugging=False
    ):
        scorer = PreviewScorer(
            query=query, repo=self.repo, llm=LLMFactory.create(self.use_llm)
        )
        if disable_debugging:
            scorer.disable_debugging()
        score, reason = scorer.score(file, file_list)
        self.console.printb(f"File {file} is scored {score}: {reason}")
        return score, reason

    def retrieve(self, query, files_only: bool = False, num_proc: int = 1) -> List[str]:
        # Rewrite the query; this may involving summarization, etc.
        query_r = (
            self.rewriter.rewrite(query)
            if len(query.split()) > CofaConfig.QSM_WORD_SIZE
            else query
        )

        # Analyze the query and find all plausible definition files
        edl_res = self.lookup_entity_definition(
            query_r, limit=CofaConfig.EDL_FILE_LIMIT
        )

        # TODO: Perhaps adding vector engines?
        # Search the keyword engine
        kws_res = self.search_keyword_engine(
            query_r, limit=CofaConfig.KWS_FILE_LIMIT, skipping=set(edl_res)
        )

        starting_files = set(edl_res + kws_res)

        # Search other context by LLMs, starting from files found by file name extractor and keyword engine
        if CofaConfig.FTE_STRATEGY in [
            CofaConfig.FTE_STRATEGY_NAME_FTD_GU,
            CofaConfig.FTE_STRATEGY_NAME_FTD_TS,
        ]:
            # We conservatively assume that the files we miss should be around these files (like in the same module)
            # So we go upward some layers and reshape the file tree before performing file finding.
            fte_res = self.explore_file_tree(
                query_r,
                starting_files=starting_files,
                # Just an experienced value
                going_upward=CofaConfig.FTE_FTD_GOING_UPWARD,
                # We will try shrink the file tree if our file tree is too large if our strategy asks us to do so
                give_up_early=(
                    CofaConfig.FTE_STRATEGY == CofaConfig.FTE_STRATEGY_NAME_FTD_GU
                ),
                # Give up searching when the file tree exceeds this number
                max_file_tree_size=CofaConfig.FTE_MAX_FILE_TREE_SIZE,
                limit=CofaConfig.FTE_FILE_LIMIT,
            )
        elif CofaConfig.FTE_STRATEGY == CofaConfig.FTE_STRATEGY_NAME_NO_FTE:
            # Skip file tree exploration
            fte_res = self._give_up_ftree_exploration(
                query_r, starting_files, [], file_limit=CofaConfig.FTE_FILE_LIMIT
            )
        else:
            raise CannotReachHereError(
                f"Unsupported FileTree Search Strategy: {CofaConfig.FTE_STRATEGY}"
            )

        interm_res = list(OrderedDict.fromkeys(edl_res + kws_res + fte_res))
        self.console.printb(
            f"Retrieved {len(interm_res)} plausible files (with false positives):\n"
            + ("\n".join(f"- {f}" for f in interm_res) or "Nothing")
        )

        # Score each plausible by their preview and retain those exceeding a threshold
        file_score = self.score_files_by_preview(
            query_r, file_list=interm_res, num_proc=num_proc
        )
        plausible_files = []
        for sc in sorted(file_score.keys(), reverse=True):
            if sc >= CofaConfig.FPS_PREVIEW_SCORE_THRESHOLD:
                plausible_files.extend([r[0] for r in file_score[sc]])
        self.console.printb(
            f"Retained {len(plausible_files)} plausible files after reading their preview:\n"
            + ("\n".join(f"- {f}" for f in plausible_files) or "Nothing")
        )

        if files_only:
            return plausible_files

        # Find all relevant snippets in each of the found relevant file.
        # Hereafter, we reuse query rather than query_s as we'd avoid information miss.
        snip_context = self._find_relevant_snippets_in_files(
            query, plausible_files, num_proc=num_proc
        )
        self.console.printb(
            f"Retrieved {len(snip_context)} relevant snippets:\n"
            + ("\n".join(f"- {sp}" for sp in snip_context) or "Nothing")
        )

        return snip_context

    def _find_relevant_snippets_in_files(
        self, query: str, files: List[str], num_proc: int = 1
    ) -> List[str]:
        num_proc = 1 if num_proc <= 1 else num_proc
        # TODO: Use "threading" as the backend for now, as the default backend
        #  "locky" got some pickling/unpickling issues for _thread.RLock.
        results = parallel(
            [
                (self._find_relevant_snippets_in_file, (query, file, num_proc > 1))
                for file in files
            ],
            n_jobs=num_proc,
            backend="threading",
        )
        return [sp for res in results for sp in res]

    def _find_relevant_snippets_in_file(
        self, query: str, file: str, disable_debugging=False
    ):
        self.console.printb(f"SCR: Finding relevant snippets in file: {file}")
        snippet_finder = SnipFinderFactory.create(
            CofaConfig.SCR_SNIPPET_FINDER,
            repo=self.repo,
            use_llm=self.use_llm,
            use_determ=CofaConfig.SCR_SNIPPET_DETERM,
            determ_args={"threshold": CofaConfig.SCR_SNIP_SCORER_THRESHOLD},
            console=self.console,
        )
        if disable_debugging:
            snippet_finder.disable_debugging()

        return snippet_finder.find(
            query=query,
            file_path=file,
            num_threads=CofaConfig.SCR_ENUM_FNDR_NUM_THREADS,
            snippet_size=CofaConfig.SCR_ENUM_FNDR_SNIPPET_SIZE,
        )

    def _reshape_file_tree_heuristics(
        self, file_tree: FileTree, *, keep_files: Set[str]
    ):
        self.console.printb(
            "Reshape file tree via heuristics by keeping files:\n"
            + ("\n".join(f"- {sp}" for sp in keep_files) or "Nothing")
        )
        # Let's keep the all such files: for f in included_files: keep all children of
        # - f.parent (f.parent^{1}), f.parent.parent (f.parent^{2}), f.parent^{3},
        # - f.parent^{depth/2} where depth is the depth of this file in file tree
        include_files_or_dirs = []
        for file_path in keep_files:
            file_depth = len(file_path.split("/"))
            for idx in range(file_depth):
                if idx > file_depth // 2:
                    include_files_or_dirs.append(
                        "/".join(file_path.split("/")[:idx])
                        + FileTree.DIRECTORY_LINE_ENDINGS
                    )
            include_files_or_dirs.append(file_path)
        file_tree.reset()
        file_tree.keep_only(include_files_or_dirs)

    def _reshape_file_tree_upward(
        self, file_tree: FileTree, *, starting_files: Set[str], upward: int
    ):
        self.console.printb(
            f"Reshape file tree via going upward ({upward}) from files:\n"
            + ("\n".join(f"- {sp}" for sp in starting_files) or "Nothing")
        )

        # Get the upward parent directory of starting files
        upward_directories = list(
            {self._get_upward_directory(file, upward) for file in starting_files}
        )
        # Prefix a "/" to each directory such that we can merge them
        upward_directories = ["/" + d for d in upward_directories]

        # Sort it such that subdirectories are following their parent directories
        upward_directories.sort()

        self.console.printb(
            "After going upward=2, the directories are:\n"
            + ("\n".join(f"- {sp}" for sp in upward_directories) or "Nothing")
        )

        # Remove all subdirectories, such that the upward_directories contains only common or disjoint directories
        front_ptr = 0
        for back_ptr in range(1, len(upward_directories)):
            if upward_directories[back_ptr].startswith(upward_directories[front_ptr]):
                upward_directories[back_ptr] = None
            else:
                front_ptr += 1
                upward_directories[front_ptr] = upward_directories[back_ptr]
                if front_ptr != back_ptr:
                    upward_directories[back_ptr] = None

        # Remove the prefixed "/" that we have added
        upward_directories = [d[1:] or "/" for d in upward_directories if d is not None]

        self.console.printb(
            "The final upward directories for reshaping the file tree are:\n"
            + ("\n".join(f"- {sp}" for sp in upward_directories) or "Nothing")
        )

        # Reshape the tree
        file_tree.reset()
        file_tree.keep_only(upward_directories)

    def _shrink_file_tree_heuristics(self, query: str, file_tree: FileTree, size: int):
        if file_tree.current_size() <= size:
            return  # It's okay
        self.console.printb(
            f"Shrink file tree heuristically until the size is: <={size}"
        )
        # Collapse irrelevant directories heuristically
        self._collapse_irrelevant_directories_heuristics(query, file_tree)
        # Collapse the tree such that it is not longer than size
        self.console.printb("Collapse progressively the innermost directories")
        file_tree.collapse_innermost_directories_until(size)
        # Let's collapse empty directories too
        self.console.printb("Collapse all empty directories")
        file_tree.collapse_empty_directories()
        self.console.printb(
            f"The file tree after shrink: size={file_tree.current_size()}"
        )

    def _collapse_irrelevant_directories_heuristics(
        self, query: str, file_tree: FileTree
    ):
        # TODO: Perhaps we need a small model to give the correlation between a directory and a query
        #   and we can therefore collapse those with a less correlation.
        # Check if the query is relevant to tests
        test_relevant = "test" in query.lower()
        test_dirs = [
            td
            for pattern in ["*/test/", "*/tests/"]
            for td in file_tree.find_files(pattern, is_dir=True)
        ]
        if test_relevant:
            self.console.printb(
                "The query is relevant to tests; let's collapse all non-test directories."
            )
            # We conservatively assume that a query relevant to tests only recalls test files
            # TODO: This is not safe, as a query related to tests may require context of non-tests
            file_tree.keep_only(test_dirs)
        else:
            self.console.printb(
                "The query is not relevant to tests; let's collapse all test directories."
            )
            # Collapse all directories that are relevant to test
            file_tree.collapse_directories(test_dirs)

    def _give_up_ftree_exploration(
        self, query, starting_files, searched_files, file_limit, *args, **kwargs
    ):
        self.console.printb("FTE: Give up file tree exploration")
        return searched_files

    @staticmethod
    def _get_upward_directory(file: str, upward: int) -> str:
        p = FilePath(file)
        for _ in range(upward):
            p = p.parent
            if str(p) == ".":  # the file parameter is a relative path
                return ""
        return str(p)
