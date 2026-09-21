# Canonical Markdown Template

Hard report-body limits: daily ≤6500 characters, weekly ≤10000, excluding URL targets only (not headings, source labels or prose). No filling to the limit. A single concise coverage caveat without raw counts is allowed when missing/failed sources materially limit coverage; detailed failures remain in the operational log. These exceptions/limits apply to the shared canonical content in every format.

Follow `../digest-prompt.md` as the authoritative editorial policy. Select once; all formats use the same items, judgments and order. These are structural placeholders, not factual examples or mandatory fill-in quotas. Translate headings to `<LANGUAGE>`; Chinese means Simplified Chinese.

## Daily — original sections, at most 30 unique items overall

```markdown
# 科技日报 — {{DATE}}

> {{2–4 句概览：概括主要变化与不确定性，不引入新事件}}

## 🧠 LLM / 大模型
• **{{标题}}** — {{发生了什么；关键技术细节或证据；影响或局限，通常 2–3 句}}。[来源](<{{URL}}>)

## 🤖 AI Agent
• **{{标题}}** — {{变化、证据与影响}}。[来源](<{{URL}}>)

## 💰 Crypto / 加密技术
• **{{标题}}** — {{协议、技术或基础设施进展；避免交易噪音}}。[来源](<{{URL}}>)

## 🚀 前沿科技
• **{{标题}}** — {{变化、证据与影响}}。[来源](<{{URL}}>)

## 📢 KOL 动态
• **{{作者}}** — {{原创观点、背景、意义；明确这是观点而非已证实事实}}。[来源](<{{URL}}>)

## 📦 GitHub 发布精选
• **{{owner/repo vX.Y.Z}}** — {{已核实的关键变化；谁应行动}}。[来源](<{{RELEASE_URL}}>)

## 🐙 GitHub 项目发现
• **{{项目}}** — {{用途、当前值得尝试的理由与局限}}。[来源](<{{URL}}>)

## 📝 博客精选
• **{{文章标题与作者}}** — {{核心观点、具体洞见、适合谁读，通常 2–3 句}}。[来源](<{{URL}}>)
```

Use configured topic labels/order if customized. Aim for 3–5 qualified news items per topic; KOL, release, discovery and blog sections each allow up to 3 items, within the global cap. Keep headings even if no item qualifies: use a brief non-bullet coverage note, never filler. A collection failure is not evidence of no news. One event has one home; keep GitHub releases short rather than restoring changelog inventories. Do not target a single Discord message.

## Weekly — at most 35 unique items overall

```markdown
# 科技周报 — {{DATE}}

> {{2–4 句本周概览：主要变化与仍存的不确定性，不引入新事件}}

## 🧠 LLM / 大模型
• **{{综合判断}}** — {{用 2–4 句连接本周进展、具体证据与影响/局限，非标题拼接}}。[来源](<{{URL}}>)

## 🤖 AI Agent
• **{{综合判断}}** — {{本周进展、证据与影响}}。[来源](<{{URL}}>)

## 💰 Crypto / 加密技术
• **{{综合判断}}** — {{协议、技术或基础设施进展及其意义}}。[来源](<{{URL}}>)

## 🚀 前沿科技
{{若无合格内容，用非列表句如：本期暂无值得单列的更新；若采集失败则说明覆盖受限。}}

## 📦 关键发布
• **{{owner/repo vX.Y.Z}}** — {{关键变化；适用对象与行动}}。[来源](<{{RELEASE_URL}}>)

## 🐙 项目发现
• **{{项目}}** — {{用途、当前尝试理由与局限}}。[来源](<{{URL}}>)

## 📝 观点与深度阅读
• **{{作者观点、论文、文档、复盘或文章}}** — {{核心论点、具体洞见与适合谁读；区分观点与事实}}。[来源](<{{URL}}>)

## 下周关注
• **{{待发布、待修复或未决问题}}** — {{关注什么以及为什么；日期/状态等事实需来源}}。[来源](<{{URL}}>)
```

Use the effective configured topic labels/order, not a hard-coded topic list. Aim for 2–4 substantial syntheses per topic, advisory only, each 2–4 concise sentences; no global three-theme constraint. Releases ≤5 repositories, Chinese explanations ≤80 characters; projects ≤3; viewpoints/deep reading ≤4 combined; optional next-week watch ≤3. Retain empty required topic/release/project/reading headings with honest non-bullet coverage notes, not filler. Caps are not quotas. Optional security/risk: urgent `## 🛡️ 安全警报` immediately after overview, otherwise consequential nonurgent risks after topics; omit when empty and never duplicate topics/releases. Omit next-week watch when empty; don't force experiments. Only clearly proposed/not-performed experiments may omit citations (question + minimal test + metric); factual watch claims require sources. Count every unique evidence event inside syntheses and standalone watch proposals toward 35. Weekly may synthesize daily coverage; daily repeats need an explicit incremental development. Do not append another trend summary from legacy cron parameters.

Weekly production validation adds repeated `--topic-heading 'EXACT LOCALIZED HEADING'` arguments in configured order, as specified in `../digest-prompt.md`. Required non-topic headings, overview, security placement, actual event counts and evidence/coverage honesty still require editorial review.

## Shared Checks

- All limits are caps, not quotas. Deduplicate canonical URLs and events across the entire report; one event has one home. Advice integrated in that home is preferable to a repeated action item.
- Titles bold, summaries plain and concise, links inline. Use `•` bullets compatible with existing renderers. Daily retains KOL viewpoints. No tables, raw URL lines, scores, social metrics or operational/generator footers.
- Releases: one repository per bullet, exact version and official release link, verified impact; Chinese explanation ≤80 characters excluding name/version/URL. Release caps apply anywhere in the report.
- Discovery is not proven popularity/trending. No lifetime-derived star growth; do not repeatedly feature mature repos without meaningful changes.
- Validate this exact canonical file with `scripts/validate-digest.py --input FILE --mode daily` or `--mode weekly`, fixing every error before delivery. Preserve this selection for Discord, email and PDF. Operational statistics belong only in the final log.
