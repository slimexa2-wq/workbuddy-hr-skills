---
name: ai-manga-drama-studio
description: Google 20x Ultra (Flow / Veo 3 / Whisk / Imagen 4 / Gemini 3.1 Pro) + ChatGPT Plus (GPT-4o / o3 / GPT-Image-2 / Sora) 极简一键漫剧全自动生产工作流。支持小说/剧本一键拆解黄金前3秒钩子分镜、StoryDiffusion级角色DNA锁脸卡、双生态提示词、SRT字幕及剪映专业版(draft_content.json)草稿导出。
---

# Google 20x Ultra × ChatGPT Plus 极简漫剧工作流 (`ai-manga-drama-studio`)

## 核心设计原则
- **效率优先，操作简单直观，后台复杂但前端极简，拒绝过度安全与繁琐配置！**
- 1 步输入小说或梗概 $\rightarrow$ 1 键输出完整分镜 JSON、角色一致性 DNA 锁脸卡、ChatGPT Plus (`GPT-Image-2`) 与 Google 20x Ultra (`Flow / Imagen 4 / Veo 3`) 提示词、`.srt` 字幕、交互式分镜看板 HTML、以及可直接导入剪映专业版的 `draft_content.json` 草稿目录。

## 一键使用方法

### 1. 命令行秒级生成全套漫剧工程包
```bash
/Users/wangmini/.local/bin/manga-studio run \
  --title "第一集_魔帝归来" \
  --style xianxia \
  --text "粘贴小说章节或剧本内容"
```
可选风格 (`--style`)：
- `xianxia`：🔥 国风修仙玄幻
- `urban_counterattack`：⚡ 都市战神/逆袭爽剧
- `k_chaebol`：🌸 唯美韩漫财阀/豪门甜虐
- `shonen_battle`：🗡️ 热血日漫少年/高燃战斗
- `chinese_horror`：👁️ 中式规则怪谈/悬疑反转
- `cyberpunk`：🤖 赛博朋克末日/机甲觉醒
- `palace_intrigue`：👑 古风宫斗/重生复仇
- `cg_3d_donghua`：🎬 3D国漫电影级CG

### 2. 启动本地零配置一键 Web 工作台
```bash
/Users/wangmini/.local/bin/manga-studio serve --port 8788
```
浏览器打开 `http://127.0.0.1:8788` 即可一键粘贴生成并复制分镜词。
