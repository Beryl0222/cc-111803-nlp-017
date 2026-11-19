# 合成文献结论与试验目录业务约定

文献可指向同一试验注册号。样本范围和结果结论逐条登记，勘误绑定它更正的试验或结论。证据查询展示原文定位，不以摘要关键词代替纳入条件。

## 本地目录

业务资料使用 JSON UTF-8 保存。fixtures/records.json 存放原始合成文本，fixtures/business.json 存放初始结构化业务资料，fixtures/work.json 存放一次查询及其陈述。文本原句保留供经办人核对，查询结果不得替代原始来源或历史记录。

## 试验与文献（business.json）

* `trials`：每项试验含 `id`、`registry` 登记号与 `attribution`。
  `confirmed` 为登记关系已确认；`suspected` 为归属存疑，查询只作待确认处理，
  不计入独立证据数。
* `papers`：文献含 `id`、所属 `trial` 与 `kind`，取值为
  `conference`（会议摘要）、`journal`（期刊稿）、`corrigendum`（勘误）。
  会议摘要与期刊稿可同属一个试验，作者表与样本数字允许不完全一致。
* `kind=corrigendum` 的文献通过 `corrections` 登记更正内容：
  `trial` 与 `outcome` 确定联动范围，`targets_claims` 显式点名被更正的陈述，
  `replaces_claim` 指明勘误后以哪条重述为准。勘误只影响同一试验、同一结局的
  陈述，其他结局的陈述仍需独立保留。
* `claims` 为业务目录自身的速查条目，不参与核对计数。

## 查询陈述（work.json）

* `query`：明确 `population`、`comparison`、`outcome`，并通过
  `include_exploratory` 声明是否接受探索性证据。
* `findings` 中每条陈述登记人群、比较条件、结局、`analysis`（主要/探索性）、
  `population_scope`（overall/subgroup）、可选的 `adjustment` 校正口径、
  `sample_note` 样本说明与 `quote` 原文。
* 任一范围项缺失即判“资料未报告”，与“范围不同”“探索性依据”“直接回答”
  严格区分；限制只从陈述自身字段推导并绑定该陈述，不跨陈述复制。
