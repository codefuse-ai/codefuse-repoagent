## CodeFuse Agent (CoFA)

## 📦 Installation

```shell
conda create -f environment.yaml
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

CoFA enforces a series of pre-commit checks that our contributors should follow: 

```shell
pre-commit install  # install pre-commit itself
pre-commit install-hooks  # install our pre-commit hooks
```
