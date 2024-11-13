from typing import List, Optional

from cofa.base.paths import FilePath, SnippetPath
from cofa.base.repos import RepoBase
from cofa.kwe.index import InvertedIndex
from cofa.kwe.tokens import TokenizerBase
from cofa.utils import misc as utils


class KwEng:
    def __init__(self, repo: RepoBase, index: InvertedIndex):
        self._repo = repo
        self._index = index

    def search_snippets(self, query: str, limit: Optional[int] = None) -> List[str]:
        snippet_scores = self._index.bm25_all(query)
        # Update snippet scores according to file scores
        snippet_list = self._repo.get_all_snippets()
        for snippet in snippet_list:
            if snippet not in snippet_scores:
                snippet_scores[snippet] = 0
        # Rank snippets according to each snippet's score
        ranked_snippets = sorted(
            snippet_list, key=lambda sp: snippet_scores[sp], reverse=True
        )
        return ranked_snippets[:limit]

    @classmethod
    def from_repo(cls, repo: RepoBase, tokenizer: TokenizerBase):
        index = InvertedIndex(tokenizer)
        for file in repo.get_all_files():
            file_path = FilePath(repo.repo_path) / file
            file_cont = file_path.read_text(encoding="utf-8", errors="replace")
            file_lines = file_cont.splitlines()
            for snippet in repo.get_all_snippets_of_file(file):
                snp_path = SnippetPath.from_str(snippet)
                snp_cont = "\n".join(
                    file_lines[snp_path.start_line : snp_path.end_line]
                )
                index.index_snippet(str(snp_path), snp_cont)
        return cls(repo, index)

    def save_to_disk(self, file_path):
        return utils.save_object(
            {
                "repo": self._repo.full_name,
                "index": self._index,
            },
            file_path,
        )

    @classmethod
    def load_from_disk(cls, file_path, repo: RepoBase):
        obj = utils.load_object(file_path)
        assert (
            "repo" in obj and obj["repo"] == repo.full_name
        ), f"Repository is not match, expecting {obj['repo']}, got {repo.full_name}"
        assert "index" in obj, "No `index` field in the disk file"
        return cls(repo, obj["index"])
