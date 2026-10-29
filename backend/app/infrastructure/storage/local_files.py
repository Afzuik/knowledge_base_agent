"""Bounded local file IO. File names never become storage paths."""
import hashlib
import os
import re
from uuid import uuid4


class UploadRejected(ValueError):
    pass


class FileIntegrityError(ValueError):
    pass


class LocalFiles:
    def __init__(self, root):
        self.root = root.resolve()
        self.pending = self.root / '.pending'
        self.pending.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        if not re.fullmatch(r'[a-f0-9]{32}', key):
            raise ValueError('Invalid storage key')
        path = self.root / key
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError('Invalid storage path')
        return path

    def stage(self, stream, limit):
        temp = self.pending / (uuid4().hex + '.part')
        digest = hashlib.sha256(); size = 0
        try:
            with temp.open('xb') as f:
                while block := stream.read(64 * 1024):
                    size += len(block)
                    if size > limit:
                        raise UploadRejected('文件超过大小限制。')
                    digest.update(block); f.write(block)
                f.flush(); os.fsync(f.fileno())
            if not size:
                raise UploadRejected('文件为空。')
            return temp, size, digest.hexdigest()
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    def promote(self, temp, key):
        target = self.path(key)
        if target.exists():
            raise FileExistsError('Storage key already exists')
        os.replace(temp, target)

    def remove(self, key):
        self.path(key).unlink(missing_ok=True)

    def discard(self, temp):
        if temp.parent != self.pending or temp.is_symlink():
            raise ValueError('Invalid temporary path')
        temp.unlink(missing_ok=True)

    def read_verified(self, key, expected_size, expected_hash, limit):
        with self.path(key).open('rb') as f:
            content = f.read(limit + 1)
        if len(content) != expected_size or len(content) > limit or hashlib.sha256(content).hexdigest() != expected_hash:
            raise FileIntegrityError('原始文件内容已改变，请恢复原文件或作为新资料上传。')
        return content

    def exists(self, key):
        return self.path(key).is_file()

    def cleanup(self, known_keys):
        # Startup only, while process lock is held and before accepting requests.
        for path in self.pending.glob('*.part'):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        for path in self.root.iterdir():
            if re.fullmatch(r'[a-f0-9]{32}', path.name) and path.is_file() and not path.is_symlink() and path.name not in known_keys:
                path.unlink()
