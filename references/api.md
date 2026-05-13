# API Reference

Use these endpoints against the fixed production origin `https://ai.cnvp.cn`.

## Auth

Send these on JSON requests:

```http
Content-Type: application/json
token: <access token>
site-id: 10000
```

For `EventSource`/SSE endpoints, the frontend implementation also accepts `token` and fixed `site-id` query parameters:

```text
?site-id=10000&token=...&project_id=<uuid>
```

Treat tokens as secrets. Do not write real tokens into skill resources, logs intended for sharing, or committed files.

## Canvas Conversations

List project conversations:

```http
GET /api/agent/canvas-conversations?project_id=<project uuid>&limit=20&offset=0
```

Create a project-scoped conversation:

```http
POST /api/agent/canvas-conversations
```

Body:

```json
{
  "title": "画布 Agent",
  "project_id": "<project uuid>"
}
```

Get conversation detail:

```http
GET /api/agent/canvas-conversations/{conversation_id}?project_id=<project uuid>
```

Append a message when an integration needs to persist host-side notes or results:

```http
POST /api/agent/canvas-conversations/{conversation_id}/messages?project_id=<project uuid>
```

Body:

```json
{
  "role": "assistant",
  "content": "Host canvas applied the operation.",
  "event_type": "tool_note",
  "attachments": [],
  "metadata": {}
}
```

## Workspace Projects

List recent projects:

```http
GET /api/workspace-projects?view=recent&limit=20&offset=0&include_description=true
```

Get one project:

```http
GET /api/workspace-projects/{project_id}
```

Create a project:

```http
POST /api/workspace-projects
```

Body:

```json
{
  "name": "未命名项目",
  "canvas_data": {
    "version": 2,
    "nodes": [],
    "connections": [],
    "groups": [],
    "nodeSizes": {},
    "nodeInputCache": {},
    "nodeTextOutputCache": {},
    "nodeCommentCache": {},
    "nodeImageInputCache": {},
    "nodeVideoInputCache": {},
    "nodeAudioInputCache": {},
    "nodeSelectedGeneratedImageUrls": {},
    "nodeSelectedGeneratedVideoUrls": {},
    "nodeAssetSourceCache": {},
    "nodeGeneration": {},
    "nodeVideoStoryState": {},
    "nodeStoryboardCache": {},
    "selectedNodeIds": [],
    "selectedGroupId": null,
    "activeNodeId": null,
    "zoom": 1,
    "canvasGridOffset": { "x": 0, "y": 0 }
  }
}
```

Save a snapshot:

```http
PUT /api/workspace-projects/{project_id}/snapshot
```

Body:

```json
{
  "snapshot_source": "auto",
  "editor_version": "external:canvas-agent-skill",
  "canvas_data": {}
}
```

## Durable Canvas Agent Runs

Create a run:

```http
POST /api/agent/canvas-runs
```

Body:

```json
{
  "prompt": "生成一张电影感产品主视觉",
  "conversation_id": null,
  "canvas_context": {
    "projectId": "<workspace project uuid>"
  },
  "image_urls": [],
  "video_urls": []
}
```

Notes:

- `project_id` is not a top-level body field. The backend extracts it from `canvas_context.projectId` or `canvas_context.project_id`.
- `conversation_id` is optional, but external agents should create or reuse one for stable project-scoped follow-up turns.
- `image_urls` and `video_urls` are explicit reference media for this turn. Keep images and videos in separate fields.
- Use `question_response` instead of `prompt` only when continuing after an `ask_user_question` event.

Response:

```json
{
  "run": {
    "id": "<run uuid>",
    "conversation_id": "<conversation uuid>",
    "project_id": "<project uuid>",
    "status": "queued",
    "prompt": "...",
    "result": {},
    "error_message": null,
    "created_at": "...",
    "updated_at": "..."
  },
  "conversation_id": "<conversation uuid>",
  "title": "..."
}
```

Get run status:

```http
GET /api/agent/canvas-runs/{run_id}?project_id=<project uuid>
```

Stream run events:

```http
GET /api/agent/canvas-runs/{run_id}/events?site-id=10000&token=<token>&project_id=<project uuid>
```

Optional replay cursor:

```text
last_event_id=<numeric event id>
```

## Direct Canvas Chat

Use this when a browser-like client will execute streamed `canvas_operation` events locally:

```http
POST /api/agent/canvas-chat
```

Body resembles:

```json
{
  "prompt": "把当前选中图片右边再生成一个视频节点",
  "stream": true,
  "conversation_id": "<conversation uuid>",
  "canvas_context": {
    "projectId": "<workspace project uuid>",
    "nodes": [],
    "edges": []
  },
  "image_url": ["https://example.com/ref.png"],
  "video_url": []
}
```

The response is SSE over the HTTP response body.

## Tool Result Feedback

Use this when the host canvas or external integration fails to execute a returned `canvas_operation`.

```http
POST /api/agent/canvas-chat
```

Body:

```json
{
  "conversation_id": "<conversation uuid>",
  "canvas_context": {
    "projectId": "<workspace project uuid>"
  },
  "tool_result_feedback": {
    "event_type": "generation_failed",
    "summary": "Workflow video node failed",
    "operation": {
      "action": "execute_workflow_template",
      "template_id": "..."
    },
    "error": "上游节点没有传递图片",
    "results": []
  }
}
```

The Canvas Agent persists the feedback as tool context, streams a user-facing explanation, and may propose a retry or missing-input fix.

## Media Field Rules

- `canvas-runs`: use `image_urls` and `video_urls`.
- `canvas-chat`: use `image_url` and `video_url`.
- Image-like extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.tiff`, `.avif`.
- Video-like extensions: `.mp4`, `.mov`, `.webm`, `.m3u8`, `.avi`, `.mkv`, `.mpeg`, `.mpg`.
- Do not pass image-like URLs in video fields. This causes downstream video providers to reject `video_url` or `video_urls`.
- Do not pass video-like URLs in image fields unless the user explicitly wants a video frame extraction workflow and the host has a separate extractor.
