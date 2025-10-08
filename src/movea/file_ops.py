"""文件操作模块"""
import streamlit as st
import os
import shutil
from pathlib import Path

# 支持的压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}

def is_archive(file_path):
    """检查文件是否是压缩包"""
    return Path(file_path).suffix.lower() in ARCHIVE_EXTENSIONS

def execute_single_folder(level1_name, data, archives_plan):
    """执行单个文件夹的移动"""
    if not archives_plan:
        st.warning(f"{level1_name} 没有移动计划")
        return

    level1_path = data['path']
    success_count = 0
    error_count = 0

    with st.spinner(f"正在移动 {level1_name} 的对象..."):
        for item_key, target_folder in archives_plan.items():
            if target_folder is None:
                continue  # 不移动

            # 检查是文件还是文件夹
            if item_key.startswith("folder_"):
                item_name = item_key[7:]  # 移除"folder_"前缀
                item_type = "文件夹"
            else:
                item_name = item_key
                item_type = "文件"

            source_path = os.path.join(level1_path, item_name)
            target_path = os.path.join(level1_path, target_folder, item_name)

            try:
                # 确保目标文件夹存在
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                # 移动文件或文件夹
                shutil.move(source_path, target_path)
                st.success(f"✅ {level1_name}/{item_name} ({item_type}) -> {target_folder}")
                success_count += 1
            except Exception as e:
                st.error(f"❌ 移动失败 {level1_name}/{item_name} ({item_type}): {e}")
                error_count += 1

    if success_count > 0 or error_count > 0:
        st.info(f"{level1_name} 移动完成! 成功: {success_count}, 失败: {error_count}")

    # 移动完成后，更新移动计划，移除已完成的文件夹
    if level1_name in st.session_state.move_plan:
        del st.session_state.move_plan[level1_name]

def execute_all_moves():
    """执行所有文件夹的移动"""
    if 'move_plan' not in st.session_state or not st.session_state.move_plan:
        st.warning("没有移动计划")
        return

    scan_results = st.session_state.scan_results
    total_success = 0
    total_error = 0

    with st.spinner("正在执行所有移动..."):
        for level1_name, archives_plan in st.session_state.move_plan.items():
            if level1_name in scan_results:
                data = scan_results[level1_name]
                success_count = 0
                error_count = 0

                for item_key, target_folder in archives_plan.items():
                    if target_folder is None:
                        continue

                    # 检查是文件还是文件夹
                    if item_key.startswith("folder_"):
                        item_name = item_key[7:]  # 移除"folder_"前缀
                        item_type = "文件夹"
                    else:
                        item_name = item_key
                        item_type = "文件"

                    source_path = os.path.join(data['path'], item_name)
                    target_path = os.path.join(data['path'], target_folder, item_name)

                    try:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.move(source_path, target_path)
                        success_count += 1
                    except Exception as e:
                        st.error(f"❌ 移动失败 {level1_name}/{item_name} ({item_type}): {e}")
                        error_count += 1

                if success_count > 0:
                    st.success(f"✅ {level1_name}: {success_count} 个对象移动成功")
                if error_count > 0:
                    st.error(f"❌ {level1_name}: {error_count} 个对象移动失败")

                total_success += success_count
                total_error += error_count

    st.info(f"全部移动完成! 总成功: {total_success}, 总失败: {total_error}")
    # 清空移动计划
    st.session_state.move_plan = {}

    # 重新扫描目录以更新显示
    if 'root_path' in st.session_state:
        from .scanner import scan_directory
        with st.spinner("正在重新扫描目录..."):
            updated_scan_results = scan_directory(st.session_state.root_path)
            st.session_state.scan_results = updated_scan_results
        st.success("重新扫描完成！")

