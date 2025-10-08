import streamlit as st
import os
import shutil
import re
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib

import tomli_w

# 支持的压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "config.toml"

def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'rb') as f:
                return tomllib.load(f)
        except Exception as e:
            st.error(f"加载配置文件失败: {e}")
    return {
        'matching': {'priority_keywords': []},
        'blacklist': {'folders': []}
    }

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'wb') as f:
            tomli_w.dump(config, f)
        return True
    except Exception as e:
        st.error(f"保存配置文件失败: {e}")
        return False

def load_blacklist():
    """加载黑名单"""
    config = load_config()
    return set(config.get('blacklist', {}).get('folders', []))

def save_blacklist(blacklist):
    """保存黑名单"""
    config = load_config()
    config['blacklist'] = {'folders': list(blacklist)}
    return save_config(config)

def add_to_blacklist(folder_name):
    """添加文件夹到黑名单"""
    blacklist = load_blacklist()
    if folder_name not in blacklist:
        blacklist.add(folder_name)
        if save_blacklist(blacklist):
            st.success(f"已将 '{folder_name}' 添加到黑名单")
            return True
    else:
        st.warning(f"'{folder_name}' 已在黑名单中")
    return False

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
        with st.spinner("正在重新扫描目录..."):
            updated_scan_results = scan_directory(st.session_state.root_path)
            st.session_state.scan_results = updated_scan_results
            # 清空移动计划，因为文件夹结构已改变
            st.session_state.move_plan = {}
        st.success("重新扫描完成！")

def is_archive(file_path):
    """检查文件是否是压缩包"""
    return Path(file_path).suffix.lower() in ARCHIVE_EXTENSIONS

def scan_directory(root_path):
    """扫描根路径下的每个一级文件夹"""
    if not os.path.exists(root_path):
        st.error(f"路径不存在: {root_path}")
        return {}
    
    # 加载黑名单
    blacklist = load_blacklist()
    
    results = {}
    try:
        # 获取一级文件夹
        for item in os.listdir(root_path):
            level1_path = os.path.join(root_path, item)
            if os.path.isdir(level1_path):
                # 跳过黑名单中的文件夹
                if item in blacklist:
                    continue
                    
                # 获取二级文件夹、压缩包和可移动文件夹
                subfolders = []
                archives = []
                movable_folders = []
                for subitem in os.listdir(level1_path):
                    subitem_path = os.path.join(level1_path, subitem)
                    if os.path.isdir(subitem_path):
                        subfolders.append(subitem)
                    elif os.path.isfile(subitem_path) and is_archive(subitem_path):
                        archives.append(subitem)
                
                # 可移动的文件夹：一级文件夹下的文件夹，但排除已存在的二级文件夹
                # 实际上，当前所有文件夹都在subfolders中，我们需要区分哪些是真正的二级文件夹，哪些是可移动的文件夹
                # 暂时先收集所有非二级文件夹的文件夹作为可移动对象
                # 这里先简化：如果有二级文件夹，则可移动文件夹就是除了二级文件夹外的其他文件夹
                # 但实际上，现在所有文件夹都被当作二级文件夹了
                
                # 为了简化，我们添加一个逻辑：文件夹如果不匹配任何模式，就认为是可移动的
                # 或者，我们可以修改逻辑，让用户指定哪些是真正的分类文件夹
                
                # 暂时先添加一个简单的逻辑：如果文件夹名不包含数字前缀，就认为是可移动的文件夹
                movable_folders = []
                for folder in subfolders[:]:  # 复制一份
                    if not re.match(r'^\d+[\.\)\]\s]*', folder):  # 如果不是以数字开头的
                        movable_folders.append(folder)
                        subfolders.remove(folder)  # 从二级文件夹中移除
                
                if (archives or movable_folders) and subfolders:  # 有可移动对象且有目标文件夹
                    results[item] = {
                        'path': level1_path,
                        'subfolders': sorted(subfolders),  # 排序二级文件夹
                        'archives': archives,
                        'movable_folders': movable_folders
                    }
    except Exception as e:
        st.error(f"扫描目录时出错: {e}")
    
    return results

