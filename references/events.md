# Canvas Run Events

`/api/agent/canvas-runs/{run_id}/events` returns server-sent events. Parse blocks separated by blank lines. Each block may include `id:`, `event:`, and one or more `data:` lines.

## Event Names

- `conversation`: contains `conversation_id` and `title`.
- `message`: streamed assistant text.
- `agent_skills`: installed prompt skills that were selected and injected into this agent run.
- `ask_user_question`: structured question set; collect answers and create a follow-up run with `question_response`.
- `canvas_operation`: the model chose a canvas action, such as creating image/video nodes or executing a workflow template.
- `generation_placeholder`: backend created a placeholder message while media generation runs.
- `generated_image_result`: generated image result message.
- `generated_video_result`: generated video result message.
- `error`: terminal or recoverable error text.
- `done`: run is complete; data usually includes `conversation_id` and `status`.
- `keepalive`: heartbeat while waiting.

## Result Metadata Shapes

Skill context events look like:

```json
{
  "items": [
    {
      "id": "skill uuid",
      "name": "Skill name",
      "summary": "Why it was relevant",
      "score": 12
    }
  ]
}
```

These are diagnostic. They do not require host canvas execution.

Generated image results are commonly embedded in message metadata under keys such as:

```json
{
  "agent_generated_images": [
    {
      "nodeId": "image-agent-generate-...",
      "modelId": "gpt-image-2",
      "modelLabel": "云歌 O2",
      "prompt": "...",
      "imageUrls": ["https://..."],
      "status": "succeeded"
    }
  ]
}
```

Generated video results are commonly embedded under:

```json
{
  "agent_generated_videos": [
    {
      "nodeId": "video-agent-generate-...",
      "modelId": "seedance-2-0",
      "modelLabel": "云梦 2.0pro",
      "prompt": "...",
      "videoUrls": ["https://..."],
      "status": "succeeded"
    }
  ]
}
```

Workflow results may appear in run result payloads or tool feedback metadata:

```json
{
  "type": "workflow",
  "status": "succeeded",
  "templateId": "...",
  "templateName": "...",
  "workflowRunId": "...",
  "progress": 100,
  "resultSummary": {},
  "nodeSummaries": []
}
```

## Practical Parsing

Do not assume every event is JSON. `message` and `error` may be plain text. Try JSON parsing and fall back to raw text.

Track the last numeric SSE `id` and pass it as `last_event_id` when reconnecting. A terminal `done` event means the stream can close.

After `done`, fetch `GET /api/agent/canvas-runs/{run_id}` for the canonical run status and result payload.

If a `canvas_operation` fails in the host integration, send `tool_result_feedback` through `/api/agent/canvas-chat` rather than silently retrying with guessed parameters.
