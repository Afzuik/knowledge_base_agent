"""Single-process execution mechanism. Receives a callback; never imports application."""
from contextlib import contextmanager
import fcntl
import logging
from threading import Event, Thread

log = logging.getLogger(__name__)


@contextmanager
def process_lock(data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / '.app.lock').open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('This data directory is already used by another server. Use one worker.') from exc
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class LocalRunner:
    def __init__(self, callback, interval=0.25):
        self.callback = callback
        self.interval = interval
        self.stop_event = Event()
        self.thread = Thread(target=self._run, name='document-ingestion', daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                worked = self.callback()
            except Exception:
                log.exception('Background execution failed')
                worked = False
            if not worked:
                self.stop_event.wait(self.interval)

    def stop(self):
        self.stop_event.set()
        self.thread.join()  # Graceful drain; process termination is recovered next startup.
