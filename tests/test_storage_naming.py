# tests/test_storage_naming.py
from app.storage.naming import new_timestamped_id


def test_new_timestamped_id_has_prefix_and_timestamp_shape():
    job_id = new_timestamped_id("asr")
    parts = job_id.split("_")
    assert parts[0] == "asr"
    assert len(parts[1]) == 8  # YYYYMMDD
    assert parts[1].isdigit()
    assert len(parts[2]) == 6  # HHMMSS
    assert parts[2].isdigit()
    assert len(parts[3]) == 8  # random suffix
    assert parts[3].isalnum()


def test_new_timestamped_id_unique():
    a = new_timestamped_id("tts")
    b = new_timestamped_id("tts")
    assert a != b
