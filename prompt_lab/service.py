"""Persistent batch runner for Qwen interview-answer prompt experiments."""

from backend.services.user_workspace import user_path, user_state, workspace

import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from openai import AsyncOpenAI



BASE_DIR = Path(__file__).resolve().parent



def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def get_catalog() -> Dict[str, Any]:
    sources = []
    for source in [source.dict() for source in user_state().config_sources]:
        qwen_models = [model for model in source.get("models", []) if model.lower().startswith("qwen")]
        if qwen_models and source.get("api_key"):
            sources.append({"name": source["name"], "models": qwen_models})
    return {
        "prompts": [
            {"version": 1, **prompt}
            for prompt in _read_json(user_path('prompt_lab/prompts.json'))
        ],
        "questions": _read_json(user_path('prompt_lab/questions.json')),
        "sources": sources,
        "background": _read_json(user_path('prompt_lab/background.json')),
    }


def save_background(content: str) -> Dict[str, Any]:
    """Persist the shared interview background used by chat and lab runs."""
    payload = {
        "name": "候选人面试背景",
        "content": str(content or "").strip(),
        "updated_at": int(time.time()),
    }
    _write_json(user_path('prompt_lab/background.json'), payload)
    return payload


def compose_lab_system_prompt(rules: str, background: str) -> str:
    parts = [str(rules or "").strip()]
    if str(background or "").strip():
        parts.append(
            "【候选人背景资料】\n"
            + str(background).strip()
            + "\n\n涉及个人经历或项目的问题只能依据以上资料回答；资料没有提供的细节不要猜测或编造。"
        )
    return "\n\n".join(part for part in parts if part)


