"""Notes are independent products; they never update answers or enter retrieval."""
import json
from .errors import AppError
from .note_export import reference_labels, markdown_for, filename_for


class Notes:
    def __init__(self, repo):
        self.repo = repo

    def require_notebook(self, owner, notebook_id):
        if not self.repo.notebook_exists(owner,notebook_id): raise AppError(404,'not_found','专题不存在。')

    def describe(self, row):
        result = dict(row)
        citations = json.loads(result.pop('citations_snapshot_json'))
        labels = reference_labels(result['body_markdown'])
        known = {c['label'] for c in citations}
        return {**result,'citations':citations,'used_labels':[x for x in labels if x in known],
                'invalid_labels':[x for x in labels if x not in known]}

    def list(self, owner, notebook_id):
        self.require_notebook(owner,notebook_id)
        return [{k:r[k] for k in ('id','notebook_id','origin_message_id','title','revision','created_at','updated_at')}
                for r in self.repo.list(owner,notebook_id)]

    def get(self, owner, notebook_id, note_id):
        row = self.repo.get(owner,notebook_id,note_id)
        if row is None: raise AppError(404,'not_found','笔记不存在或不属于当前专题。')
        return self.describe(row)

    @staticmethod
    def validate_title(title):
        title = title.strip()
        if not 1 <= len(title) <= 120 or any(ord(c)<32 or ord(c)==127 for c in title):
            raise AppError(422,'invalid_title','标题需要 1～120 个字符，不能包含换行或控制字符。')
        return title

    def create(self, owner, notebook_id, message_id, title=None):
        self.require_notebook(owner,notebook_id)
        if title is not None: title = self.validate_title(title)
        row, outcome = self.repo.create_snapshot(owner,notebook_id,message_id,title)
        if outcome == 'not_found': raise AppError(404,'not_found','回答不存在或不属于当前专题。')
        if outcome == 'not_complete': raise AppError(409,'answer_not_complete','只能保存完整生成的助手回答。')
        return self.describe(row), outcome == 'created'

    def update(self, owner, notebook_id, note_id, revision, title, body):
        title = self.validate_title(title)
        if len(body)>100000: raise AppError(422,'body_too_long','笔记正文超过长度限制。')
        row,outcome = self.repo.update(owner,notebook_id,note_id,revision,title,body)
        if outcome == 'not_found': raise AppError(404,'not_found','笔记不存在或不属于当前专题。')
        if outcome == 'conflict': raise AppError(409,'revision_conflict','笔记已在其他页面更新。当前输入已保留，请复制备份或重新加载，不能直接覆盖。')
        return self.describe(row)

    def export(self, owner, notebook_id, note_id, revision):
        note = self.get(owner,notebook_id,note_id)
        if note['revision'] != revision: raise AppError(409,'revision_conflict','导出版本已变化，请重新加载并核对内容。')
        if note['invalid_labels']: raise AppError(422,'invalid_citations','存在无效引用编号：' + '、'.join(note['invalid_labels']) + '。请修正后导出。')
        return markdown_for(note,note['citations'],note['used_labels']),filename_for(note['title'])
