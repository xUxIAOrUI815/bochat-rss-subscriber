# BoChat RSS Subscriber

BoChat RSS Subscriber 是一个社区版 RSS/Atom 订阅 Bot。它读取配置文件，定时检查订阅源，并使用 BoChat Python SDK 将新增内容以文本消息转发到指定群聊。

## 安装

在主仓库内开发时先安装本仓库 Python SDK，再安装订阅器：

```bash
cd community/bochat-rss-subscriber
python -m pip install -e ../../python-sdk
python -m pip install -e ".[dev]"
```

## 配置

生成示例配置：

```bash
bochat-rss init-config ./config.toml
```

配置字段：

```toml
base_url = "http://127.0.0.1:8080"
bot_token = "b_xxx:1710000000:signature"
state_path = "./rss_state.json"
default_interval_secs = 300
send_existing_on_first_run = false
max_items_per_check = 5

[[feeds]]
id = "rust-blog"
name = "Rust Blog"
url = "https://blog.rust-lang.org/feed.xml"
group_id = "g_xxx"
enabled = true
```

`bot_token` 来自 BoChat Bot 列表接口。`group_id` 是目标群 ID，且该 Bot 必须已加入目标群。

首次运行默认不会发送历史内容，只会把当前已有条目标记为已读，避免刷屏。需要发送历史时，将 `send_existing_on_first_run` 设置为 `true`。

## 使用

列出订阅源：

```bash
bochat-rss list --config config.toml
```

手动查看最新内容，不发送：

```bash
bochat-rss latest rust-blog --config config.toml --limit 5
```

手动检查全部订阅源：

```bash
bochat-rss check --config config.toml
```

手动检查单个订阅源：

```bash
bochat-rss check-feed rust-blog --config config.toml
```

只打印将要发送的内容，不调用 BoChat：

```bash
bochat-rss check --config config.toml --dry-run
```

长期运行：

```bash
bochat-rss run --config config.toml
```

## 状态文件

订阅器使用 `state_path` 指定的 JSON 文件记录每个 RSS 条目的去重 key。消息发送成功后才会标记为已发送；发送失败不会标记，下一轮会重试。

不要提交真实 `config.toml`、`.env` 或 `rss_state.json`。
