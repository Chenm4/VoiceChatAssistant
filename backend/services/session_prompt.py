"""Session prompt snapshots and dynamically shared interview background."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from backend.api.models import Session, SessionConfig


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_FILE = PROJECT_ROOT / "prompt_lab" / "prompts.json"
BACKGROUND_FILE = PROJECT_ROOT / "prompt_lab" / "background.json"
DEFAULT_SESSION_PROMPT_ID = "spoken_keypoints"


ANSWER_HIGHLIGHT_PROMPT = """【答题高亮输出协议】
先完成分析并核对答案，再在回答的最后追加且仅追加一个 ```json 代码块，代码块后不要输出其他内容。
JSON 格式为 {"answer_highlight":{"answers":[{"question":"1","type":"choice","answer":"A"}]}}。
仅对当前问题中的选择题和判断题输出条目。选择题 type 为 choice，answer 为大写选项字母，多选如 AC；判断题 type 为 boolean，answer 为 对 或 错。
question 必须提取当前题目原有编号（例如题号 12 输出 "12"），前端会将其以选项字母三分之一的大小显示在选项下方；没有明确题号时使用空字符串，禁止自行编号。多题按题目顺序列出多个条目。
每个模型独立输出自己核对后的答案；模型来源和左右位置由前端按并行回答卡片顺序标注，不要在 JSON 中混入其他模型的答案。
非选择/判断题，或题干/选项不完整、无法确定答案时，answers 输出空数组，不要猜测。
JSON 必须有效，不含注释；最终答案须与正文结论一致。不要在分析开头输出这个 JSON。"""


def _with_answer_highlight(rules: Optional[str], config: Optional[SessionConfig]) -> Optional[str]:
    if config and config.answer_highlight_enabled:
        return "\n\n".join(part for part in (rules, ANSWER_HIGHLIGHT_PROMPT) if part)
    return rules


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_prompt_template_snapshot(
    prompt_id: str = DEFAULT_SESSION_PROMPT_ID,
) -> Dict[str, Any]:
    """Load the latest current snapshot for ``prompt_id`` from the lab catalog.

    The returned values are copied into a session. Existing sessions therefore
    keep the exact template version they selected even when the lab template is
    edited later.
    """
    catalog = _read_json(PROMPTS_FILE)
    if not isinstance(catalog, list):
        raise ValueError("提示词模板文件格式错误")

    candidates = [item for item in catalog if item.get("id") == prompt_id]
    if not candidates:
        raise ValueError(f"找不到默认提示词模板: {prompt_id}")

    prompt = max(candidates, key=lambda item: int(item.get("version", 1)))
    system_prompt = str(prompt.get("system_prompt") or "")
    user_prompt_template = str(prompt.get("user_prompt_template") or "")
    if not system_prompt.strip():
        raise ValueError(f"提示词模板缺少 System Prompt: {prompt_id}")
    if "{{question}}" not in user_prompt_template:
        raise ValueError(f"提示词模板缺少 {{question}} 占位符: {prompt_id}")

    return {
        "id": prompt_id,
        "version": int(prompt.get("version", 1)),
        "system_prompt": system_prompt,
        "user_prompt_template": user_prompt_template,
    }


def create_default_session_config() -> SessionConfig:
    """Create the config used only for newly created sessions."""
    prompt = load_prompt_template_snapshot()
    return SessionConfig(
        system_prompt=prompt["system_prompt"],
        prompt_template_id=prompt["id"],
        prompt_template_version=prompt["version"],
        user_prompt_template=prompt["user_prompt_template"],
        background_mode="shared",
    )


def load_shared_background() -> str:
    """Read the current shared background from disk for every model request."""
    try:
        payload = _read_json(BACKGROUND_FILE)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取共享面试背景失败: %s", exc)
        return ""
    if not isinstance(payload, dict):
        logger.warning("共享面试背景文件格式错误: %s", BACKGROUND_FILE)
        return ""
    return str(payload.get("content") or "")


def compose_session_system_prompt(session: Session) -> Optional[str]:
    """Compose rules with the background selected by the session mode.

    ``shared`` reads the global file live, ``custom`` uses the session copy,
    and ``none`` sends no background. A missing mode identifies a legacy
    session and intentionally sends no additional background, preventing old
    combined prompts from receiving the same facts twice.
    """
    config = session.session_config
    if config and config.active_scene:
        # Scene instructions belong only to the current user request, never history.
        rules = config.system_prompt if config.system_prompt is not None else session.system_prompt or config.scene_common_rules
        return _with_answer_highlight(rules.strip() or None, config)
    if config is not None and config.system_prompt is not None:
        rules = config.system_prompt
    else:
        rules = session.system_prompt or ""

    background = ""
    mode = config.background_mode if config else None
    if mode == "shared":
        background = load_shared_background()
    elif mode == "custom":
        background = config.background_context or ""

    parts = []
    if rules.strip():
        parts.append(rules.strip())
    if background.strip():
        parts.append(
            "【候选人背景资料】\n"
            + background.strip()
            + "\n\n涉及个人经历或项目的问题只能依据以上资料回答；"
            "资料没有提供的细节不要猜测或编造。"
        )
    return _with_answer_highlight("\n\n".join(parts) or None, config)


def render_session_user_prompt(session: Session, question: str) -> str:
    """Render the session's snapshotted user template for one question."""
    config = session.session_config
    if config and config.active_scene:
        scene = config.active_scene
        parts = ["【当前场景】\n" + scene.name]
        if scene.rules.strip():
            parts.append("【场景要求】\n" + scene.rules.strip())
        if scene.background.strip():
            parts.append("【当前项目资料】\n" + scene.background.strip())
        parts.append("历史仅供理解问题，其他项目的经历不能当作当前项目事实。")
        parts.append("【当前问题】\n" + question)
        return "\n\n".join(parts)
    template = config.user_prompt_template if config else None
    if not template:
        return question
    if "{{question}}" not in template:
        logger.warning(
            "会话 %s 的 User Prompt 缺少 {{question}} 占位符，使用原始问题",
            session.id,
        )
        return question
    return template.replace("{{question}}", question)
