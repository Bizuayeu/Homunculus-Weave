from __future__ import annotations

import json

from adapters.state.json_state_store import JsonStateStore


def test_initially_not_sent(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    assert store.is_sent("2026-05-11") is False


def test_mark_sent_then_is_sent_true(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent("2026-05-11")
    assert store.is_sent("2026-05-11") is True


def test_mark_sent_persists_to_disk(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent("2026-05-11")

    # 別インスタンスで読み直しても通る
    store2 = JsonStateStore(state_dir=tmp_path)
    assert store2.is_sent("2026-05-11") is True


def test_multiple_dates_persisted(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent("2026-05-10")
    store.mark_sent("2026-05-11")
    store.mark_sent("2026-05-12")
    assert store.is_sent("2026-05-10") is True
    assert store.is_sent("2026-05-11") is True
    assert store.is_sent("2026-05-12") is True
    assert store.is_sent("2026-05-13") is False


def test_creates_state_dir_if_missing(tmp_path):
    nested = tmp_path / "nested" / "state"
    store = JsonStateStore(state_dir=nested)
    store.mark_sent("2026-05-11")
    assert (nested / "sent_dates.json").exists()


def test_corrupt_file_falls_back_to_empty(tmp_path):
    state_file = tmp_path / "sent_dates.json"
    state_file.write_text("not valid json {{{", encoding="utf-8")

    store = JsonStateStore(state_dir=tmp_path)
    # 壊れたファイルでも is_sent は False を返す
    assert store.is_sent("2026-05-11") is False

    # mark_sent も問題なく書ける
    store.mark_sent("2026-05-11")
    assert store.is_sent("2026-05-11") is True


def test_idempotent_mark_sent(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent("2026-05-11")
    store.mark_sent("2026-05-11")
    # ファイル内に重複が無い
    data = json.loads((tmp_path / "sent_dates.json").read_text(encoding="utf-8"))
    assert data["sent"].count("2026-05-11") == 1


def test_prunes_entries_older_than_90_days(tmp_path):
    state_file = tmp_path / "sent_dates.json"
    # 古い日付を含む状態で書く
    state_file.write_text(
        json.dumps(
            {"sent": ["2020-01-01", "2026-05-10", "2026-05-11"]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent("2026-05-12")  # mark するタイミングで prune が走る

    data = json.loads((tmp_path / "sent_dates.json").read_text(encoding="utf-8"))
    assert "2020-01-01" not in data["sent"]
    assert "2026-05-12" in data["sent"]
