---
name: zhaopin-resume-processing
description: "Use when carrying out recruitment work in Zhaopin (智联招聘), especially when real company or project facts, job-posting content, resume processing, candidate recommendations, greetings, or unread-chat handling must stay consistent."
---

# 智联招聘简历处理

This is a reusable Zhaopin recruitment workflow with resume processing at its center. The job, company, project, candidate pool, and communication goal are inputs; never hard-code one position, threshold, candidate, message, name, URL parameter, or daily quota into the workflow.

## Operating sequence

1. Confirm the operating brief: real company/project facts, target role or project, headcount, duties, pay, location, schedule, benefits, candidate pool, desired priority, and whether the user wants a draft, review, platform action, or all three. Missing facts stay “待确认”; never invent them.
2. Draft the recruitment brief from those facts. Keep duties, requirements, work conditions, compensation, benefits, and contact instructions internally consistent. Present the final draft for confirmation before public publishing; do not turn a recorded example into fixed copy.
3. In Zhaopin, reuse the user's existing logged-in tab. If the platform offers different publishing modes such as a project/priority posting, choose only the mode the user requested, complete the fields from the approved brief, and verify the published title, status, location, pay, and headcount. Publishing is an external action and requires confirmation immediately before it.
4. For the approved job, open 推荐人才 or 人才管理. Use transparent, job-related platform filters only as candidate generation. Record the active filters and result count; a closed filter menu is not proof that the filter applied.
5. Process resumes as the core task. Read the candidate card, then open the full profile or attached resume when necessary. Normalize education, chronology, role scope, responsibilities, skills, certifications, location/availability, compensation expectations, and evidence quality. Preserve “未提及/待确认”; never fill gaps with guesses.
6. Build a requirement brief from the job description: hard gates, strong evidence, preferences, and unknowns. Compare each resume with that brief and return 匹配、待复核、不匹配, with concise evidence and confidence. Rank by explainable job-related evidence, not an opaque score. The user may set priorities such as “项目经验优先” or “尽快到岗优先”; treat them as task inputs. Recommendations are advisory; do not make the final hiring decision on the user's behalf.
7. Do not use age, gender, appearance, marital status, health, or other sensitive/protected traits as an automated judgment. Treat vague appearance language as non-decisive unless the user explicitly asks for a lawful, job-relevant review.
8. Before a greeting, show the proposed candidate batch, the reason each person matches, the job-specific message or selected template, and the expected quota use. After exact-scope confirmation, send only to that batch, track the visible remaining quota, and stop when the quota is exhausted or a risk warning appears. Never bypass platform limits. A greeting counts as an external message.
9. For follow-up, open 聊天, select 未读, and read the conversation together with the relevant job and resume preview. Draft a response that answers the candidate's actual question and stays within the approved job facts. Separate the suggested next action (补充信息、继续沟通、约面、暂缓、不匹配) from the message draft. Send only after exact-scope confirmation unless already explicitly authorized for that batch and message purpose.
10. After every publish, greeting, status change, or reply, verify the visible toast, count, label, published content, or conversation state. A click, network success, or event record alone is not proof. Stop and report if Zhaopin shows an account-risk warning, CAPTCHA, abnormal-access notice, or ambiguous delivery state.

## Reusable inputs and outputs

Inputs may include: company/project facts, target job or project, approved or draft job brief, resume or candidate pool, user priorities and tradeoffs, target candidate status, desired output format, greeting/reply purpose, and approved message text.

Return:

- the recruitment brief and publishing result, when publishing was requested;
- a normalized resume summary or comparison table;
- the job context and requirement brief when one was used;
- candidates grouped as 匹配、待复核、不匹配, with concise evidence and uncertainty;
- proposed greeting batches, message drafts, status changes, and next actions separately from completed actions;
- visible verification for any completed action and any blocker.

## UI handling

Use semantic visible labels such as 职位管理, 发布职位, 项目单发布, 推荐人才, 人才管理, 筛选, 学历, 经验, 查看附件简历, 选择招呼语, 聊天, 未读, and 继续沟通. Re-observe the current page after navigation, filtering, scrolling, or opening a profile; do not replay coordinate sequences from a recording. Keep the in-app browser tab available when the user is collaborating live.

## Common failure boundaries

- A job summary and description disagree: surface the conflict; do not silently choose a threshold.
- A candidate card looks promising but the resume lacks proof: classify as 待复核, not 匹配.
- A resume has missing or ambiguous dates, education, or duties: preserve the unknown and identify the exact item to confirm.
- A filter returns zero or an unexpected count: inspect the active filter chips and clear/reapply deliberately.
- A greeting template contains stale pay, schedule, location, or project facts: compare it with the approved brief before using it.
- A candidate reply changes the context: reread the job and resume preview before drafting the next message.
- A message appears sent but delivery is not visibly confirmed: report unconfirmed and do not resend.
