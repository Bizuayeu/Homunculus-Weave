"""Phase 2: ローダー実装のテスト（TDD Red Phase）"""
import shutil
import pytest
from pathlib import Path
from pydantic import ValidationError

# テスト対象のインポート（まだ存在しないのでエラーになる）
from python.loader import load_tables, Tables


@pytest.fixture
def data_path():
    """単価テーブル・判定ロジックJSONの所在"""
    return Path(__file__).parent.parent / "python" / "data"


class TestLoadTables:
    """テーブル読み込みのテスト"""

    def test_load_building_price_table(self, data_path):
        """建築単価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        # 半地下有15件 + 半地下無15件 = 30件
        assert len(tables.建築単価.建築単価テーブル) == 30

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

    def test_load_construction_condition_table(self, data_path):
        """施工条件テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.施工条件) > 0

    def test_load_building_shape_table(self, data_path):
        """建物形状テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.建物形状) > 0

    def test_load_ground_evaluation_table(self, data_path):
        """地盤評価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.地盤評価) > 0

    def test_load_foundation_type_table(self, data_path):
        """基礎種別テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.基礎種別) > 0

    def test_load_retaining_wall_table(self, data_path):
        """山留単価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.山留単価) > 0

    def test_load_retaining_method_table(self, data_path):
        """山留工法テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        assert len(tables.山留工法) > 0

    def test_load_v2_unit_price_tables(self, data_path):
        """v2 の単価モデル 4 テーブルを読み込む（鮮度検査は Stage 3b）"""
        tables = load_tables(data_path)
        assert len(tables.建築単価帯域) == 12
        assert [e.区分 for e in tables.単価オフセット.基礎形状] == ["べた", "杭"]
        assert [e.区分 for e in tables.単価オフセット.種別] == ["共同住宅", "長屋"]
        assert len(tables.単価オフセット.道路区分) == 3
        assert len(tables.オプション単価) > 0
        assert {"建設経費率", "消費税率", "基準戸数"} <= set(tables.定数)


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
            if src.name != "建築単価テーブル.json":
                shutil.copy(src, tmp_path / src.name)

        with pytest.raises(FileNotFoundError):
            load_tables(tmp_path)

    def test_missing_table_error_names_the_file(self, tmp_path):
        """エラーメッセージに欠落したファイル名が含まれる"""
        with pytest.raises(FileNotFoundError, match="建築単価テーブル.json"):
            load_tables(tmp_path)

    def test_tables_is_dataclass_like(self, data_path):
        """TablesはDataclass的にアクセス可能"""
        tables = load_tables(data_path)

        # 属性アクセスが可能
        assert hasattr(tables, "建築単価")
        assert hasattr(tables, "基礎単価")
        assert hasattr(tables, "解体単価")
        assert hasattr(tables, "貸床単価")
        assert hasattr(tables, "施工条件")
        assert hasattr(tables, "建物形状")
        assert hasattr(tables, "地盤評価")
        assert hasattr(tables, "基礎種別")
        assert hasattr(tables, "山留単価")
        assert hasattr(tables, "山留工法")
        assert hasattr(tables, "建築単価帯域")
        assert hasattr(tables, "単価オフセット")
        assert hasattr(tables, "オプション単価")
        assert hasattr(tables, "定数")
