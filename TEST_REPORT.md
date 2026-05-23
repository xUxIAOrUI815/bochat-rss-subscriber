# bochat-rss-subscriber 测试报告

## 1. 测试概述

| 项目 | 内容 |
|------|------|
| **被测项目** | bochat-rss-subscriber（BoChat RSS/Atom 订阅器） |
| **项目版本** | 0.1.0 |
| **项目仓库** | https://github.com/xUxIAOrUI815/bochat-rss-subscriber |
| **测试日期** | 2026-05-22 |
| **测试人员** | 徐筱睿 |
| **测试环境** | Windows 11, Python 3.13.3, BoChat Server 10.210.126.58:48080 |

### 1.1 项目简介

bochat-rss-subscriber 是一个社区版 RSS/Atom 订阅 Bot。它读取 TOML 配置文件，定时检查订阅源，并使用 BoChat Python SDK 将新增内容以 Markdown 格式消息转发到指定群聊。

### 1.2 核心功能

- 支持 RSS 2.0 和 Atom feed 格式的解析
- 基于 SHA256 哈希的去重机制（已发送的条目不会重复发送）
- 首次运行不发送历史内容，避免刷屏
- 支持 `max_items_per_check` 限制单次发送数量
- 支持 dry-run 模式（仅打印，不调用 BoChat API）
- 支持 `file://` 协议读取本地文件
- 支持长期运行模式（`run` 命令，持续轮询）
- 支持命令行动态查询最新条目

## 2. 测试策略

### 2.1 测试分层

```
┌────────────────────────────────────┐
│        集成测试 (Integration)        │
│  真实 BoChat 服务端到端验证            │
├────────────────────────────────────┤
│      补充单元测试 (Supplementary)      │
│  边界条件、异常路径、边缘情况覆盖         │
├────────────────────────────────────┤
│       已有单元测试 (Existing)          │
│  核心功能基础验证                      │
└────────────────────────────────────┘
```

### 2.2 测试范围

| 模块 | 单元测试 | 集成测试 |
|------|----------|----------|
| `config.py` - 配置加载与校验 | 6 | - |
| `rss.py` - RSS 抓取与解析 | 7 | 2 |
| `runner.py` - 业务编排 | 9 | 4 |
| `sender.py` - 消息发送与格式化 | 8 | 2 |
| `state.py` - 状态持久化 | 5 | - |
| `cli.py` - 命令行接口 | - | 手动验证 |

## 3. 测试结果汇总

### 3.1 总体统计

| 指标 | 数值 |
|------|------|
| **测试用例总数** | 45 |
| **通过数** | 45 |
| **失败数** | 0 |
| **跳过数** | 0 |
| **通过率** | **100%** |
| **执行时间** | 22.48s |

### 3.2 分类统计

| 测试类别 | 数量 | 通过 | 备注 |
|----------|------|------|------|
| 已有单元测试 | 12 | 12 | 代码仓库中已有的基础测试 |
| 补充单元测试 | 22 | 22 | 本轮补充的边界/异常路径测试 |
| 集成测试 | 11 | 11 | 对接真实 BoChat 服务器的端到端测试 |

## 4. 详细测试结果

### 4.1 配置模块（config.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_parse_config_defaults | 已有 | PASS |
| test_duplicate_feed_id_rejected | 已有 | PASS |
| test_missing_required_field_rejected | 已有 | PASS |
| test_feed_interval_secs_custom_value | 补充 | PASS |
| test_disabled_feed_excluded_from_enabled | 补充 | PASS |
| test_base_url_without_http_scheme_rejected | 补充 | PASS |

**覆盖点**：配置解析默认值、必填字段校验、重复 ID 检测、自定义轮询间隔、disabled feed 过滤、非法 base_url 拒绝。

### 4.2 RSS 模块（rss.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_parse_feed_content_and_stable_key | 已有 | PASS |
| test_make_item_key_fallback_to_title_and_date | 补充 | PASS |
| test_sort_items_old_to_new | 补充 | PASS |
| test_parse_atom_feed | 补充 | PASS |
| test_fetch_feed_file_protocol | 补充 | PASS |
| test_fetch_real_public_rss_feed | 集成 | PASS |
| test_fetch_real_atom_feed | 集成 | PASS |
| test_fetch_network_error_handled | 集成 | PASS |

**覆盖点**：RSS 2.0 解析、Atom feed 解析、条目 key 稳定性（SHA256）、fallback key 生成（无 id/guid 时）、时间排序、本地文件协议、真实公网 RSS/Atom 源抓取、网络错误处理。

### 4.3 业务编排（runner.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_first_run_marks_seen_without_sending | 已有 | PASS |
| test_max_items_per_check_limits_send_count | 已有 | PASS |
| test_dry_run_does_not_mark_seen | 已有 | PASS |
| test_send_failure_does_not_mark_seen | 已有 | PASS |
| test_latest_returns_items_without_sending | 已有 | PASS |
| test_send_existing_on_first_run_true | 补充 | PASS |
| test_check_all_with_multiple_feeds | 补充 | PASS |
| test_find_feed_raises_for_unknown_id | 补充 | PASS |
| test_latest_items_respects_limit | 补充 | PASS |
| test_runner_preserves_existing_state_on_error | 补充 | PASS |
| test_check_feed_dry_run_with_real_feed | 集成 | PASS |
| test_check_feed_real_send_to_group | 集成 | PASS |
| test_latest_items_with_real_feed | 集成 | PASS |
| test_check_single_feed_with_real_data | 集成 | PASS |
| test_multi_feed_check_all_dry_run | 集成 | PASS |

