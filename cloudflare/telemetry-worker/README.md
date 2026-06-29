# Yeehe Telemetry Worker

这个目录是 `译禾工具合集 / Yeehe Toolkit Suite` 的匿名埋点接收端。

## 作用

- 接收发布版发来的匿名事件批次
- 只累计次数，不保存文本内容、文件名、路径、账号或密钥
- 按 `日期 + 事件名 + 版本号` 聚合写入 D1

## 已接好的本地上报地址

- Worker URL: `https://yeehe-telemetry.willwong0908.workers.dev/collect`

## 当前统计项

- `tool_open.home_guide`
- `tool_open.text_preprocess`
- `tool_open.ai_review`
- `tool_open.cross_excel`
- `task_start.ai_tool`
- `task_success.ai_tool`
- `task_fail.ai_tool`
- `model_mode.thinking_enabled`
- `model_tier.flash`
- `model_tier.pro`
- `task_start.text_preprocess`
- `task_success.text_preprocess`
- `task_fail.text_preprocess`
- `task_mode.term_extract`
- `task_mode.nontrans_only`
- `feature_used.nontrans_regex_generated`
- `feature_used.nontrans_regex_imported`
- `feature_used.nontrans_regex_discarded`
- `task_start.ai_review`
- `task_success.ai_review`
- `task_fail.ai_review`
- `task_mode.general_review`
- `task_mode.directional_review`
- `task_option.blocked_terms_enabled`
- `task_action.cross_excel_search`
- `task_action.cross_excel_merge`

## 当日使用总量规则

“当日使用总量” 不再统计当天所有埋点事件之和。
现在只统计“开始一次具体工具任务”的事件：

- `task_start.text_preprocess`
- `task_start.ai_review`
- `task_action.cross_excel_search`
- `task_action.cross_excel_merge`
- `diff.compare.start`

其他事件例如打开页签、成功/失败、模型档位、思考模式、跳转、导入规则等，都会继续保留为独立统计项，但不会再计入“当日使用总量”。

## 部署步骤

1. 进入本目录。
2. 首次建表：
   `wrangler d1 execute yeehe-telemetry --file=./schema.sql`
3. 发布 Worker：
   `wrangler deploy`

## 查看统计

可以直接查询 D1：

```sql
SELECT event_date, event_name, app_version, count
FROM event_counts
ORDER BY event_date DESC, event_name ASC;
```
