#!/usr/bin/env python3
"""测试画师文件夹命名问题"""
import re
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from samea.__main__ import extract_artist_info

def test_folder_naming():
    """测试具体的文件夹命名问题"""
    
    test_files = [
        "[DL 版] [カームホワイト (真白しらこ)] アイドルマスター シャイニーカラーズ.zip",
        "[DL版][カームホワイト (真白しらこ)] 別の作品.zip",
        "[汉化組] [カームホワイト (真白しらこ)] 第三个作品.zip"
    ]
    
    print("=== 测试画师信息提取 ===")
    for i, filename in enumerate(test_files, 1):
        print(f"\n📁 测试文件 {i}: {filename}")
        artist_infos = extract_artist_info(filename)
        print(f"   提取结果: {artist_infos}")
        
        # 模拟 find_common_artists 的 key 构造逻辑
        for group, artist in artist_infos:
            key = f"{group}_{artist}" if group else artist
            print(f"   生成的 key: '{key}'")
            
            # 模拟文件夹命名逻辑
            group_split, artist_split = key.split('_') if '_' in key else ('', key)
            folder_name = f"[{group_split} ({artist_split})]" if group_split else f"[{artist_split}]"
            print(f"   文件夹名称: '{folder_name}'")

if __name__ == "__main__":
    test_folder_naming()
