from devserver_mcp.log_storage import LogStorage


def test_log_storage_append_and_get_range_default():
    storage = LogStorage(max_lines=100)

    for i in range(10):
        storage.append(f"Log line {i}")

    logs, total, has_more = storage.get_range()

    assert total == 10
    assert len(logs) == 10
    assert has_more is False
    assert logs[0] == "Log line 9"
    assert logs[9] == "Log line 0"


def test_log_storage_respects_max_lines():
    storage = LogStorage(max_lines=5)

    for i in range(10):
        storage.append(f"Log line {i}")

    logs, total, has_more = storage.get_range(limit=10)

    assert total == 5
    assert len(logs) == 5
    assert logs[0] == "Log line 9"
    assert logs[4] == "Log line 5"


def test_log_storage_pagination_forward():
    storage = LogStorage()

    for i in range(100):
        storage.append(f"Log {i}")

    logs, total, has_more = storage.get_range(offset=10, limit=20, reverse=False)

    assert total == 100
    assert len(logs) == 20
    assert has_more is True
    assert logs[0] == "Log 10"
    assert logs[19] == "Log 29"


def test_log_storage_pagination_reverse():
    storage = LogStorage()

    for i in range(100):
        storage.append(f"Log {i}")

    logs, total, has_more = storage.get_range(offset=10, limit=20, reverse=True)

    assert total == 100
    assert len(logs) == 20
    assert has_more is True
    assert logs[0] == "Log 89"
    assert logs[19] == "Log 70"


def test_log_storage_negative_offset():
    storage = LogStorage()

    for i in range(100):
        storage.append(f"Log {i}")

    # With negative offset=-20, it becomes offset=80 (100-20)
    # With reverse=True and limit=10, we get the 10 items before position 80
    logs, total, has_more = storage.get_range(offset=-20, limit=10, reverse=True)

    assert total == 100
    assert len(logs) == 10
    assert has_more is True
    assert logs[0] == "Log 19"
    assert logs[9] == "Log 10"


def test_log_storage_offset_beyond_total():
    storage = LogStorage()

    for i in range(10):
        storage.append(f"Log {i}")

    logs, total, has_more = storage.get_range(offset=20, limit=10, reverse=False)

    assert total == 10
    assert len(logs) == 0
    assert has_more is False


def test_log_storage_empty():
    storage = LogStorage()

    logs, total, has_more = storage.get_range()

    assert total == 0
    assert len(logs) == 0
    assert has_more is False


def test_log_storage_clear():
    storage = LogStorage()

    for i in range(10):
        storage.append(f"Log {i}")

    assert len(storage) == 10

    storage.clear()

    assert len(storage) == 0
    logs, total, has_more = storage.get_range()
    assert total == 0


def test_log_storage_has_more_edge_cases():
    storage = LogStorage()

    for i in range(50):
        storage.append(f"Log {i}")

    _, _, has_more = storage.get_range(offset=0, limit=50, reverse=True)
    assert has_more is False

    _, _, has_more = storage.get_range(offset=0, limit=49, reverse=True)
    assert has_more is True

    _, _, has_more = storage.get_range(offset=49, limit=10, reverse=False)
    assert has_more is False


def test_log_storage_thread_safety():
    import threading
    import time

    storage = LogStorage(max_lines=1000)
    errors = []

    def writer(thread_id):
        try:
            for i in range(100):
                storage.append(f"Thread {thread_id} - Log {i}")
                time.sleep(0.0001)
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(50):
                logs, total, _ = storage.get_range(limit=10)
                assert len(logs) <= 10
                assert total >= 0
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = []
    for i in range(3):
        t = threading.Thread(target=writer, args=(i,))
        threads.append(t)
        t.start()

    reader_thread = threading.Thread(target=reader)
    threads.append(reader_thread)
    reader_thread.start()

    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(storage) <= 1000
