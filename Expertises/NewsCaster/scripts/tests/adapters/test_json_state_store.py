from __future__ import annotations

import json
from datetime import date, timedelta

from adapters.state.json_state_store import JsonStateStore


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


# RETENTION_DAYS=90 の剪定に掛からない日付（新しい順）
TODAY = _days_ago(0)
D1 = _days_ago(1)
D2 = _days_ago(2)
D3 = _days_ago(3)
# 90 日を超えて剪定される日付
STALE = _days_ago(91)


def test_initially_not_sent(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    assert store.is_sent(D1) is False


def test_mark_sent_then_is_sent_true(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent(D1)
    assert store.is_sent(D1) is True


def test_mark_sent_persists_to_disk(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent(D1)

    # 別インスタンスで読み直しても通る
    store2 = JsonStateStore(state_dir=tmp_path)
    assert store2.is_sent(D1) is True


def test_multiple_dates_persisted(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent(D3)
    store.mark_sent(D2)
    store.mark_sent(D1)
    assert store.is_sent(D3) is True
    assert store.is_sent(D2) is True
    assert store.is_sent(D1) is True
    assert store.is_sent(TODAY) is False


def test_creates_state_dir_if_missing(tmp_path):
    nested = tmp_path / "nested" / "state"
    store = JsonStateStore(state_dir=nested)
    store.mark_sent(D1)
    assert (nested / "sent_dates.json").exists()


def test_corrupt_file_falls_back_to_empty(tmp_path):
    state_file = tmp_path / "sent_dates.json"
    state_file.write_text("not valid json {{{", encoding="utf-8")

    store = JsonStateStore(state_dir=tmp_path)
    # 壊れたファイルでも is_sent は False を返す
    assert store.is_sent(D1) is False

    # mark_sent も問題なく書ける
    store.mark_sent(D1)
    assert store.is_sent(D1) is True


def test_idempotent_mark_sent(tmp_path):
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent(D1)
    store.mark_sent(D1)
    # ファイル内に重複が無い
    data = json.loads((tmp_path / "sent_dates.json").read_text(encoding="utf-8"))
    assert data["sent"].count(D1) == 1


def test_prunes_entries_older_than_90_days(tmp_path):
    state_file = tmp_path / "sent_dates.json"
    # 古い日付を含む状態で書く
    state_file.write_text(
        json.dumps({"sent": [STALE, D2, D1]}, ensure_ascii=False),
        encoding="utf-8",
    )
    store = JsonStateStore(state_dir=tmp_path)
    store.mark_sent(TODAY)  # mark するタイミングで prune が走る

    data = json.loads((tmp_path / "sent_dates.json").read_text(encoding="utf-8"))
    assert STALE not in data["sent"]
    assert TODAY in data["sent"]
