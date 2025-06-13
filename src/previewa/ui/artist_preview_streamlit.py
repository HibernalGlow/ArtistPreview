import streamlit as st
import asyncio
import aiohttp
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
from bs4 import BeautifulSoup
import io
import base64
from dataclasses import dataclass, asdict
import logging
from loguru import logger
import os
import sys

# 设置页面配置
st.set_page_config(
    page_title="画师预览管理器",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

def setup_logger(app_name="streamlit_app", project_root=None, console_output=True):
    """配置 Loguru 日志系统"""
    if project_root is None:
        project_root = Path(__file__).parent.resolve()
    
    logger.remove()
    
    if console_output:
        logger.add(
            sys.stdout,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level.icon} {level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
        )
    
    current_time = datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")
    hour_str = current_time.strftime("%H")
    minute_str = current_time.strftime("%M%S")
    
    log_dir = os.path.join(project_root, "logs", app_name, date_str, hour_str)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{minute_str}.log")
    
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {elapsed} | {level.icon} {level: <8} | {name}:{function}:{line} - {message}",
    )
    
    return logger

logger = setup_logger(app_name="artist_preview_streamlit", console_output=True)

@dataclass
class ArtistInfo:
    """画师信息数据类"""
    name: str
    folder: str
    preview_url: str
    files: List[str]
    is_existing: bool
    selected: bool = False
    has_preview: bool = False
    
    def __post_init__(self):
        self.has_preview = bool(self.preview_url)

class DataManager:
    """数据管理器，负责JSON数据的读写"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / 'data'
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.artists_file = self.data_dir / 'artists.json'
        self.cache_file = self.data_dir / 'preview_cache.json'
        self.settings_file = self.data_dir / 'settings.json'
        
    def load_artists(self) -> List[ArtistInfo]:
        """加载画师数据"""
        try:
            if self.artists_file.exists():
                with open(self.artists_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return [ArtistInfo(**item) for item in data]
            return []
        except Exception as e:
            logger.error(f"加载画师数据时发生错误: {e}")
            return []
    
    def save_artists(self, artists: List[ArtistInfo]):
        """保存画师数据"""
        try:
            data = [asdict(artist) for artist in artists]
            with open(self.artists_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(artists)} 个画师数据")
        except Exception as e:
            logger.error(f"保存画师数据时发生错误: {e}")
    
    def load_cache(self) -> Dict[str, str]:
        """加载预览图缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载缓存时发生错误: {e}")
            return {}
    
    def save_cache(self, cache: Dict[str, str]):
        """保存预览图缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓存时发生错误: {e}")
    
    def load_settings(self) -> Dict:
        """加载设置"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                'base_url': 'https://www.wn01.uk',
                'auto_select_no_preview': False,
                'items_per_page': 25
            }
        except Exception as e:
            logger.error(f"加载设置时发生错误: {e}")
            return {}
    
    def save_settings(self, settings: Dict):
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存设置时发生错误: {e}")

class PreviewGenerator:
    """预览图生成器"""
    
    def __init__(self, base_url: str = "https://www.wn01.uk"):
        self.base_url = base_url
        self.cache = {}
        
    async def get_preview_url(self, artist_name: str) -> Optional[str]:
        """获取画师作品的预览图URL"""
        clean_name = artist_name.strip('[]')
        
        # 检查缓存
        if clean_name in self.cache:
            return self.cache[clean_name]
        
        try:
            async with aiohttp.ClientSession() as session:
                # 提取搜索关键词
                search_terms = self._extract_search_terms(clean_name)
                
                for term in search_terms:
                    search_query = term.replace(' ', '+')
                    search_url = f"{self.base_url}/search/?q={search_query}"
                    
                    async with session.get(search_url) as response:
                        if response.status != 200:
                            continue
                            
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        gallery_items = soup.select('.gallary_item')
                        
                        for item in gallery_items:
                            img = item.select_one('img')
                            if img and img.get('src'):
                                img_url = f"https:{img['src']}"
                                try:
                                    async with session.head(img_url) as img_response:
                                        if img_response.status == 200:
                                            self.cache[clean_name] = img_url
                                            return img_url
                                except:
                                    continue
                
                self.cache[clean_name] = ""
                return None
                
        except Exception as e:
            logger.error(f"获取画师 {clean_name} 预览图时发生错误: {e}")
            return None
    
    def _extract_search_terms(self, artist_name: str) -> List[str]:
        """提取搜索关键词"""
        search_terms = []
        
        if '(' in artist_name:
            circle_part = artist_name.split('(')[0].strip()
            artist_part = artist_name.split('(')[1].rstrip(')').strip()
            
            artist_names = [n.strip() for n in artist_part.split('、')]
            search_terms.extend(artist_names)
            
            circle_names = [n.strip() for n in circle_part.split('、')]
            search_terms.extend(circle_names)
        else:
            search_terms = [n.strip() for n in artist_name.split('、')]
        
        search_terms = list(set(term for term in search_terms if term))
        
        if not search_terms:
            search_terms = [artist_name]
        
        return search_terms