**覆盖点**：首次运行不发历史、max_items 限流、dry-run 不持久化、发送失败保留状态、latest 查询、send_existing_on_first_run、多 feed 并发检查、未知 feed 异常、真实服务器端到端发送。

### 4.4 消息发送与格式化（sender.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_format_item_message_uses_markdown_human_date_and_plain_summary | 已有 | PASS |
| test_format_item_message_keeps_unparseable_date | 已有 | PASS |
| test_strip_html_empty_and_plain_text | 补充 | PASS |
| test_strip_html_nested_tags | 补充 | PASS |
| test_compact_summary_under_max_len | 补充 | PASS |
| test_compact_summary_truncation | 补充 | PASS |
| test_format_published_at_utc_z_suffix | 补充 | PASS |
| test_format_published_at_with_offset | 补充 | PASS |
| test_dry_run_sender_accumulates_messages | 补充 | PASS |
| test_real_sender_send_text_to_group | 集成 | PASS |
| test_dry_run_sender_no_api_call | 集成 | PASS |

**覆盖点**：Markdown 格式化、HTML 剥离（空/纯文本/嵌套）、摘要截断、多时区日期格式化、不可解析日期保持原样、DryRunSender 消息累积、真实 BoChat Sender 发送并返回 msg_id。

### 4.5 状态持久化（state.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_state_read_write_seen | 已有 | PASS |
| test_state_mark_seen_truncates_when_exceeds_max | 补充 | PASS |
| test_state_handles_corrupted_json | 补充 | PASS |
| test_state_atomic_write_does_not_lose_data | 补充 | PASS |

**覆盖点**：基本读写 seen/last_checked_at、超量 seen 截断（max=1000）、损坏 JSON 容错、原子写入（临时文件 + os.replace）。

### 4.6 错误处理

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_invalid_bot_token_graceful_error | 集成 | PASS |
| test_fetch_network_error_handled | 集成 | PASS |
| test_send_failure_does_not_mark_seen | 已有 | PASS |
| test_runner_preserves_existing_state_on_error | 补充 | PASS |
| test_state_handles_corrupted_json | 补充 | PASS |

## 5. 命令行功能验证（手动测试）

| 命令 | 测试内容 | 结果 |
|------|----------|------|
| `bochat-rss init-config` | 生成默认配置文件 | 通过 |
| `bochat-rss list` | 列出所有订阅源 | 通过 |
| `bochat-rss latest <id>` | 查询最新条目不发送 | 通过 |
| `bochat-rss check --dry-run` | 模拟检查不实际发送 | 通过 |
| `bochat-rss check` | 实际检查并发送到群聊 | 通过 |
| `bochat-rss check-feed <id>` | 单独检查一个源 | 通过 |

## 6. 发现的缺陷

| 编号 | 严重程度 | 描述 | 状态 |
|------|----------|------|------|
| - | - | 未发现缺陷 | - |

> **注**：在测试过程中发现 `check_feed` 在 dry-run 模式下，首次运行（`send_existing_on_first_run=false`）仍会标记已存在条目为"已读"并持久化状态。这是因为首次运行的历史屏蔽逻辑是独立于 dry-run 模式之外的。该行为在功能上是正确的（防止首次运行刷屏），但可能与用户"dry-run 完全无副作用"的直觉预期不完全一致。建议在用户文档中说明此行为。

## 7. 测试覆盖分析

### 7.1 模块覆盖

| 模块 | 函数/方法 | 已覆盖 | 未覆盖 |
|------|-----------|--------|--------|
| `config.py` | 7 | 7 | 0 |
| `rss.py` | 7 | 7 | 0 |
| `runner.py` | 7 | 7 | 0 |
| `sender.py` | 9 | 9 | 0 |
| `state.py` | 6 | 6 | 0 |
| `cli.py` | 5 | 0 | 5（手动验证） |

### 7.2 未覆盖说明

CLI 模块 (`cli.py`) 未编写自动化测试，原因如下：
- CLI 函数均为简单的参数解析 + 委托调用，核心逻辑已在其他模块中充分测试
- CLI 功能已通过集成测试和手动命令验证

## 8. 测试环境配置

```toml
# 集成测试使用的环境变量/配置
base_url = "http://10.210.126.58:48080"
bot_token = "通过环境变量 BOCHAT_BOT_TOKEN 注入"
group_id = "g_4b573125-726f-44ea-8680-dcd6f212e99f"
```

- **BoChat 服务端**：社区主仓库代码，运行于 `10.210.126.58:48080`
- **测试群聊**：`2026软件工程`（公开群，群号 1145141919810）
- **测试 Bot**：`test-rss-bot`，已加入测试群
- **测试用 RSS 源**：Rust Blog (https://blog.rust-lang.org/feed.xml)、GitHub Blog (https://github.blog/feed/)

## 9. 测试结论

### 9.1 总体评估

- 项目代码质量良好，模块划分清晰，依赖注入设计使得测试易于编写
- 单元测试覆盖了所有核心模块的正常路径、边界条件和异常路径
- 集成测试验证了与真实 BoChat 服务端的完整交互流程
- 状态管理机制完善（原子写入、坏 JSON 容错、发送失败不污染状态）
- 45 个自动化测试用例全部通过，通过率 100%

### 9.2 风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| 外部 RSS 源不可靠 | 低 | 当 RSS 源不可达时，该 feed 的下一轮检查会正常重试，不影响其他 feed |
| 网络环境代理限制 | 低 | 仅影响特定外部 URL 的可达性（如 httpbin.org），不影响核心功能 |
| Bot Token 过期 | 低 | 已有明确的错误处理和异常抛出 |

### 9.3 交付建议

项目已经过充分的单元测试和集成测试验证，核心功能正常，状态管理健壮，**建议可以交付**。
