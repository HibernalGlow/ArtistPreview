"""UI界面模块"""
import streamlit as st
import os
import re
from .config import load_config, save_config, load_blacklist, save_blacklist, add_to_blacklist, load_folder_blacklist, save_folder_blacklist, is_folder_blacklisted
from .scanner import scan_directory, match_archive_to_folder
from .file_ops import execute_single_folder, execute_all_moves, execute_current_page_moves, create_folders_for_level1

def render_sidebar():
    """渲染侧边栏配置"""
    with st.sidebar:
        st.header("配置")

        # 执行操作
        st.subheader("⚡ 执行操作")

        # 检查是否有扫描结果
        has_scan_results = 'scan_results' in st.session_state and st.session_state.scan_results

        if has_scan_results:
            scan_results = st.session_state.scan_results
            total_moves = sum(len(data.get('archives', [])) for data in scan_results.values())

            # 显示统计信息
            st.info(f"📊 发现 {len(scan_results)} 个文件夹，共 {total_moves} 个待移动文件")

            # 执行按钮区域
            st.markdown("---")

            # 初始化确认状态
            if 'confirm_all' not in st.session_state:
                st.session_state.confirm_all = False

            # 主要执行按钮
            col1, col2 = st.columns(2)

            with col1:
                if not st.session_state.confirm_all:
                    if st.button("🚀 确认执行移动", type="primary", help="移动所有页面的文件", use_container_width=True):
                        st.session_state.confirm_all = True
                        st.rerun()
                else:
                    st.warning("⚠️ 确定要移动所有文件吗？这将影响所有页面！")
                    if st.button("✅ 确认执行", type="primary", use_container_width=True):
                        st.session_state.execute_all = True
                        st.session_state.confirm_all = False
                        st.rerun()
                    if st.button("❌ 取消", use_container_width=True):
                        st.session_state.confirm_all = False
                        st.rerun()

            with col2:
                if st.button("📄 只对本页执行移动", help="只移动当前页面的文件", use_container_width=True):
                    st.session_state.execute_current_page = True
                    st.rerun()

            st.markdown("---")
        else:
            st.info("💡 请先点击「扫描目录」按钮开始分析文件")

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

        enable_folder_moving = st.checkbox(
            "启用文件夹移动功能",
            value=config.get('folder_moving', {}).get('enabled', True),
            help="允许移动文件夹，而不仅仅是压缩包文件"
        )
        # 保存设置到session_state
        st.session_state.enable_folder_moving = enable_folder_moving

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

        # 文件夹黑名单管理
        st.subheader("文件夹黑名单管理")
        folder_blacklist = load_folder_blacklist()
        if folder_blacklist:
            st.write("当前文件夹黑名单:")
            for item in sorted(folder_blacklist):
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.write(f"• {item}")
                with col2:
                    if st.button(f"移除", key=f"remove_folder_{item}", help=f"从文件夹黑名单中移除 {item}"):
                        folder_blacklist.remove(item)
                        if save_folder_blacklist(folder_blacklist):
                            st.success(f"已从文件夹黑名单移除 '{item}'")
                            st.rerun()  # 重新运行以更新显示
        else:
            st.write("文件夹黑名单为空")

        # 添加到文件夹黑名单
        new_folder_blacklist_item = st.text_input("添加文件夹到黑名单", key="new_folder_blacklist",
                                                placeholder="输入文件夹名称（支持正则表达式）")
        if st.button("添加到文件夹黑名单", key="add_folder_blacklist"):
            if new_folder_blacklist_item.strip():
                if new_folder_blacklist_item not in folder_blacklist:
                    folder_blacklist.append(new_folder_blacklist_item.strip())
                    if save_folder_blacklist(folder_blacklist):
                        st.success(f"已添加 '{new_folder_blacklist_item}' 到文件夹黑名单")
                        st.rerun()
                else:
                    st.warning(f"'{new_folder_blacklist_item}' 已在文件夹黑名单中")
            else:
                st.warning("请输入有效的文件夹名称")

        # 显示匹配关键词配置
        st.subheader("匹配关键词配置")
        priority_keywords = config.get('matching', {}).get('priority_keywords', [])
        if priority_keywords:
            st.write("当前优先关键词:")
            for keyword in priority_keywords:
                st.write(f"• {keyword}")
        else:
            st.write("未配置优先关键词")

    return root_path, regex_patterns, scan_button, show_full_names, items_per_page

