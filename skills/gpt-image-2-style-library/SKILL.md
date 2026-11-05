---
name: gpt-image-2-style-library
description: "Choose GPT-Image2 / gpt-image-2 visual styles and industrial prompt templates from the awesome-gpt-image-2 style library. Use when an agent needs to create, rewrite, classify, or improve image-generation prompts with repository-backed templates, categories, style tags, scene tags, pitfalls, and example cases."
---

> ✅ **本机状态注记（2026-09-18 复核，实测）**：与上游 freestylefly/awesome-gpt-image-2@0dc09c4（2026-09-11，v1.0.4）逐文件比对——package.json / agents/openai.yaml / references/style-library.md / bin/install.mjs 完全一致；SKILL.md 仅两处本机定制（模板择优规则、出图交付规则，属有意改动，保留）。Maintenance 节的 `npm run generate:style-skill` / `npm run install:skill` 与 `data/style-library.json` 属**上游仓库根目录**的脚本与数据，独立安装的 skill 包本就不含——非漂移、无需重装。日常按 `references/style-library.md` 选模板即可。

# GPT-Image2 Style Library

Use this skill to turn a user's image-generation intent into a production-ready GPT-Image2 prompt using the awesome-gpt-image-2 style library.

## Example Output

![City life system map example](assets/city-life-system-map.png)

Example request: `用 gpt-image-2-style-library 技能生成城市生命系统图谱`

## Reference

- Read `references/style-library.md` before choosing a template or style.
- The reference is generated from `data/style-library.json` in the repository.
- Prefer the reference over memory when template names, categories, covers, or style tags matter.

## Workflow

1. Detect the user's language and answer in that language.
2. Identify the user's target output: product, poster, UI, infographic, brand, photo, illustration, character, scene, history, document, or special task.
3. Match the request in this order: template category, visual style tag, scene tag, then nearest example cases.
4. If one template is clearly strongest, use it directly. If several are plausible, use the strongest fit when the user asked for an image and the choice is reversible; present 2-3 options only when the user asked to compare or the choice changes a material brand or deliverable constraint.
5. Build the final prompt with these blocks:
   - subject and task
   - composition and layout
   - visual style and materials
   - text and label requirements
   - aspect ratio and output format
   - constraints and negative details
6. Include the selected template name and any useful example case IDs.

## Output Defaults

- When the user asks for an image, continue into the image generation workflow and deliver the image; use a copyable prompt as the final output only when the user asks for a prompt.
- Provide a copyable prompt first.
- Keep constraints concrete: exact text, aspect ratio, readable labels, layout hierarchy, and avoided artifacts.
- For Chinese requests, write the final prompt in Chinese unless the user asks for English.
- For English requests, write the final prompt in English unless the user asks for Chinese.
- When the user asks for multiple concepts, reuse one template and vary subject, composition, palette, and scene.

## Maintenance

When the source repository changes, run:

```bash
npm run generate:style-skill
```

To install the skill into the local Codex skill folder, run:

```bash
npm run install:skill
```
