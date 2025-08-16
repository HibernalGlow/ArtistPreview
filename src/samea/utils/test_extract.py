#!/usr/bin/env python3
"""测试画师信息提取功能"""

import sys
sys.path.append('src')

from samea.__main__ import extract_artist_info, logger

# 测试用例
test_cases = [
    "[DL 版] [カームホワイト (真白しらこ)]",
    "[汉化组] [画师名]", 
    "[正常社团 (画师名)]",
    "[画师A][画师B]",
    "[DL版][画师名]",
    "[trash] [好画师]",
    "[社团名] [画师 (真名)]",
    "[123] [画师名]",
    "[画师名]",
    "[v1] [画师名]",
    # 新增边缘测试用例
    "[DL版] [汉化组] [真正的画师]",
    "[画师 (真名)] [其他信息]",
    "[社团A (画师A)] [社团B (画师B)]",
    "[R18] [adult] [正常画师名]",
    "[pixiv] [twitter] [gumroad] [画师名]",
    "[已找到] [trash] [unknown] [好画师]",
    "普通文件名 [画师名] 没有其他方括号",
    "[空   格  多的   (画师名)]",
]

print("🧪 测试画师信息提取功能")
print("=" * 50)

for i, test_case in enumerate(test_cases, 1):
    print(f"\n测试 {i}: {test_case}")
    result = extract_artist_info(test_case)
    if result:
        for group, artist in result:
            if group:
                print(f"  ✅ 找到: 社团=[{group}], 画师=[{artist}]")
            else:
                print(f"  ✅ 找到: 画师=[{artist}]")
    else:
        print("  ❌ 未找到画师信息")
