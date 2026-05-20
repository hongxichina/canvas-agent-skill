#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://yunjian.ai"
DEFAULT_SITE_ID = "10000"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".avif")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".m3u8", ".avi", ".mkv", ".mpeg", ".mpg")
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def load_env_files(explicit_env_file: str | None = None) -> None:
    candidates: list[Path] = []
    if explicit_env_file:
        candidates.append(Path(explicit_env_file).expanduser())
    candidates.extend(
        [
            Path.cwd() / ".env",
            SCRIPT_DIR / ".env",
            SKILL_DIR / ".env",
            SKILL_DIR.parent / ".env",
        ]
    )
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        load_dotenv(resolved)


def empty_canvas_data() -> dict[str, Any]:
    return {
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
        "selectedGroupId": None,
        "activeNodeId": None,
        "zoom": 1,
        "canvasGridOffset": {"x": 0, "y": 0},
    }


@dataclass
class Config:
    base_url: str
    token: str
    site_id: str

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Config":
        load_env_files(args.env_file)
        base_url = (os.environ.get("YUNJIAN_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        token = (
            args.token
            or os.environ.get("YUNJIAN_SYSTEM_TOKEN")
            or os.environ.get("YUNJIAN_TOKEN")
            or ""
        )
        site_id = os.environ.get("YUNJIAN_SITE_ID") or DEFAULT_SITE_ID
        if not token:
            raise SystemExit("Missing system token. Set YUNJIAN_SYSTEM_TOKEN or pass --token.")
        return cls(base_url=base_url, token=token, site_id=site_id)


class ApiError(RuntimeError):
    pass


class HuabuClient:
    def __init__(self, config: Config):
        self.config = config

    def _url(self, path: str, query: dict[str, Any] | None = None) -> str:
        url = f"{self.config.base_url}{path}"
        if query:
            normalized = {
                key: value
                for key, value in query.items()
                if value is not None and str(value) != ""
            }
            if normalized:
                url = f"{url}?{urllib.parse.urlencode(normalized)}"
        return url

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._url(path, query),
            data=data,
            method=method.upper(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.token}",
                "site-id": self.config.site_id,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise ApiError(f"{method} {path} failed: HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"{method} {path} failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def list_projects(self, *, view: str, limit: int, offset: int, include_description: bool) -> dict[str, Any]:
        return self.request(
            "GET",
            "/api/workspace-projects",
            query={
                "view": view,
                "limit": limit,
                "offset": offset,
                "include_description": str(include_description).lower(),
            },
        )

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/workspace-projects/{project_id}")

    def create_project(self, *, name: str, canvas_data: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/workspace-projects",
            body={"name": name, "canvas_data": canvas_data or empty_canvas_data()},
        )

    def list_conversations(
        self,
        *,
        project_id: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        return self.request(
            "GET",
            "/api/agent/canvas-conversations",
            query={"project_id": project_id, "limit": limit, "offset": offset},
        )

    def create_conversation(self, *, project_id: str | None, title: str | None) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/agent/canvas-conversations",
            body={"project_id": project_id, "title": title},
        )

    def get_conversation(self, conversation_id: str, *, project_id: str | None = None) -> dict[str, Any]:
        return self.request(
            "GET",
            f"/api/agent/canvas-conversations/{conversation_id}",
            query={"project_id": project_id},
        )

    def append_conversation_message(
        self,
        conversation_id: str,
        *,
        project_id: str | None,
        role: str,
        content: str,
        event_type: str | None,
        attachments: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/agent/canvas-conversations/{conversation_id}/messages",
            query={"project_id": project_id},
            body={
                "role": role,
                "content": content,
                "event_type": event_type,
                "attachments": attachments,
                "metadata": metadata,
            },
        )

    def create_run(
        self,
        *,
        prompt: str | None,
        project_id: str | None,
        conversation_id: str | None,
        canvas_context: dict[str, Any],
        image_urls: list[str],
        video_urls: list[str],
        question_response: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if project_id:
            canvas_context = {"projectId": project_id, **canvas_context}
        body: dict[str, Any] = {
            "prompt": prompt,
            "conversation_id": conversation_id,
            "canvas_context": canvas_context,
            "image_urls": image_urls,
            "video_urls": video_urls,
        }
        if question_response is not None:
            body["question_response"] = question_response
        return self.request("POST", "/api/agent/canvas-runs", body=body)

    def send_tool_feedback(
        self,
        *,
        conversation_id: str,
        project_id: str | None,
        feedback: dict[str, Any],
        canvas_context: dict[str, Any],
    ) -> Any:
        if project_id:
            canvas_context = {"projectId": project_id, **canvas_context}
        return self.request(
            "POST",
            "/api/agent/canvas-chat",
            body={
                "conversation_id": conversation_id,
                "canvas_context": canvas_context,
                "tool_result_feedback": feedback,
                "stream": True,
            },
            timeout=1800.0,
        )

    def get_run(self, run_id: str, *, project_id: str | None = None) -> dict[str, Any]:
        return self.request(
            "GET",
            f"/api/agent/canvas-runs/{run_id}",
            query={"project_id": project_id},
        )

    def stream_run_events(
        self,
        run_id: str,
        *,
        project_id: str | None = None,
        last_event_id: int | None = None,
        timeout: float = 1800.0,
    ):
        query = {
            "site-id": self.config.site_id,
            "token": self.config.token,
            "project_id": project_id,
            "last_event_id": last_event_id,
        }
        request = urllib.request.Request(
            self._url(f"/api/agent/canvas-runs/{run_id}/events", query),
            method="GET",
            headers={"Accept": "text/event-stream"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                buffer: list[str] = []
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line == "":
                        event = parse_sse_block(buffer)
                        buffer = []
                        if event is not None:
                            yield event
                            if event.get("event") == "done":
                                return
                        continue
                    buffer.append(line)
                event = parse_sse_block(buffer)
                if event is not None:
                    yield event
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise ApiError(f"stream events failed: HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"stream events failed: {exc}") from exc


def parse_sse_block(lines: list[str]) -> dict[str, Any] | None:
    if not lines:
        return None
    event_id: str | None = None
    event_name = "message"
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("event:"):
            event_name = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    data_text = "\n".join(data_lines)
    try:
        data: Any = json.loads(data_text) if data_text else None
    except json.JSONDecodeError:
        data = data_text
    event: dict[str, Any] = {"event": event_name, "data": data}
    if event_id:
        event["id"] = event_id
    return event


def parse_json_value(value: str | None, label: str) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {label} JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{label} must be a JSON object")
    return parsed


def parse_json_file(path: str | None, label: str) -> dict[str, Any] | None:
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return parse_json_value(handle.read(), label)


def media_path_extension(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    path = urllib.parse.unquote(parsed.path).lower()
    for extension in (*IMAGE_EXTENSIONS, *VIDEO_EXTENSIONS):
        if path.endswith(extension):
            return extension
    return ""


def validate_media_urls(*, image_urls: list[str], video_urls: list[str]) -> None:
    image_like_videos = [url for url in video_urls if media_path_extension(url) in IMAGE_EXTENSIONS]
    video_like_images = [url for url in image_urls if media_path_extension(url) in VIDEO_EXTENSIONS]
    if image_like_videos:
        raise SystemExit(
            "Image URL passed as video input. Move these to --image-url: "
            + ", ".join(image_like_videos)
        )
    if video_like_images:
        raise SystemExit(
            "Video URL passed as image input. Move these to --video-url: "
            + ", ".join(video_like_images)
        )


def parse_json_array_file(path: str | None, label: str) -> list[dict[str, Any]]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as handle:
        try:
            parsed = json.loads(handle.read())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid {label} JSON: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise SystemExit(f"{label} must be a JSON array of objects")
    return parsed


@dataclass
class EventSummary:
    status: str = "running"
    messages: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    workflow_run_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    last_event_id: str | None = None

    def update(self, event: dict[str, Any]) -> None:
        if event.get("id"):
            self.last_event_id = str(event["id"])
        name = str(event.get("event") or "")
        data = event.get("data")
        if name == "message" and isinstance(data, str):
            self.messages.append(data)
        elif name == "error":
            self.errors.append(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))
            self.status = "failed"
        elif name == "done":
            if isinstance(data, dict) and isinstance(data.get("status"), str):
                self.status = data["status"]
            elif self.status != "failed":
                self.status = "succeeded"
        self._collect_urls(data)

    def _collect_urls(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"imageUrls", "image_urls"} and isinstance(item, list):
                    self._extend_unique(self.image_urls, item)
                elif key in {"videoUrls", "video_urls"} and isinstance(item, list):
                    self._extend_unique(self.video_urls, item)
                elif key == "workflowRunId" and isinstance(item, str):
                    self._extend_unique(self.workflow_run_ids, [item])
                else:
                    self._collect_urls(item)
        elif isinstance(value, list):
            for item in value:
                self._collect_urls(item)

    @staticmethod
    def _extend_unique(target: list[str], values: list[Any]) -> None:
        for item in values:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if value and value not in target:
                target.append(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": "".join(self.messages).strip(),
            "image_urls": self.image_urls,
            "video_urls": self.video_urls,
            "workflow_run_ids": self.workflow_run_ids,
            "errors": self.errors,
            "last_event_id": self.last_event_id,
        }


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_projects_list(client: HuabuClient, args: argparse.Namespace) -> None:
    result = client.list_projects(
        view=args.view,
        limit=args.limit,
        offset=args.offset,
        include_description=not args.no_description,
    )
    print_json(result if args.json else result.get("items", result))


def command_projects_get(client: HuabuClient, args: argparse.Namespace) -> None:
    print_json(client.get_project(args.project_id))


def command_projects_create(client: HuabuClient, args: argparse.Namespace) -> None:
    canvas_data = parse_json_file(args.canvas_data_file, "canvas data") or empty_canvas_data()
    print_json(client.create_project(name=args.name, canvas_data=canvas_data))


def command_projects_ensure(client: HuabuClient, args: argparse.Namespace) -> None:
    if args.project_id:
        print_json(client.get_project(args.project_id))
        return
    result = client.list_projects(view="recent", limit=1, offset=0, include_description=False)
    items = result.get("items") if isinstance(result, dict) else []
    if args.use_recent and isinstance(items, list) and items:
        print_json(items[0])
        return
    print_json(client.create_project(name=args.name, canvas_data=empty_canvas_data()))


def command_conversations_list(client: HuabuClient, args: argparse.Namespace) -> None:
    result = client.list_conversations(
        project_id=args.project_id,
        limit=args.limit,
        offset=args.offset,
    )
    print_json(result if args.json else result.get("items", result))


def command_conversations_create(client: HuabuClient, args: argparse.Namespace) -> None:
    if args.project_id:
        client.get_project(args.project_id)
    print_json(client.create_conversation(project_id=args.project_id, title=args.title))


def command_conversations_get(client: HuabuClient, args: argparse.Namespace) -> None:
    print_json(client.get_conversation(args.conversation_id, project_id=args.project_id))


def command_conversations_append(client: HuabuClient, args: argparse.Namespace) -> None:
    attachments = parse_json_array_file(args.attachments_file, "attachments")
    metadata = parse_json_file(args.metadata_file, "metadata") or {}
    print_json(
        client.append_conversation_message(
            args.conversation_id,
            project_id=args.project_id,
            role=args.role,
            content=args.content,
            event_type=args.event_type,
            attachments=attachments,
            metadata=metadata,
        )
    )


def command_run(client: HuabuClient, args: argparse.Namespace) -> None:
    canvas_context = parse_json_value(args.canvas_context_json, "canvas context") or {}
    file_context = parse_json_file(args.canvas_context_file, "canvas context")
    if file_context is not None:
        canvas_context = {**canvas_context, **file_context}
    question_response = parse_json_value(args.question_response_json, "question response")
    image_urls = args.image_url or []
    video_urls = args.video_url or []
    validate_media_urls(image_urls=image_urls, video_urls=video_urls)
    if args.project_id:
        client.get_project(args.project_id)
    if args.conversation_id:
        client.get_conversation(args.conversation_id, project_id=args.project_id)
    result = client.create_run(
        prompt=args.prompt,
        project_id=args.project_id,
        conversation_id=args.conversation_id,
        canvas_context=canvas_context,
        image_urls=image_urls,
        video_urls=video_urls,
        question_response=question_response,
    )
    if not args.watch:
        print_json(result)
        return
    run = result.get("run", {}) if isinstance(result, dict) else {}
    run_id = str(run.get("id") or "")
    if not run_id:
        raise SystemExit("Run response did not include run.id")
    summary = watch_events(client, run_id=run_id, project_id=args.project_id, raw=args.raw_events)
    output = {"created": result, "summary": summary.to_dict()}
    try:
        output["final_run"] = client.get_run(run_id, project_id=args.project_id)
    except ApiError:
        pass
    print_json(output)


def watch_events(client: HuabuClient, *, run_id: str, project_id: str | None, raw: bool) -> EventSummary:
    summary = EventSummary()
    for event in client.stream_run_events(run_id, project_id=project_id):
        summary.update(event)
        if raw:
            print_json(event)
        else:
            name = event.get("event")
            data = event.get("data")
            if name == "message" and isinstance(data, str):
                print(data, end="", flush=True)
            elif name not in {"keepalive"}:
                print(f"\n[{name}] {json.dumps(data, ensure_ascii=False)}", flush=True)
        if event.get("event") == "done":
            break
    if not raw:
        print()
    return summary


def command_events(client: HuabuClient, args: argparse.Namespace) -> None:
    summary = watch_events(client, run_id=args.run_id, project_id=args.project_id, raw=args.raw)
    if args.summary:
        print_json(summary.to_dict())


def command_run_get(client: HuabuClient, args: argparse.Namespace) -> None:
    print_json(client.get_run(args.run_id, project_id=args.project_id))


def command_feedback(client: HuabuClient, args: argparse.Namespace) -> None:
    canvas_context = parse_json_value(args.canvas_context_json, "canvas context") or {}
    file_context = parse_json_file(args.canvas_context_file, "canvas context")
    if file_context is not None:
        canvas_context = {**canvas_context, **file_context}
    operation = parse_json_value(args.operation_json, "operation") or {}
    results = parse_json_array_file(args.results_file, "results")
    feedback = {
        "event_type": args.event_type,
        "summary": args.summary,
        "operation": operation,
        "error": args.error,
        "results": results,
    }
    result = client.send_tool_feedback(
        conversation_id=args.conversation_id,
        project_id=args.project_id,
        feedback=feedback,
        canvas_context=canvas_context,
    )
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Huabu canvas agent API helper")
    parser.add_argument("--env-file", help="Path to a .env file. Defaults to .env in the current directory, scripts directory, or skill directory.")
    parser.add_argument("--token", help="System access token. Defaults to YUNJIAN_SYSTEM_TOKEN.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    projects = subparsers.add_parser("projects", help="Project operations")
    project_subparsers = projects.add_subparsers(dest="project_command", required=True)
    list_parser = project_subparsers.add_parser("list", help="List workspace projects")
    list_parser.add_argument("--view", default="recent", choices=["recent", "all"])
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--offset", type=int, default=0)
    list_parser.add_argument("--no-description", action="store_true")
    list_parser.add_argument("--json", action="store_true", help="Print full list response instead of items only")
    list_parser.set_defaults(func=command_projects_list)

    get_parser = project_subparsers.add_parser("get", help="Get one project")
    get_parser.add_argument("project_id")
    get_parser.set_defaults(func=command_projects_get)

    create_parser = project_subparsers.add_parser("create", help="Create a workspace project")
    create_parser.add_argument("--name", default="未命名项目")
    create_parser.add_argument("--canvas-data-file")
    create_parser.set_defaults(func=command_projects_create)

    ensure_parser = project_subparsers.add_parser("ensure", help="Verify a project or create one")
    ensure_parser.add_argument("--project-id")
    ensure_parser.add_argument("--name", default="未命名项目")
    ensure_parser.add_argument("--use-recent", action="store_true", help="Use newest recent project if present")
    ensure_parser.set_defaults(func=command_projects_ensure)

    conversations = subparsers.add_parser("conversations", help="Canvas conversation operations")
    conversation_subparsers = conversations.add_subparsers(dest="conversation_command", required=True)
    conversation_list = conversation_subparsers.add_parser("list", help="List canvas conversations")
    conversation_list.add_argument("--project-id")
    conversation_list.add_argument("--limit", type=int, default=20)
    conversation_list.add_argument("--offset", type=int, default=0)
    conversation_list.add_argument("--json", action="store_true", help="Print full list response instead of items only")
    conversation_list.set_defaults(func=command_conversations_list)

    conversation_create = conversation_subparsers.add_parser("create", help="Create a canvas conversation")
    conversation_create.add_argument("--project-id")
    conversation_create.add_argument("--title", default="画布 Agent")
    conversation_create.set_defaults(func=command_conversations_create)

    conversation_get = conversation_subparsers.add_parser("get", help="Get one canvas conversation")
    conversation_get.add_argument("conversation_id")
    conversation_get.add_argument("--project-id")
    conversation_get.set_defaults(func=command_conversations_get)

    conversation_append = conversation_subparsers.add_parser("append", help="Append a message to a canvas conversation")
    conversation_append.add_argument("conversation_id")
    conversation_append.add_argument("--project-id")
    conversation_append.add_argument("--role", default="assistant")
    conversation_append.add_argument("--content", required=True)
    conversation_append.add_argument("--event-type")
    conversation_append.add_argument("--attachments-file")
    conversation_append.add_argument("--metadata-file")
    conversation_append.set_defaults(func=command_conversations_append)

    run_parser = subparsers.add_parser("run", help="Create a durable canvas agent run")
    run_parser.add_argument("--prompt")
    run_parser.add_argument("--project-id")
    run_parser.add_argument("--conversation-id")
    run_parser.add_argument("--image-url", action="append")
    run_parser.add_argument("--video-url", action="append")
    run_parser.add_argument("--canvas-context-json")
    run_parser.add_argument("--canvas-context-file")
    run_parser.add_argument("--question-response-json")
    run_parser.add_argument("--watch", action="store_true")
    run_parser.add_argument("--raw-events", action="store_true")
    run_parser.set_defaults(func=command_run)

    events_parser = subparsers.add_parser("events", help="Stream run events")
    events_parser.add_argument("--run-id", required=True)
    events_parser.add_argument("--project-id")
    events_parser.add_argument("--raw", action="store_true")
    events_parser.add_argument("--summary", action="store_true")
    events_parser.set_defaults(func=command_events)

    run_get_parser = subparsers.add_parser("run-get", help="Get durable run status")
    run_get_parser.add_argument("--run-id", required=True)
    run_get_parser.add_argument("--project-id")
    run_get_parser.set_defaults(func=command_run_get)

    feedback_parser = subparsers.add_parser("feedback", help="Send canvas tool-result feedback")
    feedback_parser.add_argument("--conversation-id", required=True)
    feedback_parser.add_argument("--project-id")
    feedback_parser.add_argument("--event-type", default="generation_failed")
    feedback_parser.add_argument("--summary", default="Canvas operation failed")
    feedback_parser.add_argument("--error", required=True)
    feedback_parser.add_argument("--operation-json")
    feedback_parser.add_argument("--results-file")
    feedback_parser.add_argument("--canvas-context-json")
    feedback_parser.add_argument("--canvas-context-file")
    feedback_parser.set_defaults(func=command_feedback)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = HuabuClient(Config.from_args(args))
        args.func(client, args)
        return 0
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
