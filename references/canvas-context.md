# Canvas Context

`canvas_context` is the bridge between a user request and a specific Huabu canvas. Keep it compact; include facts that help the model choose a tool or resolve references.

## Minimum

```json
{
  "projectId": "<workspace project uuid>"
}
```

This is enough for durable `canvas-runs` to scope conversations and save generated nodes into the project snapshot.

## Useful Optional Fields

```json
{
  "projectId": "<workspace project uuid>",
  "activeNodeId": "image-1",
  "selectedNodeIds": ["image-1"],
  "nodes": [
    {
      "id": "image-1",
      "type": "image",
      "request": {
        "prompt": "original generation prompt"
      },
      "media": {
        "mediaType": "image",
        "mediaUrl": "https://example.com/image.png",
        "previewUrl": "https://example.com/image.png"
      }
    }
  ],
  "edges": [
    {
      "id": "conn-1",
      "sourceId": "image-1",
      "targetId": "video-1"
    }
  ]
}
```

Include node prompts and media URLs only when they are relevant. If the user asks "use this node" or "continue from the previous image", the agent can use these fields to resolve the reference.

## Workflow Templates

When executing workflow templates through the agent, include available template summaries:

```json
{
  "projectId": "<workspace project uuid>",
  "workflow_templates": [
    {
      "template_id": "<template uuid>",
      "template_name": "商品图转短视频",
      "visibility": "private",
      "input_nodes": [
        {
          "id": "image-input-1",
          "type": "image",
          "label": "产品图"
        },
        {
          "id": "text-input-1",
          "type": "text",
          "label": "风格要求"
        }
      ]
    }
  ]
}
```

The agent validates `execute_workflow_template.template_id` against `canvas_context.workflow_templates` when this list is present. Include `input_nodes` so it can construct `input_overrides` from the prompt and reference media.

Input nodes should be graph roots: no incoming edge and at least one outgoing edge. Do not use comment nodes as the source of required workflow parameters.

## Skill Presets

The backend recognizes an optional preset:

```json
{
  "projectId": "<workspace project uuid>",
  "agent_skill_preset": {
    "id": "social-media"
  }
}
```

Known preset IDs in the current backend include:

- `social-carousel`
- `social-media`
- `logo-brand`
- `storyboard`
- `marketing-brochure`
- `product-showcase`

Use presets only when they match the user's chosen scenario. They bias the agent toward generating the right kind of canvas assets.

## Media Hints

When including media in `canvas_context.nodes`, preserve the media type:

- Image node media uses `mediaType: "image"` and image URLs.
- Video node media uses `mediaType: "video"` and video URLs.

Do not move image URLs into video fields to satisfy a downstream video node. Image-to-video models consume image inputs through image fields.

## Real-Time Browser Context

The backend can ask the active frontend for a live canvas snapshot when the browser has registered a project over WebSocket. External CLI use should not depend on this. If no browser is connected, pass the best available snapshot facts in `canvas_context` or rely on the saved project snapshot.