def save_prompt(payload: Dict[str, Any], prompt_id: str = "") -> Dict[str, Any]:
    """Create or update a prompt while retaining the previous version on disk."""
    prompts = _read_json(user_path('prompt_lab/prompts.json'))
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    system_prompt = str(payload.get("system_prompt", "")).strip()
    user_prompt_template = str(payload.get("user_prompt_template", "")).strip()
    if not name or not system_prompt or not user_prompt_template:
        raise ValueError("名称、System Prompt 和 User Prompt 不能为空")
    if "{{question}}" not in user_prompt_template:
        raise ValueError("User Prompt 必须包含 {{question}} 占位符")

    now = int(time.time())
    if prompt_id:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', prompt_id):
            raise ValueError('提示词 ID 非法')
        index = next((i for i, item in enumerate(prompts) if item.get("id") == prompt_id), None)
        if index is None:
            raise KeyError(prompt_id)
        previous = prompts[index]
        previous_version = int(previous.get("version", 1))
        history_file = user_path('prompt_lab/data/prompt_history') / f"{prompt_id}_v{previous_version}_{now}.json"
        _write_json(history_file, {**previous, "version": previous_version})
        saved = {
            **previous,
            "name": name,
            "description": description,
            "system_prompt": system_prompt,
            "user_prompt_template": user_prompt_template,
            "version": previous_version + 1,
            "updated_at": now,
        }
        prompts[index] = saved
    else:
        base_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:32]
        if not base_id:
            base_id = "custom"
        new_id = f"{base_id}_{uuid.uuid4().hex[:8]}"
        saved = {
            "id": new_id,
            "name": name,
            "description": description,
            "system_prompt": system_prompt,
            "user_prompt_template": user_prompt_template,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        prompts.append(saved)

    _write_json(user_path('prompt_lab/prompts.json'), prompts)
    return saved


def list_prompt_history(prompt_id: str) -> List[Dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", prompt_id):
        raise ValueError("提示词 ID 非法")
    history = []
    for path in user_path('prompt_lab/data/prompt_history').glob(f"{prompt_id}_v*.json"):
        try:
            history.append(_read_json(path))
        except (OSError, json.JSONDecodeError):
            continue
    current = next((item for item in _read_json(user_path('prompt_lab/prompts.json')) if item.get("id") == prompt_id), None)
    if not current:
        raise KeyError(prompt_id)
    history.append({"version": 1, **current})
    return sorted(history, key=lambda item: int(item.get("version", 1)), reverse=True)


def _source_by_name(name: str) -> Dict[str, Any]:
    source = next((item for item in [source.dict() for source in user_state().config_sources] if item.get("name") == name), None)
    if not source:
        raise ValueError(f"配置源不存在: {name}")
    if not source.get("api_key"):
        raise ValueError(f"配置源 {name} 未设置 API Key")
    return source


def _run_path(run_id: str) -> Path:
    if not run_id or any(char not in "0123456789abcdef-" for char in run_id.lower()):
        raise ValueError("实验 ID 非法")
    return user_path('prompt_lab/data/runs') / f"{run_id}.json"


def load_run(run_id: str) -> Dict[str, Any]:
    path = _run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(run_id)
    return _read_json(path)


def list_runs() -> List[Dict[str, Any]]:
    summaries = []
    for path in sorted(user_path('prompt_lab/data/runs').glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            run = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        summaries.append({
            "id": run.get("id"),
            "name": run.get("name"),
            "status": run.get("status"),
            "created_at": run.get("created_at"),
            "finished_at": run.get("finished_at"),
            "completed": run.get("completed", 0),
            "total": run.get("total", 0),
            "models": run.get("models", []),
            "model_count": len(run.get("models", [])),
            "prompt_count": len(run.get("prompt_ids", [])),
            "question_count": len(run.get("question_ids", [])),
        })
    return summaries[:100]


def create_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    catalog = get_catalog()
    prompts = {item["id"]: item for item in catalog["prompts"]}
    questions = {item["id"]: item for item in catalog["questions"]}
    source = _source_by_name(payload["source_name"])
    background = catalog.get("background", {}).get("content", "")
    models = list(dict.fromkeys(payload["models"]))
    prompt_ids = list(dict.fromkeys(payload["prompt_ids"]))
    question_ids = list(dict.fromkeys(payload["question_ids"]))

    if not models or not prompt_ids or not question_ids:
        raise ValueError("至少选择一个模型、提示词和题目")
    invalid_models = [model for model in models if model not in source.get("models", []) or not model.lower().startswith("qwen")]
    if invalid_models:
        raise ValueError(f"模型不属于所选 Qwen 配置源: {invalid_models}")
    if any(item not in prompts for item in prompt_ids):
        raise ValueError("包含不存在的提示词模板")
    if any(item not in questions for item in question_ids):
        raise ValueError("包含不存在的题目")

    combinations = len(models) * len(prompt_ids) * len(question_ids)
    if combinations > 120:
        raise ValueError(f"单次最多运行 120 个组合，当前为 {combinations} 个")

    run_id = str(uuid.uuid4())
    now = int(time.time())
    items = []
    for question_id in question_ids:
        for prompt_id in prompt_ids:
            for model in models:
                question = questions[question_id]
                prompt = prompts[prompt_id]
                effective_system_prompt = compose_lab_system_prompt(
                    prompt["system_prompt"], background
                )
                rendered_user_prompt = prompt["user_prompt_template"].replace(
                    "{{question}}", question["question"]
                )
                items.append({
                    "id": str(uuid.uuid4()),
                    "question_id": question_id,
                    "question": question["question"],
                    "category": question["category"],
                    "prompt_id": prompt_id,
                    "prompt_name": prompt["name"],
                    "prompt_snapshot": {
                        "id": prompt_id,
                        "name": prompt["name"],
                        "description": prompt.get("description", ""),
                        "base_system_prompt": prompt["system_prompt"],
                        "background_context": background,
                        "system_prompt": effective_system_prompt,
                        "user_prompt_template": prompt["user_prompt_template"],
                        "rendered_user_prompt": rendered_user_prompt,
                    },
                    "request_messages": [
                        {"role": "system", "content": effective_system_prompt},
                        {"role": "user", "content": rendered_user_prompt},
                    ],
                    "model": model,
                    "source_name": payload["source_name"],
                    "parameters": {
                        "temperature": payload.get("temperature", 0.5),
                        "top_p": payload.get("top_p", 0.9),
                        "enable_thinking": False,
                    },
                    "status": "pending",
                    "answer": "",
                    "error": None,
                    "latency_ms": None,
                    "char_count": 0,
                    "rating": None,
                    "note": "",
                })

    run = {
        "id": run_id,
        "name": str(payload.get("name") or "").strip(),
        "status": "running",
        "source_name": payload["source_name"],
        "models": models,
        "prompt_ids": prompt_ids,
        "question_ids": question_ids,
        "temperature": payload.get("temperature", 0.5),
        "top_p": payload.get("top_p", 0.9),
        "max_concurrency": payload.get("max_concurrency", 2),
        "created_at": now,
        "finished_at": None,
        "completed": 0,
        "failed": 0,
        "total": len(items),
        "items": items,
    }
    _write_json(_run_path(run_id), run)
    workspace().locks[run_id] = asyncio.Lock()
    workspace().tasks[run_id] = asyncio.create_task(_execute_run(run_id, source))
    return run


async def _execute_run(run_id: str, source: Dict[str, Any]) -> None:
    run = load_run(run_id)
    semaphore = asyncio.Semaphore(max(1, min(int(run["max_concurrency"]), 5)))
    client = AsyncOpenAI(api_key=source["api_key"], base_url=source["base_url"], timeout=120.0)

    async def execute_item(item_index: int) -> None:
        async with semaphore:
            current = load_run(run_id)
            item = current["items"][item_index]
            started = time.monotonic()
            try:
                response = await client.chat.completions.create(
                    model=item["model"],
                    messages=item["request_messages"],
                    temperature=current["temperature"],
                    top_p=current["top_p"],
                    stream=False,
                    extra_body={"enable_thinking": False},
                )
                answer = response.choices[0].message.content or ""
                status, error = "completed", None
            except Exception as exc:  # Save individual failures without aborting the matrix.
                answer, status, error = "", "failed", str(exc)
            latency_ms = int((time.monotonic() - started) * 1000)

            async with workspace().locks[run_id]:
                latest = load_run(run_id)
                target = latest["items"][item_index]
                target.update({
                    "status": status,
                    "answer": answer,
                    "error": error,
                    "latency_ms": latency_ms,
                    "char_count": len(answer),
                })
                latest["completed"] = sum(1 for entry in latest["items"] if entry["status"] in {"completed", "failed"})
                latest["failed"] = sum(1 for entry in latest["items"] if entry["status"] == "failed")
                _write_json(_run_path(run_id), latest)

    try:
        await asyncio.gather(*(execute_item(index) for index in range(len(run["items"]))))
        async with workspace().locks[run_id]:
            latest = load_run(run_id)
            latest["status"] = "completed" if latest["failed"] == 0 else "completed_with_errors"
            latest["finished_at"] = int(time.time())
            _write_json(_run_path(run_id), latest)
    finally:
        workspace().tasks.pop(run_id, None)


async def update_review(run_id: str, item_id: str, rating: Any, note: str) -> Dict[str, Any]:
    lock = workspace().locks.setdefault(run_id, asyncio.Lock())
    async with lock:
        run = load_run(run_id)
        item = next((entry for entry in run["items"] if entry["id"] == item_id), None)
        if not item:
            raise KeyError(item_id)
        item["rating"] = rating
        item["note"] = note or ""
        _write_json(_run_path(run_id), run)
        return item
