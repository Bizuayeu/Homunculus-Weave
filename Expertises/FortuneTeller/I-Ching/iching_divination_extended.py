#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周易占断システム（拡張版）- I-Ching Divination Engine Extended
変卦システムを含む完全版
"""

import json
import base64
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# 元のIChingDivinationクラスをインポート
from iching_divination import IChingDivination


class IChingDivinationExtended(IChingDivination):
    """周易占断クラス（変卦機能拡張版）"""
    
    def __init__(self, database_path: Optional[str] = None):
        """初期化（親クラスを継承）"""
        super().__init__(database_path)
        
    def find_hexagram_by_binary(self, binary: str) -> Optional[Dict[str, Any]]:
        """
        バイナリ表現から卦データを検索
        
        Args:
            binary: 6桁のバイナリ文字列（例："111111"）
            
        Returns:
            卦データ（見つからない場合はNone）
        """
        for hexagram in self.hexagrams:
            if hexagram['バイナリ'] == binary:
                return hexagram
        return None
    
    def calculate_zongua(self, hexagram_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        綜卦（上下反転）を計算
        
        Args:
            hexagram_data: 本卦のデータ
            
        Returns:
            綜卦のデータ
        """
        binary = hexagram_data['バイナリ']
        zongua_binary = binary[::-1]  # 文字列を反転
        return self.find_hexagram_by_binary(zongua_binary)
    
    def calculate_cuogua(self, hexagram_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        錯卦（陰陽反転）を計算
        
        Args:
            hexagram_data: 本卦のデータ
            
        Returns:
            錯卦のデータ
        """
        binary = hexagram_data['バイナリ']
        # 0と1を反転
        cuogua_binary = ''.join(['0' if b == '1' else '1' for b in binary])
        return self.find_hexagram_by_binary(cuogua_binary)
    
    def calculate_hugua(self, hexagram_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        互卦（内部構造）を計算
        2-4爻を下卦、3-5爻を上卦とする
        
        Args:
            hexagram_data: 本卦のデータ
            
        Returns:
            互卦のデータ
        """
        binary = hexagram_data['バイナリ']
        # 易経は下から数えるので、文字列では逆順
        # 1爻目 = binary[5], 2爻目 = binary[4], ... 6爻目 = binary[0]
        # 2-4爻 = binary[4] + binary[3] + binary[2]（下卦）
        # 3-5爻 = binary[3] + binary[2] + binary[1]（上卦）
        lower_trigram = binary[4] + binary[3] + binary[2]  # 2-4爻
        upper_trigram = binary[3] + binary[2] + binary[1]  # 3-5爻
        hugua_binary = upper_trigram + lower_trigram
        return self.find_hexagram_by_binary(hugua_binary)
    
    def calculate_zhigua(self, hexagram_data: Dict[str, Any], line_number: int) -> Optional[Dict[str, Any]]:
        """
        之卦（動爻による変化）を計算
        
        Args:
            hexagram_data: 本卦のデータ
            line_number: 動爻番号（1-6）
            
        Returns:
            之卦のデータ
        """
        binary = hexagram_data['バイナリ']
        binary_list = list(binary)
        # 易経は下から数えるので、インデックス変換が必要
        # 1爻目 = index[5], 2爻目 = index[4], ... 6爻目 = index[0]
        index = 6 - line_number
        binary_list[index] = '0' if binary_list[index] == '1' else '1'
        zhigua_binary = ''.join(binary_list)
        return self.find_hexagram_by_binary(zhigua_binary)
    
    def divine_with_biangua(self, divination_question: str, context: str = "") -> Dict[str, Any]:
        """
        変卦を含む完全な占断を実行
        
        Args:
            divination_question: 占的（占いたい内容）
            context: 状況整理（背景情報）
            
        Returns:
            本卦、動爻、変卦を含む完全な結果
        """
        # 基本の占断を実行
        basic_result = self.divine(divination_question, context)
        
        # 本卦データを取得
        hexagram_data = self.get_hexagram_data(basic_result['得卦']['番号'])
        line_number = basic_result['得爻']['番号']
        
        # 変卦を計算
        biangua = {
            '綜卦': self.calculate_zongua(hexagram_data),
            '錯卦': self.calculate_cuogua(hexagram_data),
            '互卦': self.calculate_hugua(hexagram_data),
            '之卦': self.calculate_zhigua(hexagram_data, line_number)
        }
        
        # 結果に変卦を追加
        extended_result = basic_result.copy()
        extended_result['変卦'] = {}
        
        for name, gua in biangua.items():
            if gua:
                extended_result['変卦'][name] = {
                    '番号': gua['番号'],
                    '名前': gua['名前'],
                    '読み': gua['読み'],
                    'シンボル': gua['シンボル'],
                    'バイナリ': gua['バイナリ'],
                    '卦辞': gua['卦辞'][:50] + '...' if len(gua['卦辞']) > 50 else gua['卦辞']
                }
            else:
                extended_result['変卦'][name] = None
                
        return extended_result
    
    def format_biangua_result(self, result: Dict[str, Any]) -> str:
        """
        変卦を含む結果を整形して表示
        
        Args:
            result: divine_with_biangua()の結果
            
        Returns:
            整形された文字列
        """
        lines = []
        lines.append("=" * 80)
        lines.append("🔮 周易占断結果（変卦システム完全版）")
        lines.append("=" * 80)
        lines.append("")
        
        # 占機と占的
        lines.append(f"📅 占機：{result['占機']['日時']}")
        lines.append(f"❓ 占的：{result['占的']}")
        lines.append("")
        
        # 本卦
        得卦 = result['得卦']
        lines.append(f"📿 【本卦】 {得卦['番号']}. {得卦['名前']}（{得卦['読み']}）")
        lines.append(f"   記号：{得卦['シンボル']}  バイナリ：{得卦['バイナリ']}")
        lines.append(f"   卦辞：{得卦['卦辞']}")
        lines.append("")
        
        # 動爻
        得爻 = result['得爻']
        lines.append(f"🔥 【動爻】 第{得爻['番号']}爻（{得爻['名前']}）")
        lines.append(f"   爻辞：{得爻['爻辞']}")
        lines.append("")
        
        # 変卦
        if '変卦' in result:
            lines.append("─" * 70)
            lines.append("🌟 【変卦システム】")
            lines.append("")
            
            変卦 = result['変卦']
            
            # 綜卦
            if 変卦.get('綜卦'):
                g = 変卦['綜卦']
                lines.append(f"🔄 綜卦（上下反転）: {g['番号']}. {g['名前']}（{g['読み']}） {g['シンボル']}")
                lines.append(f"   卦辞：{g['卦辞']}")
                lines.append("")
            
            # 錯卦
            if 変卦.get('錯卦'):
                g = 変卦['錯卦']
                lines.append(f"⚡ 錯卦（陰陽反転）: {g['番号']}. {g['名前']}（{g['読み']}） {g['シンボル']}")
                lines.append(f"   卦辞：{g['卦辞']}")
                lines.append("")
            
            # 互卦
            if 変卦.get('互卦'):
                g = 変卦['互卦']
                lines.append(f"🌀 互卦（内部構造）: {g['番号']}. {g['名前']}（{g['読み']}） {g['シンボル']}")
                lines.append(f"   卦辞：{g['卦辞']}")
                lines.append("")
            
            # 之卦
            if 変卦.get('之卦'):
                g = 変卦['之卦']
                lines.append(f"✨ 之卦（変化後）: {g['番号']}. {g['名前']}（{g['読み']}） {g['シンボル']}")
                lines.append(f"   卦辞：{g['卦辞']}")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)


# テスト実行用
if __name__ == "__main__":
    print("=" * 80)
    print("デジタル心易システム（変卦対応完全版）テスト")
    print("=" * 80)
    print()
    
    # システム初期化
    divination = IChingDivinationExtended()
    
    # テスト占断
    test_question = "テスト占断：システムの動作確認"
    test_context = "変卦システムが正しく動作するかのテスト"
    
    # 占断実行
    result = divination.divine_with_biangua(test_question, test_context)
    
    # 結果表示
    formatted = divination.format_biangua_result(result)
    print(formatted)
    
    # JSON出力（デバッグ用）
    print("\n" + "─" * 70)
    print("【JSON出力】")
    print(json.dumps(result, ensure_ascii=False, indent=2))
