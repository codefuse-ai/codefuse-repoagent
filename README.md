<div align="center">
  <img src="./.github/assets/codefuse.jpg" alt="CodeFuse" width="100%"/>
</div>

<div align="center">
    <h1>CodeFuse Swell</h1>
</div>

<div align="center">

  | [中文](docs/README_zh.md) | [English](README.md) |

</div>

<!-- TODO: Add Badges -->

CodeFuse Swell (or Swell) is a repository-level retrieval-augmented generation agent aiming to address user queries toward a software repository.

---

## 🔥 News

- **[Dec. 1, 2024]** We released Swell's primary component—the upstream retriever CodeFuse Repoet (or Repoet).
- **[Dec. 3, 2024]** We released Swell's downstream issue-fix agent, as well as its SWE-bench variant SWE-kit.

---

## 👏🏻 Overview

Swell utilizes its upstream agentic retriever, CodeFuse Repoet (or Repoet), to fetch relevant context. Then, it adapts these relevant context into task-specific, downstream prompt to effectively generate responses to user queries.

To effectively extract the relevant context—certain lines of code or documentation, referred to as snippets—from the repository, Repoet presents a novel yet simple composite approach. Repoet founds on a classical keyword-based search engine, while it employs modern language models (LMs) for further, assistive refinement. Repoet is built upon the key observation that while classical engines may lack some accuracy, the contexts they retrieve are often close to the actual context (or ground truth) necessary to address a user query. The observation is reflected in twofold:
+ Although not significant, the keyword engine is already able to recall a moderate portion of ground-truth files;
+ The files they retrieve are in close proximity to the ground-truth files in terms of the repository structure, and the last mile can be completed by LLMs.

![Swell's Overview](./.github/assets/overview.png)

The main usage of Swell is to resolve issues. Based on Repoet-retrieved contexts, a simple prompt drove Swell to successfully resolved 95 issues (31.67%) in SWE-bench Lite, where 8 issues are uniquely addressed. This achieved the top ranking among all open-source agents by 23/10/2024 in the leaderboard. The technical report can be found in [arXiv](#).

## 📦 Installation

First create a conda environment:

```shell
conda env create -f environment.yaml
conda activate swell_venv
mv env.template .env  # This saves some environment variables
```

Then ensure your models were downloaded or set up some environment variables in:
- If you'd prefer OpenAI, set up your API key in `.env`
- If you'd prefer HuggingFace, either enable downloading in `.env` or download your models first
- If you'd prefer Ollama, pull your models first

## 🔍 Retrieve Context

Repoet can be executed in separate to retrieve relevant context for a user query:

```shell
python -m swell.repoet      \
    -q <user_query>         \
    -m <lang_model>         \
    <repository>
```

## 🚀 Fix Issues (WIP)

> [!WARNING]
> This section is still working in progress.

Swell supports generating a plausible patch to fix a given issue for a repository:

```shell
python -m swell.swell       \
    -q <issue_text>         \
    -i <issue_id>           \
    -m <lang_model>         \
    -e <eval_script>        \
    --eval-args <eval_args> \
    -M <max_retries>        \
    <repository>
```

If an evaluation script (i.e., `-e`) is provided, Swell generates a patch until the evaluation script considers the issue has been fixed or Swell reaches the max number of allowed attempts. In this context, Swell applies the generated patch on the repository and passes the issue and the new repository's path to the evaluation script. Otherwise, Swell merely generates a plausible patch without evaluating its correctness.

## 🐑 Fix SWE-bench (WIP)

> [!WARNING]
> This section is still working in progress

Swell's SWE-kit supports generating patches for SWE-bench issues. To evaluate if the generated patch can pass SWE-bench, we have to install SWE-bench first:

```shell
git clone git@github.com:princeton-nlp/SWE-bench.git
cd SWE-bench
pip install -e .
```

After that, Swell can generate patches and evaluating the generated patch via SWE-bench.

```shell
python -m swell.swekit      \
    -d <dataset_id>         \
    -m <lang_model>         \
    -M <max_retries>        \
 <instance_id>
```

## 👨‍💻‍ Contributions

Swell enforces a series of pre-commit checks that our contributors should follow. Before contributing to this project, developers are required to install our checkers:

```shell
pre-commit install  # install pre-commit itself
pre-commit install-hooks  # install our pre-commit checkers
```

Below are checkers/hooks we have enabled:
+ Python: We use Ruff's lint and format the code; check [all rules](https://docs.astral.sh/ruff/rules/) if your commits fail. Check [ruff.md](./docs/ruff.md) to configure Ruff in PyCharm.
+ Commit: We apply Conventional Commits to format all commit messages; check [the rules](https://www.conventionalcommits.org/) to configure its format.
+ MISC: We also apply some misc checkers for example YAML.

<!-- Add "Cite Us" -->
