"""Build ordered user-only history and scope the answer to the latest question."""

ANSWER_SCOPE = (
    '本次请求只回答 messages 数组中最后一条 user 消息（当前问题）。'
    '此前所有 user 消息都是已经结束的历史问题，仅供理解背景、术语和指代。'
    '历史 AI 回答已省略；不要据此认为历史问题尚未回答。'
    '禁止逐条补答、重答或汇总历史问题。'
    '仅当最后一个问题明确要求回顾或比较历史时，才按当前要求引用历史。'
    '若用户引用了已省略的具体回答且无法判断其内容，请简短澄清，不要编造。'
)


def build_scoped_request(history, current_question, include_assistant=False):
    """Preserve budgeted user turns; never send historical assistant responses.

    include_assistant remains accepted for older callers/configurations, but
    user-only context is enforced independently of that legacy setting.
    """
    instructions = [message['content'] for message in history if message['role'] == 'system'] + [ANSWER_SCOPE]
    records = [{'role': 'user', 'content': '【已结束的历史问题：仅供参考，不要回答】\n' + message['content']}
               for message in history if message['role'] == 'user']
    return [{'role': 'system', 'content': '\n\n'.join(instructions)}] + records + [
        {'role': 'user', 'content': '【本次回答范围】\n' + ANSWER_SCOPE + '\n\n【当前问题：唯一待回答内容】\n' + current_question}]
