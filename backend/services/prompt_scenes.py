"""Shared scene catalog; sessions keep the selected rules as a snapshot."""

from backend.services.user_workspace import user_path
import json
from pathlib import Path
from backend.api.models import SceneCatalog, PromptScene



def exam_scenes():
    templates = json.loads(user_path('prompt_lab/prompts.json').read_text(encoding='utf-8'))
    labels = {
        'written_exam_concise': ('笔试专用', '选择、填空、极简代码放大'),
        'ai_coding_exam': ('AI Coding 提问助手', '生成可直接发给 AI 的提示词'),
    }
    by_id = {item['id']: item for item in templates}
    return [PromptScene(id=key, name=name, description=description,
                        rules=by_id[key]['system_prompt'], use_scene_rules_as_system=True)
            for key, (name, description) in labels.items() if key in by_id]


def load_catalog():
    if user_path('prompt_scenes.json').exists():
        return SceneCatalog(**json.loads(user_path('prompt_scenes.json').read_text(encoding='utf-8')))
    return SceneCatalog(scenes=[
        PromptScene(id='general', name='通用八股', description='概念、原理与技术问答', rules='先直接回答，再简要解释原理和适用场景。'),
        PromptScene(id='algorithm', name='算法讲解', description='思路、代码与复杂度', rules='先说明解题思路，再给出代码、边界条件和复杂度。'),
    ] + exam_scenes())


def save_catalog(catalog):
    user_path('prompt_scenes.json').parent.mkdir(parents=True, exist_ok=True)
    temporary = user_path('prompt_scenes.json').with_suffix('.tmp')
    temporary.write_text(json.dumps(catalog.dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(user_path('prompt_scenes.json'))
