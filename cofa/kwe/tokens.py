import re
from abc import abstractmethod
from dataclasses import dataclass
from typing import List

_PATTERN_TOKEN = re.compile(r"\b\w+\b")
_PATTERN_VARIABLE = re.compile(r"([A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z]|$))")


@dataclass
class Token:
    text: str
    start: int
    end: int

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text


class TokenizerBase:
    def tokenize(self, text: str) -> List[Token]:
        return self._do_tokenize(text)

    @abstractmethod
    def _do_tokenize(self, text: str) -> List[Token]: ...


class NGramTokenizer(TokenizerBase):
    def __init__(self, ensure_ascii=True, num_gram=3):
        self.ensure_ascii = ensure_ascii
        self.num_gram = num_gram

    def _do_tokenize(self, text: str) -> List[Token]:
        tokens = []
        if self.ensure_ascii:
            unigram = self._tokenize_ascii(text)
        else:
            unigram = self._tokenize_ascii(text)
        tokens.extend(unigram)
        for n in range(2, self.num_gram + 1):
            tokens.extend(self._create_ngram(n, unigram))
        return tokens

    def _tokenize_ascii(self, text: str) -> List[Token]:
        tokens = []

        def append_token_if_valid(text_, start_):
            if text_ and len(text_) > 1:
                tokens.append(
                    Token(
                        text=text_.lower(),
                        start=start_,
                        end=start_ + len(text_),
                    )
                )

        for m in re.finditer(_PATTERN_TOKEN, text):
            tok_text, tok_start = m.group(), m.start()

            # Snakecase token
            if "_" in tok_text:
                offset = 0
                for tok_part in tok_text.split("_"):
                    append_token_if_valid(tok_part.lower(), tok_start + offset)
                    offset += len(tok_part) + 1  # "1" for "_"
            # Camelcase token
            elif tok_parts := _PATTERN_VARIABLE.findall(tok_text):
                offset = 0
                for tok_part in tok_parts:
                    append_token_if_valid(tok_part.lower(), tok_start + offset)
                    offset += len(tok_part)
            # Others
            else:
                append_token_if_valid(tok_text.lower(), tok_start)
        return tokens

    def _tokenize_unicode(self, text: str) -> List[Token]:
        raise NotImplementedError()

    @staticmethod
    def _create_ngram(n: int, tokens: List[Token]) -> List[Token]:
        ngram_toks = []
        pre_toks = []
        for token in tokens:
            if len(pre_toks) == n - 1:
                new_tok = Token(
                    text="_".join([t.text for t in pre_toks] + [token.text]),
                    start=pre_toks[0].start,
                    end=token.end,
                )
                ngram_toks.append(new_tok)
                pre_toks.pop(0)
            pre_toks.append(token)
        return ngram_toks
