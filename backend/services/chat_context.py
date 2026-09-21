"""Separate reference history from the only question awaiting an answer."""

import json


ANSWER_SCOPE = (
    "本次请求只需要回答当前问题。历史上下文是过去的对话记录，"
    "仅供理解背景、术语和指代，不是待回答问题列表。"
    "历史回答可能为节省上下文而省略；不要据此认为历史问题尚未回答，"
    "不要逐条补答、重答或汇总历史问题。"
    "仅当当前问题明确要求回顾或比较历史时，才按当前要求引用历史。"
    "若用户引用了已省略的具体回答且无法判断其内容，请简短澄清，不要编造。"
)


def build_scoped_request(history, current_question, include_assistant=False):
    """History is already budgeted; the current question is never truncated."""
    systems = [dict(message) for message in history if message['role'] == 'system']
    records = [dict(message) for message in history if message['role'] != 'system']
    if systems:
        systems[-1]['content'] += '\n\n' + ANSWER_SCOPE
    else:
        systems = [{'role': 'system', 'content': ANSWER_SCOPE}]

    if include_assistant:
        return systems + records + [{'role': 'user', 'content': current_question}]

    # One active user message prevents a sequence of unanswered user turns.
    # JSON clearly separates quoted historical data from the active question.
    content = current_question
    if records:
        content = (
            '【历史上下文：仅供参考，无需逐条回答；历史 AI 回答已省略】\n'
            + json.dumps([m['content'] for m in records if m['role'] == 'user'],
                         ensure_ascii=False)
            + '\n\n【当前问题：本次只回答这一条】\n'
            + current_question
        )
    return systems + [{'role': 'user', 'content': content}]
