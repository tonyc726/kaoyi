# 考异 / kaoyi

一事多源并列，写明取舍。

静态对照站：AI Coding / Token Plan 的**官方标价**、**社区事件**、**编辑维度**分三层陈列，不合成为一颗星。

A static comparison site for AI coding and token plans. Official list prices, community events, and editorial axes stay three separate layers. No overall star rating.

站点 / Site: <https://tonyc726.github.io/kaoyi/>

Phase 1 只有官方购买按钮。仓库里没有 affiliate ID、没有 `affiliates.yml`、没有 `/go` 跳转。  
Phase 1 ships official buy links only. No affiliate IDs, no `affiliates.yml`, no `/go` redirects in this repo.

## 本地构建 / Build

需要 Python 3.12 与 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync --group dev
uv run python scripts/build.py
uv run pytest
uv run ruff check .
```

可选：抓取官方页（解析失败时保留已有快照，不编造数字）：

```bash
uv run python scripts/fetch.py
```

每日 08:00（Asia/Shanghai，cron `0 0 * * *` UTC）GitHub Action 会对每家 adapter 跑 `scripts/fetch.py`，写入 `data/snapshots/`；只有官方目录价真的变了才新增 `price_change` 事件。今日抓取/解析失败记在 `data/fetch-status.json`（与快照里的 `parse_ok` 分开——保留上次有效数字时快照仍是 `parse_ok=true`），首页在 N>0 时显示「今日失败 N 家」。`workflow_dispatch` 可立刻跑同一条流水线。

GITHUB_TOKEN 提交数据**不会**再触发其他 workflow，所以定时任务在同一次 job 里、用抓取后的工作区构建并部署 Pages，不依赖数据提交去重跑 `pages.yml`。只提交数据产物（snapshots、新事件、fetch-status），不提交 `dist/`。

产物在 `dist/`。GitHub Pages 是项目站，所有内部链接和静态资源走 `/kaoyi/`。

## 启用 GitHub Pages / Enable Pages

工作流会用 `actions/upload-pages-artifact` + `actions/deploy-pages` 发布。

如果第一次部署停在权限/环境上，仓库所有者需要点一次：

1. 打开仓库 **Settings → Pages**
2. **Source** 选 **GitHub Actions**
3. 重新跑 `pages` workflow，或再 push 一次 `main`

不要添加 `CNAME`。不要绑定自定义域名。

If the first deploy needs a click, the repo owner must enable Pages (Source: GitHub Actions) once.

## 社区来源 / Community intake

纠错、新厂商、带方法的实测请开 GitHub Issue（见仓库 Issue 模板）。不抓取 Linux.do、小红书等登录墙后的帖子。

Issues are the community intake. Linux.do and 小红书 login walls are not scraped.

## 数据原则 / Honesty

- 官方页上看不到的数字写成 `-`
- 每个价格格带 `source_url` 与 `as_of`
- OpenAI ChatGPT/Codex 是会员行，不与 OpenAI API 预付合并
- 汇率快照：`config.yml` 里 `usd_to_cny_rate: 6.8`，带日期，不是牌价

## 许可 / License

MIT. See `LICENSE`.