def match_archive_to_folder(archive_name, subfolders, regex_patterns, allow_move_to_unnumbered=False):
    """使用正则匹配压缩包到二级文件夹，优先选择包含关键词的文件夹"""
    config = load_config()
    priority_keywords = config.get('matching', {}).get('priority_keywords', [])
    
    # 先找到所有正则匹配的文件夹
    matched_folders = []
    for folder in subfolders:
        for pattern in regex_patterns:
            try:
                if re.search(pattern, archive_name, re.IGNORECASE):
                    matched_folders.append(folder)
                    break  # 找到匹配就停止
            except re.error:
                continue  # 忽略无效的正则表达式
    
    # 如果允许移动到无编号文件夹，添加没有编号的文件夹（但排除自身）
    if allow_move_to_unnumbered:
        # 定义编号模式
        number_patterns = [
            r'^\d+\.\s*',  # "1. ", "01. " 等
            r'^\(\d+\)\s*',  # "(1) ", "(01) " 等
            r'^\[\d+\]\s*',  # "[1] ", "[01] " 等
        ]
        
        unnumbered_folders = []
        for folder in subfolders:
            has_number = False
            for pattern in number_patterns:
                if re.match(pattern, folder):
                    has_number = True
                    break
            if not has_number:
                unnumbered_folders.append(folder)
        
        # 将无编号文件夹添加到匹配列表，但不包括已经在matched_folders中的
        for folder in unnumbered_folders:
            if folder not in matched_folders:
                matched_folders.append(folder)
    
    if not matched_folders:
        return []
    
    # 在匹配的文件夹中，优先选择包含关键词的文件夹
    priority_folders = []
    regular_folders = []
    
    for folder in matched_folders:
        is_priority = any(keyword.lower() in folder.lower() for keyword in priority_keywords)
        if is_priority:
            priority_folders.append(folder)
        else:
            regular_folders.append(folder)
    
    # 返回优先文件夹 + 普通文件夹
    return priority_folders + regular_folders

