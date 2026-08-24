"""Phase 2 / Stage 3: ローダーのテスト

v2 で読むのは新テーブル群と温存テーブルのみ。退役 4 本
（施工条件・建物形状・山留工法・山留単価）は読まない。
"""
import json
import shutil
import pytest
from pathlib import Path

from python.loader import load_tables, Tables


@pytest.fixture
def data_path():
    """単価テーブル・判定ロジックJSONの所在"""
    return Path(__file__).parent.parent / "python" / "data"


def _read(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestLoadTables:
    """テーブル読み込みのテスト"""

    def test_load_foundation_price_table(self, data_path):
        """基礎単価テーブルJSONの読み込み（杭 3 行へ縮小済み）"""
        tables = load_tables(data_path)
        assert [e.基礎種別 for e in tables.基礎単価] == [
            "20m杭基礎",
            "30m杭基礎",
            "40m杭基礎",
        ]

    def test_load_demolition_price_table(self, data_path):
        """解体単価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        # 5種類の古家構造
        assert len(tables.解体単価) >= 5

    def test_load_rental_price_table(self, data_path):
        """貸床単価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        # 東京23区の区が存在
        assert len(tables.貸床単価) > 0
        # 目黒区のデータが存在するか確認
        meguro = [e for e in tables.貸床単価 if e.土地所在 == "目黒区"]
        assert len(meguro) > 0

    def test_load_ground_evaluation_table(self, data_path):
        """地盤評価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.地盤評価) > 0

    def test_load_foundation_type_table(self, data_path):
        """基礎種別テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.基礎種別) > 0

    def test_loader_v2_tables_and_freshness(self, data_path):
        """v2 の単価モデル 4 テーブルと、その鮮度タグ

        鮮度は JSON の属性であって Tables の属性ではないため、
        metadata はファイルを直接読んで検査する（Tables には持たせない）。
        """
        tables = load_tables(data_path)
        assert len(tables.建築単価帯域) == 12
        assert [e.区分 for e in tables.単価オフセット.道路区分] == [
            "2.5m以下",
            "2.5〜8m",
            "幹線・バス通り",
        ]
        assert [e.区分 for e in tables.単価オフセット.基礎形状] == ["べた", "杭"]
        assert [e.区分 for e in tables.単価オフセット.種別] == ["共同住宅", "長屋"]
        assert len(tables.オプション単価) > 0
        assert {"建設経費率", "基準戸数", "標準住戸面積"} <= set(tables.定数)
        # 単価表が税込につき ×1.1 をしない（2026-08-24 裁定）。消費税率は退役した
        assert "消費税率" not in tables.定数

        for name in ("建築単価帯域", "単価オフセット", "オプション単価", "定数"):
            assert _read(data_path / f"{name}.json")["metadata"]["as_of"] == "2026-08-04"

        # 長屋は Excel に 400〜500 帯しか無く、他帯は共同 +2 で導出した
        長屋 = [e for e in tables.単価オフセット.種別 if e.区分 == "長屋"][0]
        assert 長屋.derived is True

    def test_retired_tables_are_not_loaded(self, data_path):
        """退役 4 本は Tables に存在しない（読み込みも参照もしない）"""
        tables = load_tables(data_path)
        for 属性 in ("施工条件", "建物形状", "山留単価", "山留工法", "建築単価"):
            assert not hasattr(tables, 属性)


class TestLoadTablesErrors:
    """エラーハンドリングのテスト"""

    def test_load_missing_directory_raises(self):
        """存在しないディレクトリでエラー"""
        with pytest.raises(FileNotFoundError):
            load_tables(Path("nonexistent_directory"))

    def test_empty_directory_raises(self, tmp_path):
        """テーブルが1つも無いディレクトリでエラー

        空テーブルのまま計算を続行すると、エラー無しに過少な単価で
        採算判断が出てしまう（静かな失敗）。読み込み時点で落とす。
        """
        with pytest.raises(FileNotFoundError):
            load_tables(tmp_path)

    def test_partially_missing_table_raises(self, tmp_path, data_path):
        """必須テーブルが1つでも欠けていればエラー"""
        for src in data_path.glob("*.json"):
            if src.name != "建築単価帯域.json":
                shutil.copy(src, tmp_path / src.name)

        with pytest.raises(FileNotFoundError):
            load_tables(tmp_path)

    def test_missing_table_error_names_the_file(self, tmp_path, data_path):
        """エラーメッセージに欠落したファイル名が含まれる"""
        for src in data_path.glob("*.json"):
            if src.name != "建築単価帯域.json":
                shutil.copy(src, tmp_path / src.name)

        with pytest.raises(FileNotFoundError, match="建築単価帯域.json"):
            load_tables(tmp_path)

    def test_tables_is_dataclass_like(self, data_path):
        """TablesはDataclass的にアクセス可能"""
        tables = load_tables(data_path)

        # 属性アクセスが可能
        assert hasattr(tables, "基礎単価")
        assert hasattr(tables, "解体単価")
        assert hasattr(tables, "貸床単価")
        assert hasattr(tables, "地盤評価")
        assert hasattr(tables, "基礎種別")
        assert hasattr(tables, "建築単価帯域")
        assert hasattr(tables, "単価オフセット")
        assert hasattr(tables, "オプション単価")
        assert hasattr(tables, "定数")
