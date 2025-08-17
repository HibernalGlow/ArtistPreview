#!/usr/bin/env python3
"""测试实际的问题文件名"""
import re
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from samea.__main__ import extract_artist_info, is_artist_name_blacklisted

def test_real_problem():
    """测试实际遇到的问题文件名"""
    
    test_files = [
        "[DL 版] [アイドルマスター シャイニーカラーズ] 某个作品.zip",
        "[DL 版] [あきのそら] 某个作品.zip", 
        "[DL 版] [ブルーアーカイブ] 某个作品.zip",
        "[DL 版] [甘露アメ] 某个作品.zip",
        "[DL 版] [宮元一佐] 某个作品.zip",
        "[DL 版] [鳥茶丸] 某个作品.zip",
        "[DL 版] [勝利の女神：NIKKE] 某个作品.zip"
    ]
    
    print("=== 测试黑名单过滤 ===")
    print(f"'DL 版' 是否在黑名单: {is_artist_name_blacklisted('DL 版')}")
    print(f"'DL版' 是否在黑名单: {is_artist_name_blacklisted('DL版')}")
    
    print("\n=== 测试实际问题文件名 ===")
    for i, filename in enumerate(test_files, 1):
        print(f"\n📁 测试文件 {i}: {filename}")
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
            
            if "DL 版" in folder_name:
                print(f"   ❌ 仍然包含 'DL 版'！")
            else:
                print(f"   ✅ 已正确过滤 'DL 版'")

if __name__ == "__main__":
    test_real_problem()