def main():
    st.title("压缩包分类移动工具")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("配置")
        
        # 执行操作
        st.subheader("执行操作")
        if 'scan_results' in st.session_state:
            # 初始化确认状态
            if 'confirm_all' not in st.session_state:
                st.session_state.confirm_all = False
            
            if not st.session_state.confirm_all:
                if st.button("确认执行移动", type="primary", help="移动所有页面的文件"):
                    st.session_state.confirm_all = True
                    st.rerun()
            else:
                st.warning("⚠️ 确定要移动所有文件吗？这将影响所有页面！")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认执行", type="primary"):
                        st.session_state.execute_all = True
                        st.session_state.confirm_all = False
                        st.rerun()
                with col2:
                    if st.button("❌ 取消"):
                        st.session_state.confirm_all = False
                        st.rerun()
            
            if st.button("只对本页执行移动", help="只移动当前页面的文件"):
                st.session_state.execute_current_page = True
                st.rerun()
    
        # 用户输入根路径
        root_path = st.text_input("输入根路径:", value=r"E:\1Hub\EH\1EHV", placeholder="例如: D:\\Manga\\Artists")
        
        # 正则表达式配置
        st.subheader("正则表达式配置")
        default_patterns = [
            # r'^(.+?)\s*[-_]\s*',  # 匹配开头直到第一个分隔符
            # r'\b(.+?)\b',  # 匹配单词
        ]
        patterns_text = st.text_area(
            "输入正则表达式（每行一个）:",
            value="\n".join(default_patterns),
            height=100,
            help="用于匹配压缩包文件名到二级文件夹名"
        )
        regex_patterns = [line.strip() for line in patterns_text.split('\n') if line.strip()]
        
        # 扫描按钮
        scan_button = st.button("扫描目录", type="primary")
        
        # 显示选项
        st.subheader("显示选项")
        show_full_names = st.checkbox("显示完整文件夹名", value=True, help="显示二级文件夹的完整名称，包括编号等前缀")
        items_per_page = st.selectbox("每页显示文件夹数", options=[3, 5, 10, 15, 20], index=1, help="选择每页显示的一级文件夹数量")
        
        # 移动选项
        st.subheader("移动选项")
        config = load_config()
        allow_move_to_unnumbered = st.checkbox(
            "允许无编号二级文件夹作为目标", 
            value=config.get('matching', {}).get('allow_move_to_unnumbered', False),
            help="允许将压缩包移动到没有编号前缀的二级文件夹（如'汉化'而不是'1. 汉化'）"
        )
        # 保存设置到session_state
        st.session_state.allow_move_to_unnumbered = allow_move_to_unnumbered
        
        # 黑名单管理
        st.subheader("黑名单管理")
        blacklist = load_blacklist()
        if blacklist:
            st.write("当前黑名单:")
            for item in sorted(blacklist):
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.write(f"• {item}")
                with col2:
                    if st.button(f"移除", key=f"remove_{item}", help=f"从黑名单中移除 {item}"):
                        blacklist.discard(item)
                        if save_blacklist(blacklist):
                            st.success(f"已从黑名单移除 '{item}'")
                            st.rerun()  # 重新运行以更新显示
        else:
            st.write("黑名单为空")
        
        # 显示匹配关键词配置
        st.subheader("匹配关键词配置")
        config = load_config()
        priority_keywords = config.get('matching', {}).get('priority_keywords', [])
        if priority_keywords:
            st.write("当前优先关键词:")
            for keyword in priority_keywords:
                st.write(f"• {keyword}")
        else:
            st.write("未配置优先关键词")
    # 主界面
    if scan_button:
        if not root_path:
            st.error("请输入根路径")
            return
        
        with st.spinner("正在扫描目录..."):
            scan_results = scan_directory(root_path)
        
        if not scan_results:
            st.warning("未找到同时包含压缩包和二级文件夹的一级文件夹")
            return
        
        # 存储扫描结果在session_state
        st.session_state.scan_results = scan_results
        st.session_state.root_path = root_path
        st.session_state.regex_patterns = regex_patterns
        st.session_state.show_full_names = show_full_names
        st.session_state.items_per_page = items_per_page
        
        st.success(f"扫描完成，找到 {len(scan_results)} 个一级文件夹")
    
    # 显示扫描结果和移动建议
    if 'scan_results' in st.session_state:
        scan_results = st.session_state.scan_results
        regex_patterns = st.session_state.regex_patterns
        show_full_names = st.session_state.get('show_full_names', True)
        items_per_page = st.session_state.get('items_per_page', 5)
        
        st.header("移动计划")
        
        # 分页设置
        level1_names = list(scan_results.keys())
        total_folders = len(level1_names)
        
        # 计算总页数
        total_pages = (total_folders + items_per_page - 1) // items_per_page
        
        # 初始化当前页码（如果不存在）
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 0
        
        current_page = st.session_state.current_page
        
        # 确保页码在有效范围内
        if current_page >= total_pages:
            current_page = total_pages - 1
            st.session_state.current_page = current_page
        if current_page < 0:
            current_page = 0
            st.session_state.current_page = current_page
        
        # 获取当前页的一级文件夹
        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, total_folders)
        current_level1_names = level1_names[start_idx:end_idx]
        
        # 为每个一级文件夹创建选择
        move_plan = {}
        
        for level1_name in current_level1_names:
            data = scan_results[level1_name]
            
            # 创建标题行：文件夹名 + 按钮组
            col_title, col_open, col_blacklist, col_execute = st.columns([0.45, 0.15, 0.15, 0.25])
            with col_title:
                st.subheader(f"📁 {level1_name}")
            with col_open:
                if st.button(f"打开", key=f"open_{level1_name}", help=f"在文件管理器中打开 {level1_name} 文件夹"):
                    try:
                        os.startfile(data['path'])  # Windows系统打开文件夹
                        st.success(f"已打开文件夹: {level1_name}")
                    except Exception as e:
                        st.error(f"无法打开文件夹: {e}")
            with col_blacklist:
                if st.button(f"黑名单", key=f"blacklist_{level1_name}", help=f"将 {level1_name} 添加到黑名单"):
                    add_to_blacklist(level1_name)
            with col_execute:
                if st.button(f"执行移动", key=f"execute_{level1_name}", help=f"只移动 {level1_name} 文件夹下的文件"):
                    # 执行单个文件夹的移动
                    execute_single_folder(level1_name, data, level1_move_plan)
            
            # 快速创建文件夹
            config = load_config()
            folder_templates = config.get('folder_templates', {}).get('templates', [])
            if folder_templates:
                with st.expander(f"📁 为 {level1_name} 创建子文件夹", expanded=False):
                    selected_templates = []
                    cols = st.columns(3)  # 每行3个复选框
                    for i, template in enumerate(folder_templates):
                        col_idx = i % 3
                        with cols[col_idx]:
                            if st.checkbox(f"{template}", key=f"create_{level1_name}_{template}"):
                                selected_templates.append(template)
                    
                    if st.button(f"创建选中文件夹", key=f"create_btn_{level1_name}", help=f"为 {level1_name} 创建选中的子文件夹"):
                        if selected_templates:
                            create_folders_for_level1(level1_name, data, selected_templates)
                        else:
                            st.warning("请先选择要创建的文件夹")
            
            # 全选勾选框
            skip_all = st.checkbox(f"跳过 {level1_name} 的所有文件", key=f"skip_all_{level1_name}", 
                                 help=f"取消移动 {level1_name} 文件夹下的所有压缩包")
            
            level1_move_plan = {}
            
            for archive in data['archives']:
                # 匹配建议的文件夹
                matched_folders = match_archive_to_folder(archive, data['subfolders'], regex_patterns, 
                                                   st.session_state.get('allow_move_to_unnumbered', False))
                
                # 默认选择：优先选择包含关键词的文件夹
                default_folder = matched_folders[0] if matched_folders else (data['subfolders'][0] if data['subfolders'] else None)
                
                # 如果全选跳过，则默认不移动
                move_default = bool(default_folder) and not skip_all
                
                # 创建列布局：勾选框 | 文件名 | 目标选择
                col1, col2, col3 = st.columns([0.1, 0.4, 0.5])
                
                with col1:
                    # 勾选框：是否移动
                    move_enabled = st.checkbox(
                        f"移动 {archive}",
                        value=move_default,
                        key=f"move_{level1_name}_{archive}",
                        label_visibility="collapsed"
                    )
                
                with col2:
                    st.write(f"**{archive}**")
                
                with col3:
                    if move_enabled and data['subfolders']:
                        # 平铺radio buttons选择目标文件夹
                        if show_full_names:
                            # 显示完整文件夹名
                            selected_folder = st.radio(
                                f"选择目标文件夹 ({archive})",
                                options=data['subfolders'],
                                index=data['subfolders'].index(default_folder) if default_folder and default_folder in data['subfolders'] else 0,
                                key=f"target_{level1_name}_{archive}",
                                label_visibility="collapsed",
                                format_func=lambda x: f"📁 {x}"  # 添加文件夹图标并显示完整名称
                            )
                        else:
                            # 简化显示：尝试提取主要部分
                            def simplify_name(full_name):
                                # 移除常见的编号前缀，如 "1. ", "01. ", "(1) " 等
                                simplified = re.sub(r'^\d+\.\s*', '', full_name)
                                simplified = re.sub(r'^\(\d+\)\s*', '', simplified)
                                simplified = re.sub(r'^\[\d+\]\s*', '', simplified)
                                return simplified if simplified != full_name else full_name
                            
                            simplified_options = [simplify_name(name) for name in data['subfolders']]
                            selected_idx = data['subfolders'].index(default_folder) if default_folder and default_folder in data['subfolders'] else 0
                            
                            selected_simplified = st.radio(
                                f"选择目标文件夹 ({archive})",
                                options=simplified_options,
                                index=selected_idx,
                                key=f"target_{level1_name}_{archive}",
                                label_visibility="collapsed",
                                format_func=lambda x: f"📁 {x}"
                            )
                            
                            # 根据简化名称找到对应的完整名称
                            selected_folder = data['subfolders'][simplified_options.index(selected_simplified)]
                        
                        level1_move_plan[archive] = selected_folder
                    else:
                        st.write("不移动")
                        level1_move_plan[archive] = None
            
            move_plan[level1_name] = level1_move_plan
            
            # 处理可移动的文件夹
            if 'movable_folders' in data and data['movable_folders']:
                st.subheader(f"📁 可移动的文件夹 ({len(data['movable_folders'])} 个)")
                
                for folder in data['movable_folders']:
                    # 为文件夹匹配目标文件夹（使用文件夹名作为匹配依据）
                    matched_folders = match_archive_to_folder(folder, data['subfolders'], regex_patterns, 
                                                       st.session_state.get('allow_move_to_unnumbered', False))
                    
                    # 默认选择
                    default_folder = matched_folders[0] if matched_folders else (data['subfolders'][0] if data['subfolders'] else None)
                    
                    # 创建列布局：勾选框 | 文件夹名 | 目标选择
                    col1, col2, col3 = st.columns([0.1, 0.4, 0.5])
                    
                    with col1:
                        # 勾选框：是否移动
                        move_enabled = st.checkbox(
                            f"移动文件夹 {folder}",
                            value=bool(default_folder),
                            key=f"move_folder_{level1_name}_{folder}",
                            label_visibility="collapsed"
                        )
                    
                    with col2:
                        st.write(f"**📁 {folder}**")
                    
                    with col3:
                        if move_enabled and data['subfolders']:
                            # 选择目标文件夹
                            if show_full_names:
                                selected_folder = st.radio(
                                    f"选择目标文件夹 ({folder})",
                                    options=data['subfolders'],
                                    index=data['subfolders'].index(default_folder) if default_folder and default_folder in data['subfolders'] else 0,
                                    key=f"target_folder_{level1_name}_{folder}",
                                    label_visibility="collapsed",
                                    format_func=lambda x: f"📁 {x}"
                                )
                            else:
                                # 简化显示
                                def simplify_name(full_name):
                                    simplified = re.sub(r'^\d+\.\s*', '', full_name)
                                    simplified = re.sub(r'^\(\d+\)\s*', '', simplified)
                                    simplified = re.sub(r'^\[\d+\]\s*', '', simplified)
                                    return simplified if simplified != full_name else full_name
                                
                                simplified_options = [simplify_name(name) for name in data['subfolders']]
                                selected_idx = data['subfolders'].index(default_folder) if default_folder and default_folder in data['subfolders'] else 0
                                
                                selected_simplified = st.radio(
                                    f"选择目标文件夹 ({folder})",
                                    options=simplified_options,
                                    index=selected_idx,
                                    key=f"target_folder_{level1_name}_{folder}",
                                    label_visibility="collapsed",
                                    format_func=lambda x: f"📁 {x}"
                                )
                                
                                selected_folder = data['subfolders'][simplified_options.index(selected_simplified)]
                            
                            level1_move_plan[f"folder_{folder}"] = selected_folder
                        else:
                            st.write("不移动")
                            level1_move_plan[f"folder_{folder}"] = None
            
            st.divider()
        
        # 存储移动计划（只存储当前页的）
        if 'move_plan' not in st.session_state:
            st.session_state.move_plan = {}
        st.session_state.move_plan.update(move_plan)
        
        # 显示分页信息
        if total_pages > 1:
            st.write(f"显示第 {start_idx + 1}-{end_idx} 个文件夹，共 {total_folders} 个")
        else:
            st.write(f"共 {total_folders} 个文件夹")
        
        # 检查执行标志并执行移动
        if 'execute_all' in st.session_state and st.session_state.execute_all:
            execute_all_moves()
            del st.session_state.execute_all
        
        if 'execute_current_page' in st.session_state and st.session_state.execute_current_page:
            execute_current_page_moves()
            del st.session_state.execute_current_page
        
        # 统计信息（基于所有文件夹）
        total_archives = sum(len(data['archives']) for data in scan_results.values())
        total_movable_folders = sum(len(data.get('movable_folders', [])) for data in scan_results.values())
        move_count = sum(1 for plans in st.session_state.move_plan.values() for plan in plans.values() if plan is not None)
        
        st.info(f"总压缩包: {total_archives} | 可移动文件夹: {total_movable_folders} | 计划移动: {move_count}")
        
        # 分页导航（底部）
        if total_pages > 1:
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
            with col1:
                if st.button("⏮️ 首页", key="first_page", disabled=(current_page == 0)):
                    st.session_state.current_page = 0
                    st.rerun()
            
            with col2:
                if st.button("⬅️ 上一页", key="prev_page", disabled=(current_page == 0)):
                    st.session_state.current_page = current_page - 1
                    st.rerun()
            
            with col3:
                st.markdown(f"<center><strong>第 {current_page + 1} 页 / 共 {total_pages} 页</strong></center>", 
                          unsafe_allow_html=True)
                # 页码跳转
                jump_page = st.number_input(
                    "跳转到页码",
                    min_value=1,
                    max_value=total_pages,
                    value=current_page + 1,
                    step=1,
                    key="jump_page_input"
                )
                if st.button("跳转", key="jump_button"):
                    if 1 <= jump_page <= total_pages:
                        st.session_state.current_page = jump_page - 1
                        st.rerun()
            
            with col4:
                if st.button("下一页 ➡️", key="next_page", disabled=(current_page >= total_pages - 1)):
                    st.session_state.current_page = current_page + 1
                    st.rerun()
            
            with col5:
                if st.button("末页 ⏭️", key="last_page", disabled=(current_page >= total_pages - 1)):
                    st.session_state.current_page = total_pages - 1
                    st.rerun()
            
            st.markdown("---")
        
            st.markdown("---")

if __name__ == "__main__":
    main()