<div align="center">
  <img src="./.github/assets/codefuse.jpg" alt="CodeFuse" width="100%"/>
</div>

<div align="center">
    <h1>CodeFuse RepoAgent</h1>
</div>

<div align="center">

  | [中文](docs/README_zh.md) | [English](README.md) |

</div>

<!-- TODO: Add Badges -->

CodeFuse RepoAgent (or CoRA) is a repository-level retrieval-augmented generation agent aiming to address user queries toward a software repository.

---

## 🔥 News

- **[Dec. 1, 2024]** We released CoRA's primary component—the upstream retriever CodeFuse Agentic Retriever (or CFAR).
- **[Dec. 3, 2024]** We released CoRA's downstream issue-fixing agent FixIt!, as well as its SWE-bench variant SWE-kit.

---

## 👏🏻 Overview

CoRA utilizes its upstream agentic retriever, CodeFuse Agentic Retriever (or CFAR), to fetch relevant context. Then, it adapts these relevant context into task-specific, downstream prompt to effectively generate responses to user queries.

To effectively extract the relevant context—certain lines of code or documentation, referred to as snippets—from the repository, CFAR presents a novel yet simple composite approach. CFAR founds on a classical keyword-based search engine, while it employs modern language models (LMs) for further, assistive refinement. CFAR is built upon the key observation that while classical engines may lack some accuracy, the contexts they retrieve are often close to the actual context (or ground truth) necessary to address a user query. The observation is reflected in twofold:
+ Although not significant, the keyword engine is already able to recall a moderate portion of ground-truth files;
+ The files they retrieve are in close proximity to the ground-truth files in terms of the repository structure, and the last mile can be completed by LLMs.

![CoRA's Overview](./.github/assets/overview.png)

The main usage of CoRA is to resolve issues. Based on CFAR-retrieved contexts, a simple prompt drove CoRA to successfully resolved 95 issues (31.67%) in SWE-bench Lite, where 8 issues are uniquely addressed. This achieved the top ranking among all open-source agents by 23/10/2024 in the leaderboard. The technical report can be found in [arXiv](#).

## 📦 Installation

First create a conda environment:

```shell
conda env create -f environment.yaml
conda activate cora_venv
mv env.template .env  # This saves some environment variables
```

Then ensure your models were downloaded or set up some environment variables in:
- If you'd prefer OpenAI, set up your API key in `.env`
- If you'd prefer HuggingFace, either enable downloading in `.env` or download your models first
- If you'd prefer Ollama, pull your models first

## 🔍 Retrieve Context

CFAR can be executed in separate to retrieve relevant context for a user query:

```shell
python -m cora.cfar         \
    -q <user_query>         \
    -m <lang_model>         \
    <repository>
```

## 🚀 Fix Issues (WIP)

> [!WARNING]
> This section is still working in progress.

CoRA's FixIt! supports generating a plausible patch to fix a given issue for a repository:

```shell
python -m cora.fixit        \
    -q <issue_text>         \
    -i <issue_id>           \
    -m <lang_model>         \
    -e <eval_script>        \
    --eval-args <eval_args> \
    -M <max_retries>        \
    <repository>
```

If an evaluation script (i.e., `-e`) is provided, FixIt! generates a patch until the evaluation script considers the issue has been fixed or FixIt! reaches the max number of allowed attempts. In this context, FixIt! applies the generated patch on the repository and passes the issue and the new repository's path to the evaluation script. Otherwise, FixIt! merely generates a plausible patch without evaluating its correctness.

## 🐑 Fix SWE-bench (WIP)

> [!WARNING]
> This section is still working in progress

CoRA's SWE-kit supports generating patches for SWE-bench issues. To evaluate if the generated patch can pass SWE-bench, we have to install SWE-bench first:

```shell
git clone git@github.com:princeton-nlp/SWE-bench.git
cd SWE-bench
pip install -e .
```

After that, SWE-kit can generate patches and evaluating the generated patch via SWE-bench.

```shell
python -m cora.swekit       \
    -d <dataset_id>         \
    -m <lang_model>         \
    -M <max_retries>        \
 <instance_id>
```

## 🤖 Answer Questions

CoRA's RepoQA can answer user's questions towards the repository:

```shell
python -m cora.repoqa       \
    -q <user_query>         \
    -m <lang_model>         \
    <repository>
```

## 👨‍💻‍ Contributions

CoRA enforces a series of pre-commit checks that our contributors should follow. Before contributing to this project, developers are required to install our checkers:

```shell
pre-commit install  # install pre-commit itself
pre-commit install-hooks  # install our pre-commit checkers
```

Below are checkers/hooks we have enabled:
+ Python: We use Ruff's lint and format the code; check [all rules](https://docs.astral.sh/ruff/rules/) if your commits fail. Check [ruff.md](./docs/ruff.md) to configure Ruff in PyCharm.
+ Commit: We apply Conventional Commits to format all commit messages; check [the rules](https://www.conventionalcommits.org/) to configure its format.
+ MISC: We also apply some misc checkers for example YAML.

<!-- Add "Cite Us" -->
