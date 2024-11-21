from swell.agents.rewrite.base import RewriterBase


class DontRewrite(RewriterBase):
    def rewrite(self, query: str) -> str:
        return query