def render_main_interface(scan_button, root_path, regex_patterns, show_full_names, items_per_page):
    """渲染主界面"""
    # 初始化session_state
    if 'move_plan' not in st.session_state:
        st.session_state.move_plan = {}

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
            col_title, col_open, col_blacklist, col_execute = st.columns([0.4, 0.18, 0.18, 0.24])

            with col_title:
                # 显示文件夹信息
                archive_count = len(data.get('archives', []))
                folder_count = len(data.get('movable_folders', []))
                st.subheader(f"📁 {level1_name}")
                st.caption(f"📦 {archive_count} 个压缩包 • 📂 {folder_count} 个文件夹")

                # 显示警告信息（如果有）
                if data.get('warning'):
                    st.warning(data['warning'])

            with col_open:
                if st.button("🔍 打开", key=f"open_{level1_name}", help=f"在文件管理器中打开 {level1_name} 文件夹", use_container_width=True):
                    try:
                        os.startfile(data['path'])  # Windows系统打开文件夹
                        st.success(f"已打开文件夹: {level1_name}")
                    except Exception as e:
                        st.error(f"无法打开文件夹: {e}")

            with col_blacklist:
                if st.button("🚫 黑名单", key=f"blacklist_{level1_name}", help=f"将 {level1_name} 添加到黑名单", use_container_width=True):
                    add_to_blacklist(level1_name)

            with col_execute:
                # 检查是否有移动计划
                level1_move_plan = st.session_state.move_plan.get(level1_name, {})
                has_moves = bool(level1_move_plan)

                button_text = "⚡ 执行移动" if has_moves else "📋 无移动计划"
                button_help = f"移动 {level1_name} 文件夹下的文件" if has_moves else "此文件夹没有待移动的文件"

                if st.button(button_text, key=f"execute_{level1_name}", help=button_help,
                           disabled=not has_moves, use_container_width=True):
                    # 执行单个文件夹的移动
                    execute_single_folder(level1_name, data, level1_move_plan)
                    # 重新扫描目录以更新显示
                    st.session_state.scan_results = scan_directory(st.session_state.root_path)
                    st.session_state.move_plan.pop(level1_name, None)
                    st.rerun()  # 强制刷新页面

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
                            # 重新扫描目录以更新显示
                            st.session_state.scan_results = scan_directory(st.session_state.root_path)
                            st.rerun()  # 强制刷新页面
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

            # 处理可移动的文件夹（只有启用文件夹移动功能时才显示）
            if (st.session_state.get('enable_folder_moving', True) and
                'movable_folders' in data and data['movable_folders']):
                st.subheader(f"📁 可移动的文件夹 ({len(data['movable_folders'])} 个)")

                folder_blacklist = load_folder_blacklist()

                for folder in data['movable_folders']:
                    # 检查文件夹是否在黑名单中（支持正则匹配）
                    if is_folder_blacklisted(folder, folder_blacklist):
                        st.write(f"**📁 {folder}** (在文件夹黑名单中，跳过)")
                        level1_move_plan[f"folder_{folder}"] = None
                        continue

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
            st.rerun()  # 强制刷新页面以显示更新结果

        if 'execute_current_page' in st.session_state and st.session_state.execute_current_page:
            execute_current_page_moves()
            del st.session_state.execute_current_page
            st.rerun()  # 强制刷新页面以显示更新结果

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