<div align="center">
  <img src="../.github/assets/codefuse.jpg" alt="CodeFuse" width="100%"/>
</div>

<div align="center">
    <h1>CodeFuse RepoAgent</h1>
</div>

<div align="center">

  | [中文](./README_zh.md) | [English](../README.md) |

</div>

<!-- TODO: Add Badges -->

CodeFuse RepoAgent (CoRA) 是一个仓库级检索增强生成（r-RAG）智能体，旨在通过提升 r-RAG 的上游检索（R）能力，进而增强下游大模型的生成（G）能力，并据此回答用户对仓库的查询和提问。CoRA 利用其上游的语义检索智能体 CodeFuse Agentic Retriever (CFAR) 来获取于用户提问紧密相关的上下文信息，随后，它将这些上下文信息转换为特定任务的下游任务提示指令，以有效地生成对用户查询的响应。

---

## 🔥 新闻

- **[2024/12/01]** 我们发布了 CoRA 最核心的上下文检索工具 CodeFuse Agentic Retriever (CFAR)。
- **[2024/12/03]** 我们发布了 CoRA 的缺陷修复工具 FixIt! 和 SWE-kit，其中，SWE-kit 集成 SWE-bench 进行补丁正确性验证。

---

## 👏🏻 简介

CoRA 利用 CFAR 获取与用户提问紧密相关的上下文信息，随后，它将这些上下文信息转换为特定任务的下游任务提示指令，以有效地生成对用户查询的响应。

仓库级检索增强生成（r-RAG）所面临的主要挑战是提取与用户提问紧密相关的上下文信息——即称为“片段上下文”或简称“上下文”的特定代码行或文档行——以有效响应用户的仓库相关查询。虽然目前已经有一些现有方法，但它们存在准确性不足、结果不确定性以及设计复杂且难以实施等局限。为了解决这些问题，CFAR 提出了一种新颖且简单易行的复合方法，将传统的基于关键字的搜索与大语言模型（LLM）相结合，以提升 r-RAG 的语义检索能力。CFAR 的设计基于一个观察：尽管关键字搜索的准确性可能不高，但它所检索出的上下文往往接近于解决用户查询所需的真实上下文（GT, ground truths）。这一观察体现在两个方面：首先，虽然结果并不总是特别好，但关键字搜索仍能够召回相当一部分的 GT 文件；其次，关键字引擎所找到的文件在仓库结构上与 GT 文件距离较为接近，LLM 可以帮助在这些文件的附近进行更有效的查找。CFAR 的工作流程如下：
1. **识别可行文件**：CFAR 首先利用关键字引擎找到一系列可能与用户查询相关的可行文件。这些可行文件为后续基于LLM的优化提供了基础，具体包括：（1）分析用户提问中的代码实体（例如函数和类）和仓库的组织结构，以补充可能在引擎搜索过程中遗漏的可行文件；（2）让 LLM 对每个可行文件进行概览分析，以过滤掉在引擎搜索中错误提及的不相关文件。
2. **检索片段上下文**：接下来，CFAR 利用 LLM 深入检查每个可行文件的具体内容，查找与用户查询相关的片段，并在此阶段对相关片段进行排序和优化。

![CoRA's Overview](../.github/assets/overview.png)

CoRA 的用途之一是仓库级的缺陷修复。基于 CFAR 获取的上下文，CoRA 通过一条简单直接的提示词，便成功促使 GPT-4o 解决了 SWE-bench Lite 中的 95 个问题（31.67%）。在 2024 年 10 月 23 日前，这个结果曾一度在 SWE-bench Lite 开源排行榜上排名第一。我们将 CoRA 的技术报告发表在了 [arXiv](#) 上。

## 📦 安装

首先，创建一个 conda 环境:

```shell
conda env create -f environment.yaml
conda activate cora_venv
mv env.template .env  # This saves some environment variables
```

其次，根据下表进行配置，确保欲使用的库/框架及大模型处于可用状态：
- `√` 代表对应库/框架已经支持。
- `.` 代表对应库/框架正在支持中或未来即将支持。
- `x` 代表暂不考虑支持对应库/框架。

|       库/框架       | 状态 | 配置方式                                      |
|:----------------:|:--:|:------------------------------------------|
|   [OpenAI](#)    | √  | 在 `.env` 中配置 API key 等环境变量                |
|   [Ollama](#)    | √  | 在使用 CoRA 前通过 `ollama pull` 下载所需模型并启动      |
| [HuggingFace](#) | .  | 要么提前下载好模型，要么在 `.env` 中配置允许 HuggingFace 联网 |
| [EasyDeploy](#)  | .  | 未来将支持                                     |


## 🔍 上下文检索

CFAR 可独立用于上下文检索:

```shell
python -m cora.cfar         \
    -q <user_query>         \
    -m <lang_model>         \
    <repository>
```

## 🚀 缺陷修复（WIP）

> [!WARNING]
> This section is still working in progress.

CoRA 的 FixIt! 可以为仓库中的某个缺陷生成修复该缺陷的补丁（patch）:

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

如果提供了评估脚本（即 `-e`），FixIt! 将使用该脚本评估所生成的补丁是否能够通过该脚本的测试。若未通过，FixIt! 将重试，直到生成能够通过该脚本的补丁或达到被允许尝试的最大尝试次数（即 `-M`）。若没有提供评估脚本，，FixIt! 仅生成一个看似合理的补丁，而不评估其正确性。

## 🐑 SWE-bench (WIP)

> [!WARNING]
> This section is still working in progress

CoRA 的 SWE-kit 可以修复 SWE-bench 数据集中的缺陷。为了验证 SWE-kit 生成的补丁是否可以通过 SWE-bench 中收录的测试，首先需要安装 SWE-bench:

```shell
git clone git@github.com:princeton-nlp/SWE-bench.git
cd SWE-bench
pip install -e .
```

然后，便可以用 SWE-kit 尝试为某个缺陷生成补丁：

```shell
python -m cora.swekit       \
    -d <dataset_id>         \
    -m <lang_model>         \
    -M <max_retries>        \
 <instance_id>
```

## 🤖 问题回答

CoRA's RepoQA 可以回答用户针对仓库的提问：

```shell
python -m cora.repoqa       \
    -q <user_query>         \
    -m <lang_model>         \
    <repository>
```

## 👨‍💻‍ 写给开发者

为更好地维护仓库，CoRA 设置了一系列预提交检查，比如代码风格检查、提交信息检查等。因此，在为该项目提交代码之前，开发者需要安装 CoRA 所需的检查工具：

```shell
pre-commit install  # install pre-commit itself
pre-commit install-hooks  # install our pre-commit checkers
```

下面列举了 CoRA 设置的部分检查器:
+ Python：CoRA 使用 ruff 进行代码检查和格式化，[这里](https://docs.astral.sh/ruff/rules/)列举了所有 Ruff 支持的规则。若开发者使用 PyCharm，可根据 [ruff.md](./docs/ruff.md) 进行 ruff 配置。
+ Commit Messages：CoRA 遵循 Conventional Commits 来规范所有提交信息，见[这里](https://www.conventionalcommits.org/)。
+ 其他：CoRA 还应用了一些其他检查工具，例如 YAML 检查。

<!-- Add "Cite Us" -->
