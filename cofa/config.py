import os
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv


class _CofaRetrieverConfigMixin:
    # User Query Search
    UQS_FILE_LIMIT = 10

    # Keyword Engine Search
    KWS_FILE_LIMIT = 5

    # File Tree Search
    FTS_STRATEGY_NAME_NO_FTS = "disable-fts"
    FTS_STRATEGY_NAME_FTD_GU = "files-then-dirs__give-up"
    FTS_STRATEGY_NAME_FTD_TS = "files-then-dirs__try-shrinking"
    FTS_STRATEGY_NAME_DTF_GU = "dirs-then-files__give-up"
    FTS_STRATEGY = FTS_STRATEGY_NAME_FTD_GU
    FTS_FTD_GOING_UPWARD = 2
    FTS_DTF_DIR_LIMIT = 5
    FTS_FILE_LIMIT = 1
    FTS_MAX_FILE_TREE_SIZE = 1500

    # File Snippet Finding
    FSF_SNIPPET_FINDER_NAME_ENUM_FNDR = "enumerative-finder"
    FSF_SNIPPET_FINDER_NAME_LINE_CHOOSER = "line_chooser"
    FSF_SNIPPET_FINDER_NAME_QA_FINDER = "qa-function-finder"
    FSF_SNIPPET_FINDER = FSF_SNIPPET_FINDER_NAME_ENUM_FNDR
    # FSF_SNIPPET_FINDER = FSF_SNIPPET_FINDER_NAME_QA_FINDER
    FSF_ENUM_OR_RANK_FNDR_SNIPPET_SIZE = 100
    FSF_ENUM_OR_RANK_FNDR_NUM_THREADS = 1
    FSF_RANK_FNDR_GROUP_SIZE = 5
    FSF_SNIPPET_DETER_NAME_SNIP_SCORER = "snippet-scorer"
    FSF_SNIPPET_DETER = FSF_SNIPPET_DETER_NAME_SNIP_SCORER
    FSF_SNIP_SCORER_THRESHOLD = 1

    # Overall Results
    FINAL_FILE_LIMIT = 5


class _CofaFileConfigMixin:
    MAX_BYTES_PER_FILE = 240000  # Do not consider files exceeding this size
    MAX_FILES_PER_DIRECTORY = (
        100  # Do not consider directories containing files more than this number
    )
    EXCLUDE_HIDDEN_FILES = True  # Whether to consider hidden files

    EXCLUDED_FILE_NAMES: List[str] = ["gradle-wrapper.properties", "local.properties"]
    EXCLUDED_DIRECTORY_NAMES: List[str] = [
        ".git",
        ".github",
        ".gitlab",
        "venv",
        "__pycache__",
        "node_modules",
        ".gradle",
        ".maven",
        ".mvn",
        ".idea",
        ".vscode",
        ".eclipse",
    ]
    EXCLUDED_SUFFIXES: List[str] = [
        ".min.js",
        ".min.js.map",
        ".min.css",
        ".min.css.map",
        ".tfstate",
        ".tfstate.backup",
        ".jar",
        ".ipynb",
        ".png",
        ".jpg",
        ".jpeg",
        ".download",
        ".gif",
        ".bmp",
        ".tiff",
        ".ico",
        ".mp3",
        ".wav",
        ".wma",
        ".ogg",
        ".flac",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".patch",
        ".patch.disabled",
        ".wmv",
        ".m4a",
        ".m4v",
        ".3gp",
        ".3g2",
        ".rm",
        ".swf",
        ".flv",
        ".iso",
        ".bin",
        ".tar",
        ".zip",
        ".7z",
        ".gz",
        ".bz",
        ".bz2",
        ".rar",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".svg",
        ".parquet",
        ".pyc",
        ".pub",
        ".pem",
        ".ttf",
        ".log",
    ]

    @classmethod
    def should_exclude(cls, path: str) -> bool:
        path = Path(path).resolve()
        if not path.exists():
            return True
        if cls.EXCLUDE_HIDDEN_FILES and path.name.startswith("."):
            return True
        if path.is_file():
            return cls.should_exclude_file(path)
        elif path.is_dir():
            return cls.should_exclude_directory(dir_path=path)
        else:
            return True

    @classmethod
    def should_exclude_file(cls, file_path: Path):
        # Check stems, suffixes, and parents
        if file_path.suffix in cls.EXCLUDED_SUFFIXES:
            return True
        if file_path.stem in cls.EXCLUDED_FILE_NAMES:
            return True
        if file_path.parent.name in cls.EXCLUDED_DIRECTORY_NAMES:
            return True
        try:
            if os.stat(file_path).st_size > cls.MAX_BYTES_PER_FILE:
                return True
        except FileNotFoundError:
            return True
        is_binary = False
        with file_path.open("rb") as fin:
            # noinspection PyTypeChecker
            for block in iter(lambda: fin.read(1024), b""):
                if b"\0" in block:
                    is_binary = True
                    break
        return is_binary

    @classmethod
    def should_exclude_directory(cls, dir_path: Path) -> bool:
        return (
            dir_path.name in cls.EXCLUDED_DIRECTORY_NAMES
            or len(list(dir_path.iterdir())) > cls.MAX_FILES_PER_DIRECTORY
        )


class CofaConfig(_CofaFileConfigMixin, _CofaRetrieverConfigMixin):
    # Additional environments or overridden environments
    _additional_envs_ = {}

    @staticmethod
    def load(env_file: Optional[str] = None):
        load_dotenv(env_file)

    @classmethod
    def get(cls, key: str) -> Optional[str]:
        return cls._additional_envs_.get(key, None) or os.getenv(key, None)

    @classmethod
    def set(cls, key: str, val: str):
        cls._additional_envs_[key] = val
        return True

    @classmethod
    def cache_directory(cls) -> Path:
        return Path(cls.get("CACHE_DIRECTORY_PATH")).resolve()

    @classmethod
    def keyword_index_cache_directory(cls) -> Path:
        keyword_index_cache_directory = CofaConfig.cache_directory() / "keyword_indices"
        if not keyword_index_cache_directory.exists():
            keyword_index_cache_directory.mkdir(parents=True)
        return keyword_index_cache_directory

    @classmethod
    def sanitize_content_in_repository(cls) -> bool:
        return True if cls.get("SANITIZE_CONTENT_IN_REPOSITORY") else False


__ENV_LOADED = False
if not __ENV_LOADED:
    CofaConfig.load()
    __ENV_LOADED = True
