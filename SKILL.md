---
name: canvas-agent-skill
description: Operate the Huabu/CNVP canvas agent APIs from Codex or another external agent. Use this skill whenever the user wants to create or select a Huabu workspace project, create or reuse a project-scoped canvas conversation, run the canvas intelligent agent, generate images or videos on a canvas, execute workflow templates through the canvas agent, stream canvas run events, send tool-result feedback after host canvas execution fails, inspect saved canvas-agent results, or package these APIs for external automation. This skill is especially relevant for prompts mentioning canvas-runs, canvas-conversations, /api/agent/canvas-chat, /api/workspace-projects, project_id, canvas_context, agent_skills, generated_image_result, generated_video_result, tool_result_feedback, or workflow template execution.
---

# Canvas Agent Skill

## Overview

Use the Huabu canvas agent by preparing a workspace project, creating or reusing a project-scoped conversation, passing the project ID in `canvas_context`, creating an agent run, and streaming server-sent events until completion. Prefer the bundled CLI for repeatable calls and load reference files only when you need exact payloads or event semantics.

## Quick Start

Use `scripts/canvas_agent.py` for normal API work:

```bash
cp canvas-agent-skill/.env.example canvas-agent-skill/scripts/.env
# Edit canvas-agent-skill/scripts/.env and set YUNJIAN_SYSTEM_TOKEN to the user's system access token.

python canvas-agent-skill/scripts/canvas_agent.py projects list
python canvas-agent-skill/scripts/canvas_agent.py projects ensure --name "未命名项目"
python canvas-agent-skill/scripts/canvas_agent.py conversations create --project-id "<uuid>" --title "画布 Agent"
python canvas-agent-skill/scripts/canvas_agent.py run --project-id "<uuid>" --prompt "生成一张赛博城市海报"
python canvas-agent-skill/scripts/canvas_agent.py events --run-id "<uuid>" --project-id "<uuid>"
```

The default API origin is `http://yunjian.ai` and `site-id` defaults to `10000`.
If the user provides a system access token, write it to `canvas-agent-skill/scripts/.env` as `YUNJIAN_SYSTEM_TOKEN=<token>` before running the CLI. Create the `.env` file from `.env.example` when it does not exist.
Never store real system access tokens in committed skill files, references, examples, or generated zip packages. Runtime `.env` is local-only and must not be packaged or committed.
Do not package or commit `canvas-agent-skill/scripts/.env`. Only `.env.example` should be distributed. The CLI automatically loads `.env` from the current directory, the script directory, the skill directory, or the parent directory. Use `--env-file <path>` when the credentials live elsewhere.

## Workflow

1. Resolve configuration.
   Load `.env` first, then use `YUNJIAN_SYSTEM_TOKEN`. The API origin defaults to `http://yunjian.ai` and `site-id` defaults to `10000`.

2. Ensure a workspace project exists.
   If the user gave `project_id`, verify it with `GET /api/workspace-projects/{project_id}`. If they did not, list recent projects and either choose the newest reasonable project or create a new one when the user asked for a new canvas. For project details, read `references/projects.md`.

3. Create or reuse a canvas conversation.
   Use a project-scoped conversation for follow-up turns. If the user supplied `conversation_id`, verify it with the same project id. Otherwise create one with `POST /api/agent/canvas-conversations`. For exact endpoints, read `references/api.md`.

4. Build `canvas_context`.
   Always include `projectId` for project-backed runs. Include current nodes, edges, selected node IDs, active node ID, reference media, workflow template summaries, or skill preset data only when available and relevant. For field guidance, read `references/canvas-context.md`.

5. Create the agent run.
   Prefer `POST /api/agent/canvas-runs` for durable automation because the backend queues a run, executes media/workflow operations, writes project snapshots, and exposes replayable events. Use `POST /api/agent/canvas-chat` only for direct browser-style interactive streaming. For exact endpoints, read `references/api.md`.

6. Stream events.
   Subscribe to `/api/agent/canvas-runs/{run_id}/events`, parse SSE blocks, and continue until `done`. Surface generated image/video URLs, workflow results, injected `agent_skills`, questions, and errors. For event meanings, read `references/events.md`.

7. Return a concise result.
   Include the project ID, run ID, final status, generated media URLs, workflow run IDs if any, and the frontend URL or API URL the user can open if known.

## Choosing Endpoints

Use `canvas-runs` when the user wants a job that can run to completion outside the browser:

- Generate image nodes.
- Generate video nodes.
- Execute workflow templates.
- Persist output into a workspace project snapshot.
- Recover or replay events after interruption.

Use `canvas-chat` when the user specifically needs immediate streaming chat behavior that a browser frontend will execute locally, such as UI-only node moves or real-time canvas operation handling.

Use `workspace-projects` before either endpoint when project context matters. Project context usually matters for canvas work because it scopes conversation history, lets the backend save snapshots, and allows the frontend to reopen results.

## Media Discipline

Keep media fields typed. Images go only to `image_urls`/`image_url`; videos go only to `video_urls`/`video_url`. Do not put `.jpg`, `.jpeg`, `.png`, `.webp`, or `.gif` links into video fields, and do not put `.mp4`, `.mov`, `.webm`, `.m3u8`, or `.avi` links into image fields. The backend tries to normalize URLs from prompts, but explicit typed fields are more reliable and prevent downstream model errors.

## Tool Feedback

If the host canvas fails to execute a `canvas_operation`, send `tool_result_feedback` to `/api/agent/canvas-chat` with the same `conversation_id` and `canvas_context.projectId`. This lets the Canvas Agent explain the real failure and propose the next step instead of inventing a reason.

```bash
python canvas-agent-skill/scripts/canvas_agent.py feedback \
  --conversation-id "<uuid>" \
  --project-id "<uuid>" \
  --event-type generation_failed \
  --summary "视频节点执行失败" \
  --error "上游节点没有传递图片"
```

## Common Tasks

For a new canvas generation:

```bash
PROJECT_ID=$(python canvas-agent-skill/scripts/canvas_agent.py projects ensure --name "Agent Canvas" --json | jq -r '.id')
python canvas-agent-skill/scripts/canvas_agent.py run --project-id "$PROJECT_ID" --prompt "生成一张电影感产品主视觉" --watch
```

For image-to-video:

```bash
python canvas-agent-skill/scripts/canvas_agent.py run \
  --project-id "<uuid>" \
  --prompt "让这张图里的人物自然走动，镜头缓慢推进" \
  --image-url "https://example.com/ref.png" \
  --watch
```

For a workflow template:

```bash
python canvas-agent-skill/scripts/canvas_agent.py run \
  --project-id "<uuid>" \
  --prompt "按我 @ 的模板执行，并使用这张产品图作为根输入" \
  --image-url "https://example.com/product.png" \
  --canvas-context-json '{"workflow_templates":[...]}'
```

## Resources

- `scripts/canvas_agent.py`: deterministic CLI for project listing/creation, run creation, SSE event streaming, and project fetches.
- `references/api.md`: exact API endpoints, conversation APIs, tool feedback payloads, and auth headers.
- `references/projects.md`: project preflight and empty canvas data.
- `references/canvas-context.md`: `canvas_context` structure and when to include optional fields.
- `references/events.md`: SSE event names and result extraction.
