# 论文摘要中的方法、样本与结论适用范围

本地文本工作区用于保存研究对象与方法抽取相关的合成记录，并提供基础规范化和词项查看能力。

## 环境

需要 Python 3.11 或更新版本。运行程序仅使用 Python 标准库。测试依赖固定为 pytest 8.3.4，可执行 `python -m pip install -r requirements-dev.txt` 安装。

## 运行

运行 `PYTHONPATH=src python -m nlp_research_method_result_links.desk_cli` 查看当前问题能使用哪些独立试验和文本证据。合成文献用登记号确定试验。没有报出条件的结果显示资料未报告，多个文献版本可保留各自的引用。

从项目根目录执行 `PYTHONPATH=src python -m nlp_research_method_result_links.cli ingest fixtures/records.json` 导入样例，随后执行 `PYTHONPATH=src python -m nlp_research_method_result_links.cli list` 查看记录。工作数据写入 `var/records.json`。业务查询使用 fixtures/business.json 中的初始资料，约定见 fixtures/business-contract.md。执行 `PYTHONPATH=src python -m nlp_research_method_result_links.cli business` 可查看当前业务目录结果。

样例为本地合成文本。记录包含来源、修订号和原文，当前工作区对空白做统一处理，并提供字符及英文词项切分。

## 证据核对口径（desk_cli）

每条陈述按查询的人群、比较条件、结局和分析口径逐项核对，输出四类结论：

| 结论 | 含义 | 可用性定级 |
| --- | --- | --- |
| 直接回答 | 三项范围一致且为非探索性分析（或查询显式纳入探索性证据） | 可直接使用 |
| 范围不同 | 任一已报告的范围项与查询不一致 | 仅作旁证 |
| 资料未报告 | 查询所需的人群、比较条件或结局缺失 | 需查阅全文 |
| 探索性依据 | 范围一致但属于探索性（含亚组、特定校正口径）分析 | 仅作旁证 |

限制与陈述逐条绑定：亚组、探索性、校正口径、样本限制只约束它所在的陈述，
两个亚组陈述不能合并为总体结果，安全性陈述的人群限制也不会复制给功效结论。

勘误按“试验 + 结局”联动：被显式点名的陈述标记为 `explicit`，同试验同结局的
其他文献版本标记为 `trial-outcome`，均降为历史旁证；其他结局的陈述独立保留。
勘误文献上的重述视为更正后的版本，不再被同一份勘误标记。

同一试验的会议摘要与期刊稿分别保留引用，但独立证据数按试验登记号只计一次，
不以文章数量充当重复验证。归属为 `suspected` 的试验进入 `unconfirmed_links`，
不计入独立证据数，也不给出确定的重复验证结论。每条输出保留 `quote` 原文和
`reason` 判定理由，经办人可据此回到原文并说明为何可直接使用、只能作旁证或
需要查阅全文。

## 测试

执行 `python -m pytest -q` 检查规范化、记录持久化、来源筛选与证据核对口径。
