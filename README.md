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

产物在 `dist/`。GitHub Pages 是项目站，所有内部链接和静态资源走 `/kaoyi/`。

## 启用 GitHub Pages / Enable Pages

工作流会用 `actions/upload-pages-artifact` + `actions/deploy-pages` 发布。

如果第一次部署停在权限/环境上，仓库所有者需要点一次：

1. 打开仓库 **Settings → Pages**
2. **Source** 选 **GitHub Actions**
3. 重新跑 `pages` workflow，或再 push 一次 `main`

不要添加 `CNAME`。不要绑定自定义域名。

If the first deploy needs a click, the repo owner must enable Pages (Source: GitHub Actions) once.

## 数据原则 / Honesty

- 官方页上看不到的数字写成 `-`
- 每个价格格带 `source_url` 与 `as_of`
- OpenAI ChatGPT/Codex 是会员行，不与 OpenAI API 预付合并
- 汇率快照：`config.yml` 里 `usd_to_cny_rate: 6.8`，带日期，不是牌价

## 许可 / License

MIT. See `LICENSE`.
