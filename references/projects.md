# Workspace Project Preflight

Canvas agent work should normally be project-backed. A project gives the backend somewhere to persist generated nodes and lets future turns refer to the same canvas.

## Decision Flow

1. If the user provides `project_id`, verify it with `GET /api/workspace-projects/{project_id}`.
2. If the user asks for a new canvas or no project is available, create a project.
3. If the user says to use an existing canvas but gives no ID, list recent projects and present a concise choice, unless one project is clearly the active/recent target.
4. Create or reuse a canvas conversation scoped to that project.
5. Always pass the chosen ID as `canvas_context.projectId` when creating a run.

## Empty Canvas Data

Use the same shape as the frontend when creating a blank project:

```json
{
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
```

The backend has fallbacks for missing snapshot fields, but using the frontend shape reduces surprises and makes project snapshots open cleanly in the UI.

## Result Location

Backend durable runs save generated node data to the project's latest snapshot when `run.project_id` is present. If the run was created without `canvas_context.projectId`, generation may still happen, but there may be no project snapshot for the user to open.

## Conversation Location

Canvas Agent conversations are also project-scoped. Use `POST /api/agent/canvas-conversations` with `project_id` before creating a durable run when the caller needs stable follow-up turns, tool feedback, or history lookup. Reuse `conversation_id` for follow-up runs in the same project.
