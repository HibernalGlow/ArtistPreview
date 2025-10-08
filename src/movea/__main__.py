import streamlit as st
import os
import shutil
import re
from pathlib import Path

# 支持的压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}

def is_archive(file_path):
    """检查文件是否是压缩包"""
    return Path(file_path).suffix.lower() in ARCHIVE_EXTENSIONS

def scan_directory(root_path):
    """扫描根路径下的每个一级文件夹"""
    if not os.path.exists(root_path):
        st.error(f"路径不存在: {root_path}")
        return {}
    
    results = {}
    try:
        # 获取一级文件夹
        for item in os.listdir(root_path):
            level1_path = os.path.join(root_path, item)
            if os.path.isdir(level1_path):
                # 获取二级文件夹和压缩包
                subfolders = []
                archives = []
                for subitem in os.listdir(level1_path):
                    subitem_path = os.path.join(level1_path, subitem)
                    if os.path.isdir(subitem_path):
                        subfolders.append(subitem)
                    elif os.path.isfile(subitem_path) and is_archive(subitem_path):
                        archives.append(subitem)
                
                if archives:  # 只处理有压缩包的一级文件夹
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
        root_path = st.text_input("输入根路径:", value="", placeholder="例如: D:\\Manga\\Artists")
        
        # 正则表达式配置
        st.subheader("正则表达式配置")
        default_patterns = [
            r'^(.+?)\s*[-_]\s*',  # 匹配开头直到第一个分隔符
            r'\b(.+?)\b',  # 匹配单词
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
    
    # 主界面
    if scan_button:
        if not root_path:
            st.error("请输入根路径")
            return
        
        with st.spinner("正在扫描目录..."):
            scan_results = scan_directory(root_path)
        
        if not scan_results:
            st.warning("未找到包含压缩包的一级文件夹")
            return
        
        # 存储扫描结果在session_state
        st.session_state.scan_results = scan_results
        st.session_state.regex_patterns = regex_patterns
        
        st.success(f"扫描完成，找到 {len(scan_results)} 个一级文件夹")
    
    # 显示扫描结果和移动建议
    if 'scan_results' in st.session_state:
        scan_results = st.session_state.scan_results
        regex_patterns = st.session_state.regex_patterns
        
        st.header("移动计划")
        
        # 为每个一级文件夹创建选择
        move_plan = {}
        
        for level1_name, data in scan_results.items():
            st.subheader(f"📁 {level1_name}")
            
            level1_move_plan = {}
            
            for archive in data['archives']:
                # 匹配建议的文件夹
                matched_folders = match_archive_to_folder(archive, data['subfolders'], regex_patterns)
                
                # 默认选择：排序后的第一个匹配文件夹
                default_folder = sorted(matched_folders)[0] if matched_folders else (data['subfolders'][0] if data['subfolders'] else None)
                
                # 创建列布局
                col1, col2, col3 = st.columns([0.1, 0.4, 0.5])
                
                with col1:
                    # 勾选框：是否移动
                    move_enabled = st.checkbox(
                        "",
                        value=bool(default_folder),
                        key=f"move_{level1_name}_{archive}"
                    )
                
                with col2:
                    st.write(f"**{archive}**")
                
                with col3:
                    if move_enabled and data['subfolders']:
                        # 选择目标文件夹
                        selected_folder = st.selectbox(
                            "移动到:",
                            options=data['subfolders'],
                            index=data['subfolders'].index(default_folder) if default_folder and default_folder in data['subfolders'] else 0,
                            key=f"target_{level1_name}_{archive}",
                            label_visibility="collapsed"
                        )
                        level1_move_plan[archive] = selected_folder
                    else:
                        st.write("不移动")
                        level1_move_plan[archive] = None
            
            move_plan[level1_name] = level1_move_plan
            
            st.divider()
        
        # 存储移动计划
        st.session_state.move_plan = move_plan
        
        # 统计信息
        total_archives = sum(len(data['archives']) for data in scan_results.values())
        move_count = sum(1 for plans in move_plan.values() for plan in plans.values() if plan is not None)
        
        st.info(f"总压缩包数量: {total_archives} | 计划移动: {move_count}")
        
        # 确认执行
        if st.button("确认执行移动", type="primary"):
            if not move_plan:
                st.error("没有移动计划")
                return
            
            with st.spinner("正在执行移动..."):
                success_count = 0
                error_count = 0
                
                for level1_name, archives_plan in move_plan.items():
                    level1_path = scan_results[level1_name]['path']
                    
                    for archive, target_folder in archives_plan.items():
                        if target_folder is None:
                            continue  # 不移动
                        
                        source_path = os.path.join(level1_path, archive)
                        target_path = os.path.join(level1_path, target_folder, archive)
                        
                        try:
                            # 确保目标文件夹存在
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            # 移动文件
                            shutil.move(source_path, target_path)
                            st.success(f"✅ {level1_name}/{archive} -> {target_folder}")
                            success_count += 1
                        except Exception as e:
                            st.error(f"❌ 移动失败 {level1_name}/{archive}: {e}")
                            error_count += 1
                
                st.success(f"移动完成! 成功: {success_count}, 失败: {error_count}")
                
                # 清除session_state
                del st.session_state.scan_results
                del st.session_state.move_plan
                del st.session_state.regex_patterns

if __name__ == "__main__":
    main()