# 考异 / kaoyi — living product plan

一事多源并列，写明取舍。

Public site: <https://tonyc726.github.io/kaoyi/>  
Project Pages only. No custom domain. No `CNAME`. Every asset and internal link uses base `/kaoyi/`.

## What it is

A static comparison site for AI Coding / Token Plans.

Official list prices, community events, and editorial dimensions are **three separate layers**. They are never merged into one star rating. Tables are the main UI. Radar is a build-time wireframe SVG.

Not a clone of `wmpeng/codingplan`. No dreamfree affiliate shortlinks. No finished-account sales.

## Phase 1 (this scaffold)

- Official buy buttons only. No `/go` affiliate redirects. No `affiliates.yml` in git.
- Missing official numbers stay `-`. Every price cell has `source_url` + `as_of`.
- Reviews may be `未评`. Prefer placeholders over invented 1–5 scores.
- OpenAI ChatGPT/Codex is a **membership row**, not merged with OpenAI API prepaid.
- Homepage and vendor pages list **official SKUs** one-to-one (e.g. Claude Max 5x / Max 20x). Never compress platforms into 入门 / 主力 / 高用量 buckets.

## Cold-start vendors (10)

套餐:

- 智谱AI — https://www.bigmodel.cn/glm-coding
- MiniMax — https://platform.minimaxi.com/docs/guides/pricing-token-plan
- 字节·方舟 Coding Plan — https://www.volcengine.com/activity/codingplan
- 方舟 Agent Plan — https://www.volcengine.com/activity/agentplan
- 阿里·百炼 — https://help.aliyun.com/zh/model-studio/coding-plan
- Cursor — https://cursor.com/pricing
- Claude — https://claude.com/pricing
- SuperGrok — https://x.ai/pricing
- OpenAI ChatGPT/Codex — https://chatgpt.com/pricing/

按量:

- OpenRouter — https://openrouter.ai/pricing

## Pages

1. 套餐对照 (default)
2. 按量 / 聚合
3. 事件 (empty-capable; examples must be marked)
4. 平台页 for each vendor
5. 关于 (method, units isolation, no-overall-star, Phase 1 no-affiliate disclosure)

## Evaluation radar

8 axes, integers 1–5, no overall star, do not sort by radar area:

可获得性, 价格结构, 用量经济, 能力覆盖, 稳定性, 支付与区域, 计费透明度, 切换成本。

外圈表示对用户更有利。切换成本在绘图时取反，外圈仍表示对用户更有利。

## Tech (locked)

- Python 3.12 + uv
- httpx + selectolax + pydantic (adapters may stub; stubs must not invent numbers)
- Jinja2 static HTML
- Radar: build-time SVG
- pytest + ruff
- GitHub Actions → GitHub Pages (`upload-pages-artifact` + `deploy-pages`)
- No React, Astro, Next, database, SSR, Playwright login scraping

## UI (locked, x.ai-inspired, no trademarks)

- Dark canvas ~`#1f2228`, white type, almost no second brand color
- Geist Mono (or `ui-monospace`) for display/labels; Inter-like grotesque + Chinese gothic (no Song)
- Hairline white outline pills; at most one solid white CTA
- No phosphor-green terminal theme, no paper/vermilion scholarly theme, no purple AI gradients, no glassmorphism
- Status literals: `OPEN` / `LIMITED` / `SOLD OUT` / `PAUSED`
- Source as mono labels: `SRC OFFICIAL · AS OF date`
- Footer: 最终以官方为准. Prices are snapshots, not live.

## Repo layout

`vendors.yml`, `reviews.yml`, `config.yml` (`usdToCnyRate` 6.8 + date, `site_base` `/kaoyi/`)  
`data/snapshots/`, `data/events/`, `data/official-posts/`  
`adapters/` (one file per vendor)  
`site/` templates + css  
`scripts/fetch.py` `scripts/build.py`  
`.github/workflows/pages.yml` — push `main` + daily 08:00 CST fetch (`0 0 * * *` UTC) + `workflow_dispatch`; same job builds/deploys after fetch  
`data/fetch-status.json` — today's adapter fetch/parse failures (not snapshot `parse_ok`)

## GitHub Pages

Deploy from Actions. The scheduled fetch writes snapshots/events then builds `dist/` in the same job (`GITHUB_TOKEN` data commits do not retrigger workflows). Repo owner must enable Pages once if needed:

Settings → Pages → Source: **GitHub Actions**.

## Data honesty

Hand-fill official price fields only after fetching the official page and seeing the number. Otherwise `-`. Never invent Claude / Cursor / OpenAI dollar amounts from memory.
