#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
デジタル心易システム統合テスト
実際の使用例と返り値構造の検証
"""

import sys
from pathlib import Path

# モジュールのインポート
sys.path.append(str(Path(__file__).parent))
from iching_divination import IChingDivination


def test_basic_divination():
    """基本的な占断のテスト"""
    print("=" * 60)
    print("テスト1: 基本的な占断")
    print("=" * 60)

    # システムの初期化
    divination = IChingDivination()

    # 占断の実行
    占的 = "新しいプロジェクトを始めるべきか"
    result = divination.divine(占的)

    # 返り値の構造を検証
    assert '占機' in result
    assert '日時' in result['占機']
    assert 'タイムスタンプ' in result['占機']

    assert '占的' in result
    assert result['占的'] == 占的

    assert '状況整理' in result

    assert '得卦' in result
    assert '番号' in result['得卦']
    assert 1 <= result['得卦']['番号'] <= 64
    assert '名前' in result['得卦']
    assert '読み' in result['得卦']
    assert 'シンボル' in result['得卦']
    assert 'バイナリ' in result['得卦']
    assert '卦辞' in result['得卦']
    assert '上卦' in result['得卦']
    assert '下卦' in result['得卦']

    assert '変爻' in result
    assert '番号' in result['変爻']
    assert 1 <= result['変爻']['番号'] <= 6
    assert '名前' in result['変爻']
    assert '陰陽' in result['変爻']
    assert '爻辞' in result['変爻']

    print("[OK] 返り値の構造が正しいことを確認")
    print(f"得卦: {result['得卦']['番号']}番 {result['得卦']['名前']}")
    print(f"変爻: 第{result['変爻']['番号']}爻 {result['変爻']['名前']}")


def test_with_context():
    """状況整理を含む占断のテスト"""
    print("\n" + "=" * 60)
    print("テスト2: 状況整理を含む占断")
    print("=" * 60)

    divination = IChingDivination()

    占的 = "転職すべきか"
    状況 = """
    現職：IT企業で5年勤務、年収600万円
    オファー：スタートアップからCTO候補として声がかかった
    懸念：給与は下がるが株式オプションあり
    """

    result = divination.divine(占的, 状況)

    assert result['状況整理'] == 状況
    print("[OK] 状況整理が正しく記録されることを確認")
    print(f"占的: {result['占的']}")
    print(f"得卦: {result['得卦']['番号']}番 {result['得卦']['名前']}")


def test_deterministic():
    """決定論的であることのテスト"""
    print("\n" + "=" * 60)
    print("テスト3: 決定論的動作の検証")
    print("=" * 60)

    divination = IChingDivination()

    占的 = "同じ質問"
    状況 = "同じ状況"

    # 同じ入力で3回実行
    results = []
    for i in range(3):
        result = divination.divine(占的, 状況)
        results.append(result['得卦']['番号'])

    # すべて同じ卦番号になることを確認
    assert len(set(results)) == 1, "同じ入力で異なる結果が出ました"
    print(f"[OK] 同じ入力で常に同じ卦（{results[0]}番）が出ることを確認")


def display_template_usage():
    """テンプレートの使用例"""
    print("\n" + "=" * 60)
    print("テンプレート使用例")
    print("=" * 60)

    divination = IChingDivination()
    result = divination.divine("テンプレートテスト用の占的")

    # 基本的なデータアクセスの確認
    print(f"占機: {result['占機']['日時']}")
    print(f"占的: {result['占的']}")
    print(f"得卦番号: {result['得卦']['番号']}")
    print(f"得卦名前: {result['得卦']['名前']}")
    print(f"変爻番号: {result['変爻']['番号']}")
    print(f"変爻名前: {result['変爻']['名前']}")
    print("[OK] テンプレート用データアクセスが正常")


def main():
    """すべてのテストを実行"""
    try:
        test_basic_divination()
        test_with_context()
        test_deterministic()
        display_template_usage()

        print("\n" + "=" * 60)
        print("SUCCESS: すべてのテストが成功しました！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[ERROR] テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] エラー発生: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()