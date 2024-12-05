from cora.agents.rewrite.summ import SummaryGenBuilder

SUMMARIZE_PROMPT = """\
## YOUR TASK ##

You are a powerful developer familiar with GitHub issues tasked to summarize issues concisely.
I will give you a real Github issue about the repository: {repo}, \
I need you to generate a query according to the content of the issue, \
which developers can use this query to identify the problem he needs to solve without check the issue.
A good query should:\
1) accurately summarize the "ISSUE"; \
2) be expressed naturally and concisely, without burdening the user with reading; \
3) help me better locate the target files in the repo which need to be modified to solve the issue; \
4) be not more than 40 words, ideally one or two sentences, that captures the essence of the issue's requirements;

## ISSUE ##

{query}

"""

SUMMARIZE_SUMMARY_KEY = "new_query"

SUMMARIZE_RETURNS = [
    (
        "reason",
        str,
        '"the reason why you generate the query that way" // explain in detail, step-by-step',
    ),
    (SUMMARIZE_SUMMARY_KEY, str, "<Your extension or rewriting of the existed query>"),
]


EVALUATE_PROMPT = """\
## YOUR TASK ##

You are a distinguished code developer familiar with Github Issues and bug repair. \
I will give you a "ISSUE" and a "QUERY" which is created by others to summarize the ISSUE, \
and your task is to determine if the given "QUERY" summarize "ISSUE" well, \
and give a score according to your determination.

A query summarize the issue well if developers can use this query to identify the problem he needs to solve without check the issue.\
You should determine your score by the following steps:
1. Think carefully about what problems the issue raises;
2. Analyze if the query include the most important elements of the issue;
3. Check Whether query can be used instead of issue to express the same requirement and whether it is clear to the developer to understand;
4. Conclude if the query summarize the issue well and give a score.

The score (an integer chosen from [0, 1, 2, 3]) represent the extent to which the query summarizes the issue, where
- Score 0: The query is totally irrelevant to the issue;
- Score 1: The query can only cover some important elements which is not enough to help the developers to solve the problem
- Score 2: The query can cover most important elements of issue, and can give developers a basic understanding of the issue
- Score 3: The query can cover all important elements of issue, and achieve the same effect as the issue.

## ISSUE ##

{query}

## QUERY ##

{summary}

"""

EVALUATE_SCORE_KEY = "score"

EVALUATE_RETURNS = [
    (
        "reason",
        str,
        '"the reason why you give the score" // explain in detail, step-by-step',
    ),
    (
        EVALUATE_SCORE_KEY,
        int,
        "<score> // the summarization score; it should be an integer chosen from [0, 1, 2, 3]",
    ),
]


UPDATE_PROMPT = """\
## YOUR TASK ##

You are an experienced developer familiar with GitHub issues tasked to summarize issues concisely.
I will give you a Github issue about the repository: {repo}.
I already have a preliminary version of this query, but I feel it could be improved for clarity and completeness.
Please help me refine or rewrite my existing query to make it more effective for searching and understanding the issue at hand.
A good query should:\
1) accurately summarize the "ISSUE"; \
2) be expressed naturally and concisely, without burdening the user with reading; \
3) help me better locate the target files in the repo which need to be modified to solve the issue; \
4) be not more than 40 words, ideally one or two sentences, that captures the essence of the issue's requirements;

## ISSUE ##

{query}

## EXISTED QUERY ##

{summary}

"""

UPDATE_SUMMARY_KEY = "new_query"

UPDATE_RETURNS = [
    (
        "reason",
        str,
        '"the reason why you give the query that way" // explain in detail, step-by-step',
    ),
    (UPDATE_SUMMARY_KEY, str, "<Your extension or rewriting of the existed query>"),
]


IssueSummarizer = (
    SummaryGenBuilder()
    .with_summarize_prompt(SUMMARIZE_PROMPT)
    .with_summarize_summary_key(SUMMARIZE_SUMMARY_KEY)
    .with_summarize_returns(SUMMARIZE_RETURNS)
    .with_evaluate_prompt(EVALUATE_PROMPT)
    .with_evaluate_score_key(EVALUATE_SCORE_KEY)
    .with_evaluate_returns(EVALUATE_RETURNS)
    .with_update_prompt(UPDATE_PROMPT)
    .with_update_summary_key(UPDATE_SUMMARY_KEY)
    .with_update_returns(UPDATE_RETURNS)
    .build()
)
