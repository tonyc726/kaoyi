# 考异 / kaoyi — living product plan

一事多源并列，写明取舍。

Public site: <https://tonyc726.github.io/kaoyi/>  
Project Pages only. No custom domain. No `CNAME`. Every asset and internal link uses base `/kaoyi/`.

## What it is

A static comparison site for AI Coding / Token Plans.

Official list prices, community events, and scores are **three separate visual layers**. Catalog prices are never rewritten by promos or scores. The composite score is allowed and should be prominent so a buyer can grasp it in one glance. It is not a black-box star that invents missing axes.

Not a clone of `wmpeng/codingplan`. No dreamfree affiliate shortlinks. No finished-account sales.

## Phase 1 (this scaffold)

- Official buy buttons only. No `/go` affiliate redirects. No `affiliates.yml` in git.
- Missing official numbers stay `-`. Every price cell has `source_url` + `as_of`.
- Missing official quota numbers stay out of unit-cost ranking. Never invent a 3 to fill a radar axis.
- OpenAI ChatGPT/Codex is a **membership row**, not merged with OpenAI API prepaid.
- Homepage and vendor pages list **official SKUs** one-to-one (e.g. Claude Max 5x / Max 20x). Never compress platforms into 入门 / 主力 / 高用量 buckets.
- Composite and unit-cost ranking live on `/value/` and on vendor pages next to the radar. The official price table is not sorted by score.

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
2. 性价比 / 综合 (`/value/`)
3. 按量 / 聚合
4. 事件 (empty-capable; examples must be marked)
5. 平台页 for each vendor
6. 关于 (method, units isolation, composite + unit-cost, Phase 1 no-affiliate disclosure)

## Evaluation radar + composite

8 axes, integers 1–5. Missing axes stay empty. Do not fill with 3.

可获得性, 价格结构, 用量经济, 能力覆盖, 稳定性, 支付与区域, 计费透明度, 切换成本。

Composite = arithmetic mean of scored axes only, after the same invert used for radar area (switching_cost is buyer-facing in storage; invert so higher = better for the buyer). Display `3.8 / 5` plus `已评 N/8`. Fewer than 3 scored axes → `暂无综合分`.

Derived axes (availability, price_structure, usage_economy, stability, payment_region, billing_transparency) refresh on every fetch from official snapshots and ingested status posts. Handwritten overlay in `reviews.yml` fills capability and switching_cost only. Do not invent those.

Unit cost is a separate league table: monthly list CNY / official numeric quota, same unit+window only. USD uses `usd_to_cny_rate` and is labeled 编辑换算. MiniMax「约 N Agent」and Claude 5x/20x multipliers are not quotas.

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
- Footer: 最终以官方为准. Prices and scores are snapshots about every 3 hours, not live quotes.

## Repo layout

`vendors.yml`, `reviews.yml`, `config.yml` (`usdToCnyRate` 6.8 + date, `site_base` `/kaoyi/`)  
`data/snapshots/`, `data/events/`, `data/official-posts/`, `data/scores.json`  
Official 动态: vendor-domain blogs/changelogs plus verified GitHub Releases, public status pages, and official forum announcement categories. 90-day window. Not catalog prices.  
`adapters/` (one file per vendor)  
`site/` templates + css  
`scripts/fetch.py` `scripts/build.py`  
`.github/workflows/pages.yml` — push `main` + every 3 hours (`0 */3 * * *` UTC, Asia/Shanghai 02/05/08/11/14/17/20/23) + `workflow_dispatch`; same job builds/deploys after fetch  
`data/fetch-status.json` — today's adapter fetch/parse failures (not snapshot `parse_ok`)

## GitHub Pages

Deploy from Actions. The scheduled fetch writes snapshots/events/scores then builds `dist/` in the same job (`GITHUB_TOKEN` data commits do not retrigger workflows). Repo owner must enable Pages once if needed:

Settings → Pages → Source: **GitHub Actions**.

## Data honesty

Hand-fill official price fields only after fetching the official page and seeing the number. Otherwise `-`. Never invent Claude / Cursor / OpenAI dollar amounts from memory. Never copy models.dev / pi.dev / third-party media quotes as list prices. Catalog prices only from official pages already used by adapters.
