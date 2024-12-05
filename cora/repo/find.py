import os
from typing import List, Optional

import rapidfuzz

from cora.base.paths import FilePath
from cora.base.repos import RepoBase
from cora.utils.generic import CastSelfToThis
from cora.utils.pattern import match_any_pattern


class FindMixin(CastSelfToThis[RepoBase]):
    def find_similar_files(
        self,
        file_path: str,
        limit: int = 10,
        absolute: bool = False,
        includes: Optional[List[str]] = None,
    ) -> List[str]:
        return self._find_similar_paths(
            file_path,
            self.this.get_all_files(),
            limit=limit,
            absolute=absolute,
            includes=includes,
        )

    def find_similar_directories(
        self,
        directory_path: str,
        limit: int = 10,
        absolute: bool = False,
        includes: List[str] = None,
    ) -> List[str]:
        return self._find_similar_paths(
            directory_path,
            self.this.get_all_directories(),
            limit=limit,
            absolute=absolute,
            includes=includes,
        )

    def _find_similar_paths(
        self,
        to_path: str,
        from_path_list: List[str],
        limit: int = 10,
        absolute: bool = False,
        includes: Optional[List[str]] = None,
    ) -> List[str]:
        path_name = FilePath(to_path).name
        if includes:
            from_path_list = [
                path for path in from_path_list if match_any_pattern(path, includes)
            ]
        similar_paths = self._find_similar_names(path_name, from_path_list, limit=limit)
        if absolute:
            return [os.path.join(self.this.repo_path, path) for path in similar_paths]
        else:
            return similar_paths

    @staticmethod
    def _find_similar_names(name: str, name_list: List[str], limit: int = 10):
        sorted_full_scores = sorted(
            name_list,
            key=lambda n: rapidfuzz.fuzz.ratio(name, n) + (101 if name in n else 0),
            reverse=True,
        )
        sorted_part_scores = sorted(
            name_list, key=lambda n: rapidfuzz.fuzz.partial_ratio(name, n), reverse=True
        )
        sorted_final_scores = sorted_full_scores[:limit]
        for s in sorted_part_scores[:limit]:
            if s not in sorted_final_scores:
                sorted_final_scores.append(s)
        return sorted_final_scores