def load_yaml_data(yaml_path: str) -> Tuple[List[ArtistInfo], List[ArtistInfo]]:
    """从YAML文件加载数据"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        existing_artists = []
        for folder, files in data['artists']['existing_artists'].items():
            existing_artists.append(ArtistInfo(
                name=folder.strip('[]'),
                folder=folder,
                preview_url="",
                files=files,
                is_existing=True
            ))
        
        new_artists = []
        for folder, files in data['artists']['new_artists'].items():
            new_artists.append(ArtistInfo(
                name=folder.strip('[]'),
                folder=folder,
                preview_url="",
                files=files,
                is_existing=False
            ))
        
        return existing_artists, new_artists
        
    except Exception as e:
        logger.error(f"加载YAML文件时发生错误: {e}")
        st.error(f"加载YAML文件时发生错误: {e}")
        return [], []

def create_download_link(data: str, filename: str, link_text: str) -> str:
    """创建下载链接"""
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:text/plain;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

async def generate_previews_async(artists: List[ArtistInfo], generator: PreviewGenerator):
    """异步生成预览图"""
    tasks = []
    for artist in artists:
        if not artist.is_existing and not artist.preview_url:
            tasks.append(generator.get_preview_url(artist.name))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    task_idx = 0
    for artist in artists:
        if not artist.is_existing and not artist.preview_url:
            result = results[task_idx]
            if isinstance(result, str) and result:
                artist.preview_url = result
                artist.has_preview = True
            task_idx += 1

def main():
    """主函数"""
    st.title("🎨 画师预览管理器")
    st.markdown("---")
    
    # 初始化数据管理器
    if 'data_manager' not in st.session_state:
        st.session_state.data_manager = DataManager()
    
    # 初始化设置
    if 'settings' not in st.session_state:
        st.session_state.settings = st.session_state.data_manager.load_settings()
    
    # 初始化画师数据
    if 'artists' not in st.session_state:
        st.session_state.artists = st.session_state.data_manager.load_artists()
    
    # 初始化状态变量
    if 'last_update' not in st.session_state:
        st.session_state.last_update = datetime.now()
    
    if 'processing' not in st.session_state:
        st.session_state.processing = False
      # 侧边栏
    with st.sidebar:
        st.header("⚙️ 设置")
        
        # 显示当前状态
        if st.session_state.artists:
            total_artists = len(st.session_state.artists)
            existing_count = len([a for a in st.session_state.artists if a.is_existing])
            new_count = total_artists - existing_count
            preview_count = len([a for a in st.session_state.artists if a.has_preview and not a.is_existing])
            
            st.metric("总画师数", total_artists)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("已存在", existing_count)
                st.metric("有预览", preview_count)
            with col2:
                st.metric("新画师", new_count)
                st.metric("无预览", new_count - preview_count)
            
            st.markdown("---")
        
        # 基础设置
        st.session_state.settings['base_url'] = st.text_input(
            "搜索网站URL", 
            value=st.session_state.settings.get('base_url', 'https://www.wn01.uk'),
            help="用于搜索画师预览图的网站"
        )
        
        st.session_state.settings['items_per_page'] = st.selectbox(
            "每页显示数量",
            [10, 25, 50, 100],
            index=[10, 25, 50, 100].index(st.session_state.settings.get('items_per_page', 25)),
            help="每页显示的画师数量"
        )
        
        # 保存设置
        if st.button("💾 保存设置"):
            st.session_state.data_manager.save_settings(st.session_state.settings)
            st.success("设置已保存")
        
        st.divider()
          # 数据导入
        st.header("📁 数据导入")
        
        # 测试数据
        if st.button("🧪 加载测试数据"):
            try:
                test_file = st.session_state.data_manager.data_dir / 'test_artists.json'
                if test_file.exists():
                    with open(test_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    st.session_state.artists = [ArtistInfo(**item) for item in data]
                    st.session_state.data_manager.save_artists(st.session_state.artists)
                    st.success("测试数据已加载")
                    st.rerun()
                else:
                    st.warning("测试数据文件不存在")
            except Exception as e:
                st.error(f"加载测试数据失败: {e}")
        
        uploaded_yaml = st.file_uploader("选择YAML文件", type=['yaml', 'yml'])
        if uploaded_yaml is not None:
            if st.button("📥 导入YAML数据"):
                try:
                    # 保存上传的文件
                    yaml_path = st.session_state.data_manager.data_dir / uploaded_yaml.name
                    with open(yaml_path, 'wb') as f:
                        f.write(uploaded_yaml.getvalue())
                    
                    # 加载数据
                    existing_artists, new_artists = load_yaml_data(str(yaml_path))
                    st.session_state.artists = existing_artists + new_artists
                    
                    # 保存到JSON
                    st.session_state.data_manager.save_artists(st.session_state.artists)
                    
                    st.success(f"成功导入 {len(existing_artists)} 个已存在画师和 {len(new_artists)} 个新画师")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"导入失败: {e}")
        
        uploaded_json = st.file_uploader("选择JSON文件", type=['json'])
        if uploaded_json is not None:
            if st.button("📥 导入JSON数据"):
                try:
                    data = json.loads(uploaded_json.getvalue().decode('utf-8'))
                    st.session_state.artists = [ArtistInfo(**item) for item in data]
                    st.session_state.data_manager.save_artists(st.session_state.artists)
                    st.success(f"成功导入 {len(st.session_state.artists)} 个画师")
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败: {e}")
        
        # 文本导入
        st.subheader("✏️ 文本导入")
        artist_text = st.text_area("画师名称列表（每行一个）")
        if st.button("📥 导入画师名称"):
            if artist_text.strip():
                names = [name.strip() for name in artist_text.strip().split('\n') if name.strip()]
                for artist in st.session_state.artists:
                    artist.selected = any(
                        name.lower() in artist.name.lower() or name.lower() in artist.folder.lower()
                        for name in names
                    )
                st.success(f"已根据 {len(names)} 个名称更新选择状态")
                st.rerun()
        
        st.divider()
        
        # 数据导出
        st.header("📤 数据导出")
        
        if st.session_state.artists:
            selected_artists = [a for a in st.session_state.artists if a.selected]
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 导出选中画师"):
                    if selected_artists:
                        artist_names = [artist.name for artist in selected_artists]
                        data = '\n'.join(artist_names)
                        st.download_button(
                            label="下载画师列表",
                            data=data,
                            file_name="selected_artists.txt",
                            mime="text/plain"
                        )
                    else:
                        st.warning("请先选择画师")
            
            with col2:
                if st.button("📦 导出压缩包"):
                    if selected_artists:
                        files = []
                        for artist in selected_artists:
                            files.extend(artist.files)
                        data = '\n'.join(files)
                        st.download_button(
                            label="下载文件列表",
                            data=data,
                            file_name="selected_files.txt",
                            mime="text/plain"
                        )
                    else:
                        st.warning("请先选择画师")
            
            if st.button("💾 导出JSON数据"):
                data = json.dumps([asdict(artist) for artist in st.session_state.artists], 
                                ensure_ascii=False, indent=2)
                st.download_button(
                    label="下载JSON文件",
                    data=data,
                    file_name="artists_data.json",
                    mime="application/json"
                )
    
    # 主内容区域
    if not st.session_state.artists:
        st.info("👆 请在侧边栏导入数据开始使用")
        return
    
    # 筛选和操作栏
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        search_term = st.text_input("🔍 搜索画师", placeholder="输入画师名称或文件夹名称")
    
    with col2:
        show_type = st.selectbox("显示类型", ["全部", "已存在", "新画师"])
    with col3:
        preview_filter = st.selectbox("预览图筛选", ["全部", "有预览图", "无预览图"])
    
    with col4:
        st.write("")  # 占位
        if st.button("🔄 生成预览图", disabled=st.session_state.processing):
            st.session_state.processing = True
            
            generator = PreviewGenerator(st.session_state.settings['base_url'])
            new_artists = [a for a in st.session_state.artists if not a.is_existing and not a.preview_url]
            
            if new_artists:
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    for i, artist in enumerate(new_artists):
                        status_text.text(f"正在处理: {artist.name} ({i+1}/{len(new_artists)})")
                        progress_bar.progress((i + 1) / len(new_artists))
                        
                        # 获取预览图
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            preview_url = loop.run_until_complete(generator.get_preview_url(artist.name))
                            if preview_url:
                                artist.preview_url = preview_url
                                artist.has_preview = True
                        finally:
                            loop.close()
                    
                    # 保存数据
                    st.session_state.data_manager.save_artists(st.session_state.artists)
                    
                    progress_bar.empty()
                    status_text.empty()
                    st.success(f"已为 {len(new_artists)} 个画师生成预览图")
                    
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"生成预览图时发生错误: {e}")
                
                finally:
                    st.session_state.processing = False
                    st.rerun()
            else:
                st.session_state.processing = False
                st.info("没有需要生成预览图的画师")
    
    # 快速操作按钮
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("✅ 全选"):
            for artist in st.session_state.artists:
                artist.selected = True
            st.rerun()
    
    with col2:
        if st.button("❌ 全不选"):
            for artist in st.session_state.artists:
                artist.selected = False
            st.rerun()
    
    with col3:
        if st.button("🚫 选择无预览"):
            for artist in st.session_state.artists:
                artist.selected = not artist.has_preview and not artist.is_existing
            st.rerun()
    
    with col4:
        if st.button("🔄 反选"):
            for artist in st.session_state.artists:
                artist.selected = not artist.selected
            st.rerun()
    
    # 筛选艺术家
    filtered_artists = st.session_state.artists
    
    if search_term:
        filtered_artists = [
            a for a in filtered_artists 
            if search_term.lower() in a.name.lower() or search_term.lower() in a.folder.lower()
        ]
    
    if show_type == "已存在":
        filtered_artists = [a for a in filtered_artists if a.is_existing]
    elif show_type == "新画师":
        filtered_artists = [a for a in filtered_artists if not a.is_existing]
    
    if preview_filter == "有预览图":
        filtered_artists = [a for a in filtered_artists if a.has_preview]
    elif preview_filter == "无预览图":
        filtered_artists = [a for a in filtered_artists if not a.has_preview]
    
    # 显示统计信息
    total_count = len(st.session_state.artists)
    filtered_count = len(filtered_artists)
    selected_count = len([a for a in st.session_state.artists if a.selected])
    
    st.info(f"📊 总计: {total_count} | 筛选结果: {filtered_count} | 已选择: {selected_count}")
    
    # 分页显示
    items_per_page = st.session_state.settings['items_per_page']
    total_pages = (len(filtered_artists) + items_per_page - 1) // items_per_page
    
    if total_pages > 1:
        page = st.selectbox("页码", range(1, total_pages + 1)) - 1
    else:
        page = 0
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered_artists))
    page_artists = filtered_artists[start_idx:end_idx]
    
    # 显示画师列表
    for i, artist in enumerate(page_artists):
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 6])
            
            with col1:
                artist.selected = st.checkbox(
                    "选择", 
                    value=artist.selected, 
                    key=f"select_{start_idx + i}"
                )
            
            with col2:
                if artist.preview_url and not artist.is_existing:
                    st.image(artist.preview_url, width=100)
                elif not artist.is_existing:
                    st.write("🚫 无预览图")
                else:
                    st.write("📁 已存在")
            
            with col3:
                st.write(f"**{artist.name}**")
                st.write(f"📂 {artist.folder}")
                st.write(f"📄 {len(artist.files)} 个文件")
                
                if not artist.is_existing and st.button(f"🔄 重新获取预览", key=f"refresh_{start_idx + i}"):
                    with st.spinner("获取预览图..."):
                        generator = PreviewGenerator(st.session_state.settings['base_url'])
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            preview_url = loop.run_until_complete(generator.get_preview_url(artist.name))
                            if preview_url:
                                artist.preview_url = preview_url
                                artist.has_preview = True
                                st.session_state.data_manager.save_artists(st.session_state.artists)
                                st.success("预览图已更新")
                                st.rerun()
                            else:
                                st.warning("未找到预览图")
                        finally:
                            loop.close()
            
            with col4:
                with st.expander(f"文件列表 ({len(artist.files)} 个)"):
                    for file in artist.files[:10]:  # 只显示前10个文件
                        st.write(f"• {file}")
                    if len(artist.files) > 10:
                        st.write(f"... 还有 {len(artist.files) - 10} 个文件")
            
            st.divider()
    
    # 页面底部信息
    if total_pages > 1:
        st.write(f"第 {page + 1} 页，共 {total_pages} 页")

if __name__ == "__main__":
    main()