def execute_current_page_moves():
    """执行当前页面的移动"""
    if 'move_plan' not in st.session_state or not st.session_state.move_plan:
        st.warning("没有移动计划")
        return

    scan_results = st.session_state.scan_results
    items_per_page = st.session_state.get('items_per_page', 5)
    current_page = st.session_state.get('current_page', 0)

    level1_names = list(scan_results.keys())
    start_idx = current_page * items_per_page
    end_idx = min(start_idx + items_per_page, len(level1_names))
    current_level1_names = level1_names[start_idx:end_idx]

    total_success = 0
    total_error = 0

    with st.spinner("正在执行当前页面移动..."):
        for level1_name in current_level1_names:
            if level1_name in st.session_state.move_plan:
                archives_plan = st.session_state.move_plan[level1_name]
                data = scan_results[level1_name]
                success_count = 0
                error_count = 0

                for item_key, target_folder in archives_plan.items():
                    if target_folder is None:
                        continue

                    # 检查是文件还是文件夹
                    if item_key.startswith("folder_"):
                        item_name = item_key[7:]  # 移除"folder_"前缀
                        item_type = "文件夹"
                    else:
                        item_name = item_key
                        item_type = "文件"

                    source_path = os.path.join(data['path'], item_name)
                    target_path = os.path.join(data['path'], target_folder, item_name)

                    try:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.move(source_path, target_path)
                        success_count += 1
                    except Exception as e:
                        st.error(f"❌ 移动失败 {level1_name}/{item_name} ({item_type}): {e}")
                        error_count += 1

                if success_count > 0:
                    st.success(f"✅ {level1_name}: {success_count} 个对象移动成功")
                if error_count > 0:
                    st.error(f"❌ {level1_name}: {error_count} 个对象移动失败")

                total_success += success_count
                total_error += error_count

                # 移除已完成的文件夹
                del st.session_state.move_plan[level1_name]

    st.info(f"当前页面移动完成! 总成功: {total_success}, 总失败: {total_error}")

    # 重新扫描目录以更新显示
    if 'root_path' in st.session_state:
        from .scanner import scan_directory
        with st.spinner("正在重新扫描目录..."):
            updated_scan_results = scan_directory(st.session_state.root_path)
            st.session_state.scan_results = updated_scan_results
            # 清空移动计划，因为文件位置已改变
            st.session_state.move_plan = {}
        st.success("重新扫描完成！")

def create_folders_for_level1(level1_name, data, templates):
    """为指定的一级文件夹创建子文件夹"""
    level1_path = data['path']
    created_count = 0
    skipped_count = 0

    for template in templates:
        folder_path = os.path.join(level1_path, template)
        try:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
                created_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            st.error(f"创建文件夹失败 {level1_name}/{template}: {e}")

    if created_count > 0:
        st.success(f"✅ {level1_name}: 成功创建 {created_count} 个文件夹")
    if skipped_count > 0:
        st.info(f"⏭️ {level1_name}: 跳过 {skipped_count} 个已存在的文件夹")

    # 重新扫描目录以更新显示
    if 'root_path' in st.session_state:
        from .scanner import scan_directory
        with st.spinner("正在重新扫描目录..."):
            updated_scan_results = scan_directory(st.session_state.root_path)
            st.session_state.scan_results = updated_scan_results
            # 清空移动计划，因为文件夹结构已改变
            st.session_state.move_plan = {}
        st.success("重新扫描完成！")

def create_folders_for_all(templates):
    """为所有一级文件夹创建指定的子文件夹"""
    if 'scan_results' not in st.session_state:
        st.error("没有扫描结果")
        return

    scan_results = st.session_state.scan_results
    total_created = 0
    total_skipped = 0

    with st.spinner("正在创建文件夹..."):
        for level1_name, data in scan_results.items():
            level1_path = data['path']
            for template in templates:
                folder_path = os.path.join(level1_path, template)
                try:
                    if not os.path.exists(folder_path):
                        os.makedirs(folder_path, exist_ok=True)
                        total_created += 1
                    else:
                        total_skipped += 1
                except Exception as e:
                    st.error(f"创建文件夹失败 {level1_name}/{template}: {e}")

    if total_created > 0:
        st.success(f"成功创建 {total_created} 个文件夹")
    if total_skipped > 0:
        st.info(f"跳过 {total_skipped} 个已存在的文件夹")

    # 重新扫描目录以更新显示
    if 'root_path' in st.session_state:
        from .scanner import scan_directory
        with st.spinner("正在重新扫描目录..."):
            updated_scan_results = scan_directory(st.session_state.root_path)
            st.session_state.scan_results = updated_scan_results
            # 清空移动计划，因为文件夹结构已改变
            st.session_state.move_plan = {}
        st.success("重新扫描完成！")