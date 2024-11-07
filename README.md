## CodeFuse Agent (CoFA)

## 📦 Installation

```shell
conda create -f environment.yaml
conda activate cofa_venv
```

## 🚀 Fix Issues

CoFA supports generating a plausible patch that might fix a given issue for a repository

```shell
python -m cofa.swell -i <issue_yaml> -e <eval_script> <repository>
```

If an evaluation script is provided, CoFA generates a patch until the evaluation script considers the issue has been fixed or CoFA reaches the max number of allowed attempts. In this context, CoFA applies the generated patch on the repository and passes the issue and the new repository's path to the evaluation script.

```shell
python -m cofa.swell -i <issue_yaml> -e <eval_script> -M 20 <repository>
```

## 🚀 Benchmark SWE-bench

CoFA can try fixing issues in SWE-bench where `<swe-bench-id>` can be one of `lite`, `verified`, and `full`:

```shell
python -m cofa.swekit -i <issue_id> -M 20 <swe-bench-id>
```

## 🔍 Retrieve Context

CoFA's context retriever can be executed in separate. The arguments and options are the same as Swell:

```shell
python -m cofa.repoet -i <issue_yaml> -e <eval_script> <repository>
```

## 👨‍💻‍ Contributions

CoFA enforces a series of pre-commit checks that our contributors should follow. Before contributing to this project, developers are required to install our checkers:

```shell
pre-commit install  # install pre-commit itself
pre-commit install-hooks  # install our pre-commit checkers
```

Below are checkers/hooks we have enabled:
+ Python: We use Ruff's lint and format the code; check [all rules](https://docs.astral.sh/ruff/rules/) if your commits fail. Check [ruff.md](../docs/ruff.md) to configure Ruff in PyCharm.
+ Commit: We apply Conventional Commits to format all commit messages; check [the rules](https://www.conventionalcommits.org/) to configure its format.
+ MISC: We also apply some misc checkers for example YAML.
