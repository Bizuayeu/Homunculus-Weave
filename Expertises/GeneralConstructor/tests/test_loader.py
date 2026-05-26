"""Phase 2: ローダー実装のテスト（TDD Red Phase）"""
import pytest
from pathlib import Path
from pydantic import ValidationError

# テスト対象のインポート（まだ存在しないのでエラーになる）
from python.loader import load_tables, Tables


class TestLoadTables:
    """テーブル読み込みのテスト"""

    @pytest.fixture
    def data_path(self):
        """テストデータのパス"""
        return Path(__file__).parent.parent / "python" / "data"

    def test_load_building_price_table(self, data_path):
        """建築単価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        # 半地下有15件 + 半地下無15件 = 30件
        assert len(tables.建築単価.建築単価テーブル) == 30

    def test_load_foundation_price_table(self, data_path):
        """基礎単価テーブルJSONの読み込み"""
        tables = load_tables(data_path)
        # 5種類の基礎
        assert len(tables.基礎単価) >= 5

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


class TestLoadTablesErrors:
    """エラーハンドリングのテスト"""

    def test_load_missing_directory_raises(self):
        """存在しないディレクトリでエラー"""
        with pytest.raises(FileNotFoundError):
            load_tables(Path("nonexistent_directory"))

    def test_tables_is_dataclass_like(self):
        """TablesはDataclass的にアクセス可能"""
        data_path = Path(__file__).parent.parent / "python" / "data"
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
