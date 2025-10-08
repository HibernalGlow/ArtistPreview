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

# 黑名单文件路径
BLACKLIST_FILE = Path(__file__).parent / "blacklist.toml"

def load_blacklist():
    """加载黑名单"""
    if BLACKLIST_FILE.exists():
        try:
            with open(BLACKLIST_FILE, 'rb') as f:
                data = tomllib.load(f)
                return set(data.get('blacklist', []))
        except Exception as e:
            st.error(f"加载黑名单失败: {e}")
    return set()

def save_blacklist(blacklist):
    """保存黑名单"""
    try:
        data = {'blacklist': list(blacklist)}
        with open(BLACKLIST_FILE, 'wb') as f:
            tomli_w.dump(data, f)
        return True
    except Exception as e:
        st.error(f"保存黑名单失败: {e}")
        return False

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
                    
                # 获取二级文件夹和压缩包
                subfolders = []
                archives = []
                for subitem in os.listdir(level1_path):
                    subitem_path = os.path.join(level1_path, subitem)
                    if os.path.isdir(subitem_path):
                        subfolders.append(subitem)
                    elif os.path.isfile(subitem_path) and is_archive(subitem_path):
                        archives.append(subitem)
                
                if archives and subfolders:  # 只处理有压缩包且有二级文件夹的一级文件夹
                    results[item] = {
                        'path': level1_path,
                        'subfolders': sorted(subfolders),  # 排序二级文件夹
                        'archives': archives
                    }
    except Exception as e:
        st.error(f"扫描目录时出错: {e}")
    
    return results

def match_archive_to_folder(archive_name, subfolders, regex_patterns):
    """使用正则匹配压缩包到二级文件夹"""
    matches = []
    for folder in subfolders:
        for pattern in regex_patterns:
            try:
                if re.search(pattern, archive_name, re.IGNORECASE):
                    matches.append(folder)
                    break  # 找到匹配就停止
            except re.error:
                continue  # 忽略无效的正则表达式
    return matches

def main():
    st.title("压缩包分类移动工具")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("配置")
        
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
            col_title, col_open, col_blacklist = st.columns([0.6, 0.2, 0.2])
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
            
            # 全选勾选框
            skip_all = st.checkbox(f"跳过 {level1_name} 的所有文件", key=f"skip_all_{level1_name}", 
                                 help=f"取消移动 {level1_name} 文件夹下的所有压缩包")
            
            level1_move_plan = {}
            
            for archive in data['archives']:
                # 匹配建议的文件夹
                matched_folders = match_archive_to_folder(archive, data['subfolders'], regex_patterns)
                
                # 默认选择：排序后的第一个匹配文件夹
                default_folder = sorted(matched_folders)[0] if matched_folders else (data['subfolders'][0] if data['subfolders'] else None)
                
                # 如果全选跳过，则默认不移动
                move_default = bool(default_folder) and not skip_all
                
                # 创建列布局：勾选框 | 文件名 | 目标选择
                col1, col2, col3 = st.columns([0.1, 0.4, 0.5])
                
                with col1:
                    # 勾选框：是否移动
                    move_enabled = st.checkbox(
                        "",
                        value=move_default,
                        key=f"move_{level1_name}_{archive}"
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
        
        # 统计信息（基于所有文件夹）
        total_archives = sum(len(data['archives']) for data in scan_results.values())
        move_count = sum(1 for plans in st.session_state.move_plan.values() for plan in plans.values() if plan is not None)
        
        st.info(f"总压缩包数量: {total_archives} | 计划移动: {move_count}")
        
        # 确认执行
        col1, col2 = st.columns(2)
        with col1:
            execute_all = st.button("确认执行移动", type="primary", help="移动所有页面的文件")
        with col2:
            execute_current_page = st.button("只对本页执行移动", help="只移动当前页面的文件")
        
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