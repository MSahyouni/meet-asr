# tests/test_jobs_persistence.py — disk-backed async job store + resume
import json
import pathlib

import pytest


@pytest.fixture
def job_store(tmp_path, monkeypatch):
    from app.config import settings
    from app.server import jobs as jobs_mod

    monkeypatch.setattr(settings, "OUTPUTS_DIR", tmp_path)
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(jobs_mod, "JOBS_DIR", jobs_dir)
    jobs_mod.JOBS.clear()
    yield jobs_mod
    jobs_mod.JOBS.clear()


def test_set_job_writes_queued_status_immediately(job_store):
    path = job_store.set_job("asr_test1", status="queued", user_email=None)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "queued"
    assert job_store.JOBS["asr_test1"]["status"] == "queued"


def test_set_job_user_scoped_path(job_store, tmp_path):
    path = job_store.set_job(
        "asr_user1",
        status="done",
        user_email="user@example.com",
        result={"text": "مرحبا"},
    )
    assert path.exists()
    assert path.parent.name == "jobs"
    assert path.resolve().is_relative_to(tmp_path.resolve())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "done"
    assert data["result"]["text"] == "مرحبا"
    assert data["user_email"] == "user@example.com"


def test_find_job_file_after_memory_clear(job_store):
    job_store.set_job(
        "asr_find1",
        status="done",
        user_email="findme@local",
        result={"ok": True},
    )
    job_store.JOBS.clear()
    found = job_store.find_job_file("asr_find1")
    assert found is not None
    assert found.exists()
    payload = job_store.load_job_payload("asr_find1")
    assert payload is not None
    assert payload["status"] == "done"
    assert payload["result"]["ok"] is True


def test_reload_marks_queued_without_staging_as_interrupted(job_store):
    job_store.set_job("q1", status="queued", user_email=None)
    job_store.set_job("r1", status="running", user_email="u@local")
    job_store.set_job("d1", status="done", user_email=None, result={"x": 1})
    job_store.JOBS.clear()

    stats = job_store.reload_jobs_from_disk()
    assert stats["interrupted"] == 2
    assert stats["restored"] == 1
    assert stats["pending"] == []

    assert job_store.JOBS["q1"]["status"] == "error"
    assert job_store.JOBS["q1"]["error"] == job_store.INTERRUPTED_ERROR
    assert job_store.JOBS["d1"]["status"] == "done"


def test_reload_resumes_transcribe_when_staging_exists(job_store, tmp_path):
    audio = tmp_path / "jobs_staging" / "asr_resume1" / "clip.wav"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"RIFF....WAVEfmt ")
    kwargs = {"model_name": "heavy", "user_email": None, "job_id": "asr_resume1"}
    job_store.set_job(
        "asr_resume1",
        status="running",
        user_email=None,
        resume={
            "job_type": "transcribe",
            "input_paths": [str(audio)],
            "kwargs": kwargs,
        },
    )
    job_store.JOBS.clear()

    stats = job_store.reload_jobs_from_disk()
    assert stats["interrupted"] == 0
    assert len(stats["pending"]) == 1
    assert stats["pending"][0]["job_id"] == "asr_resume1"
    assert job_store.JOBS["asr_resume1"]["status"] == "queued"
    payload = job_store.load_job_payload("asr_resume1")
    assert payload["job_type"] == "transcribe"
    assert payload["input_paths"] == [str(audio)]


def test_stage_job_inputs_moves_into_durable_dir(job_store, tmp_path):
    src_dir = tmp_path / "tmp_upload"
    src_dir.mkdir()
    src = src_dir / "a.wav"
    src.write_bytes(b"audio")
    staged = job_store.stage_job_inputs("asr_stage1", [src], user_email=None)
    assert len(staged) == 1
    assert staged[0].exists()
    assert "jobs_staging" in staged[0].as_posix()
    assert staged[0].name == "a.wav"
    assert not src.exists()


def test_enhance_mode_default_is_off(monkeypatch, tmp_path):
    monkeypatch.delenv("ENHANCE_MODE", raising=False)
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path))
    from app.config import Settings

    s = Settings()
    assert s.ENHANCE_MODE == "off"


def test_enhance_mode_invalid_falls_back_to_off(monkeypatch, tmp_path):
    monkeypatch.setenv("ENHANCE_MODE", "not-a-mode")
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path))
    from app.config import Settings

    s = Settings()
    assert s.ENHANCE_MODE == "off"
