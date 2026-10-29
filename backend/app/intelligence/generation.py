import json
from .prompts import SYSTEM, REWRITE


def history_pairs(messages, source_ids=None):
    if source_ids is not None:
        allowed = set(source_ids)
        messages = [m for m in messages if set(m['source_ids']).issubset(allowed)]
    return [{'role': x['role'], 'content': x['content'][:1500]} for x in messages if x['status'] == 'complete'][-6:]


def query_for(question, history, llm):
    if not history: return question
    rewritten = llm.complete([{'role':'system','content':REWRITE},
        {'role':'user','content':json.dumps({'history':history,'question':question}, ensure_ascii=False)}], max_tokens=256).strip()
    return rewritten[:1000] if rewritten else question


def messages_for(question, history, evidence):
    # Evidence JSON keeps text clearly separate from system policy; not an injection-proof sandbox.
    context = [{'label':c['label'],'filename':c['filename'],'page':c['page_start'],'text':c['text']} for c in evidence]
    return [{'role':'system','content':SYSTEM}, {'role':'user','content':json.dumps({
        'history_for_reference_only':history, 'selected_evidence':context, 'question':question}, ensure_ascii=False)}]
