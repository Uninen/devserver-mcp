from collections import deque
from threading import Lock


class LogStorage:
    def __init__(self, max_lines: int = 10000):
        self.max_lines = max_lines
        self._logs: deque[str] = deque(maxlen=max_lines)
        self._lock = Lock()

    def append(self, line: str) -> None:
        with self._lock:
            self._logs.append(line)

    def get_range(self, offset: int = 0, limit: int = 100, reverse: bool = True) -> tuple[list[str], int, bool]:
        with self._lock:
            total = len(self._logs)

            if total == 0:
                return [], 0, False

            if offset < 0:
                # Negative offset means "from the end"
                # -1 means last item, -10 means 10th from last
                offset = max(0, total + offset)

            if reverse:
                start = max(0, total - offset - limit)
                end = total - offset
                if end <= 0:
                    # Offset is beyond total, no logs to return
                    return [], total, False
                logs = list(self._logs)[start:end]
                logs.reverse()
                has_more = start > 0
            else:
                start = offset
                end = min(offset + limit, total)
                logs = list(self._logs)[start:end]
                has_more = end < total

            return logs, total, has_more

    def clear(self) -> None:
        with self._lock:
            self._logs.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._logs)
