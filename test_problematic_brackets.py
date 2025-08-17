#!/usr/bin/env python3
"""测试不完整括号的文件名"""
import re
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from samea.__main__ import extract_artist_info, find_balanced_brackets

def test_problematic_filenames():
    """测试有问题的文件名"""
    
    test_files = [
        "(C105) (コミック エグゼ 51) 異世界来たのでスケベスキルで全力謳歌しようと思う 14 射目 [g [DL 版] [あきのそら] [中国翻訳].zip",
        "(C105) PURUPURU NYURUN [死想恋歌个人汉化 [DL 版] [勝利の女神：NIKKE] [AERODOG (inu)] [中国翻訳].zip",
        "(C105) TS 魔法少女シュヴァリアちゃんとその仲間はメスに堕とされてもう男に戻れないってマジですか！_ [I'mmoralist ( [DL 版].zip",
        "(C105) ヒナちゃんとイチャイチャする本 2 [牛 [DL 版] [ブルーアーカイブ] [remora field (remora)] [中国翻訳].zip",
        "(C105) 真夏の夜の夢 [無邪 [DL 版] [アイドルマスター シャイニーカラーズ] [OrangeMaru (YD)] [中国翻訳] [無修正].zip",
        "(COMIC LO 2025 年 2 月号) (C105) これはお手伝いなので [DL 版] [甘露アメ] [中国翻訳] [吗喽汉化组].zip",
        "(COMIC 快楽天 2025 年 1 月号) いいからヤリたい！ [DL 版] [鳥茶丸] [中国翻訳] [大鸟可不敢乱转汉化].zip",
        "あいぞめ [DL 版] [あきのそら] [中国翻訳] [無修正].zip",
        "はーとまーくもっと多め。 [DL 版] [宮元一佐] [中国翻訳].zip",
        "独身ハンターの出逢いはエルフの森で♡ 第 6 話 [DL 版] [kakao] [中国翻訳] [无毒汉化组].zip"
    ]
    
    print("=== 测试不完整方括号的文件名 ===")
    for i, filename in enumerate(test_files, 1):
        print(f"\n📁 测试文件 {i}:")
        print(f"   文件名: {filename}")
        
        # 测试配对方括号查找
        brackets = find_balanced_brackets(filename)
        bracket_contents = [content for _, _, content in brackets]
        print(f"   配对方括号: {bracket_contents}")
        
        # 测试画师信息提取
        artist_infos = extract_artist_info(filename)
        print(f"   提取结果: {artist_infos}")
        
        if artist_infos:
            group, artist = artist_infos[0]  # 取第一个结果
            key = f"{group}_{artist}" if group else artist
            print(f"   生成的 key: '{key}'")
            
            # 模拟文件夹命名逻辑
            group_split, artist_split = key.split('_') if '_' in key else ('', key)
            folder_name = f"[{group_split} ({artist_split})]" if group_split else f"[{artist_split}]"
            print(f"   文件夹名称: '{folder_name}'")
            
            if "DL 版" in folder_name or "DL版" in folder_name:
                print(f"   ❌ 仍然包含 'DL 版'！")
            else:
                print(f"   ✅ 已正确过滤 'DL 版'")

if __name__ == "__main__":
    test_problematic_filenames()
