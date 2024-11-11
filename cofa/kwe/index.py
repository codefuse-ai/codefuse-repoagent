import math
from collections import defaultdict, Counter
from typing import Dict

from cofa.kwe.tokens import TokenizerBase


class InvertedIndex:
    def __init__(self, tokenizer: TokenizerBase, bm25_k1=1.2, bm25_b=0.75):
        self.tokenizer = tokenizer
        self._intern = defaultdict(list)  # token -> [(snippet_path, token_count)]
        self._length = {}  # snippet_path -> num_tokens
        self._ave_len = 0.0
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b

    def bm25_all(self, query: str) -> Dict[str, float]:
        bm25 = defaultdict(float)

        # Calculate a BM25 score for each snippet toward the query
        for token in [tok.text for tok in self.tokenizer.tokenize(query)]:
            for sp, tok_cnt in self._intern[token]:
                tf = ((self.bm25_k1 + 1) * tok_cnt) / (
                    tok_cnt
                    + self.bm25_k1
                    * (
                        1
                        - self.bm25_b
                        + self.bm25_b * (self._length[sp] / self._ave_len)
                    )
                )
                idf = math.log10(
                    ((len(self._length) - len(self._intern[token])) + 0.5)
                    / (len(self._intern[token]) + 0.5)
                    + 1.0
                )
                bm25[sp] += idf * tf

        # Normalize all bm25 scores for each snippet toward the query
        mmax, mmin = 1, 0
        if bm25:
            mmax, mmin = max(bm25.values()), min(bm25.values())
        if mmin < mmax:
            mmin = 0
        for snip in bm25.keys():
            bm25[snip] = (bm25[snip] - mmin) / (mmax - mmin)

        return bm25

    def index_snippet(self, snippet: str, content: str):
        tokens = self.tokenizer.tokenize(content)
        # Updating inverted index
        counts = Counter([tok.text for tok in tokens])
        for tok, num in counts.items():
            self._intern[tok].append((snippet, num))
        # Caching length
        self._length[snippet] = len(tokens)
        self._ave_len = sum(self._length.values()) / len(self._length)
