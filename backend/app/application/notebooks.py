"""Notebook use cases; HTTP and SQL details stay outside this layer."""
from .errors import AppError


class Notebooks:
    def __init__(self, repo):
        self.repo = repo

    def require(self, owner, notebook_id):
        row = self.repo.notebook(owner, notebook_id)
        if row is None:
            raise AppError(404, 'not_found', '专题不存在。')
        return row

    def list(self, owner):
        return self.repo.notebooks(owner)

    def create(self, owner, name):
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise AppError(422, 'invalid_name', '专题名称需要 1～100 个字符。')
        return self.repo.create_notebook(owner, name)
