import yaml
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
import logging
import asyncio
import aiohttp
from dataclasses import dataclass
from datetime import datetime
import os
import sys
from jinja2 import Environment, FileSystemLoader
import json
from nodes.record.logger_config import setup_logger

config = {
    'script_name': 'artistpreview_table',
    'console_enabled': True
}
logger, config_info = setup_logger(config)

@dataclass
class ArtistPreview:
    name: str
    folder: str
    preview_url: str
    files: List[str]
    is_existing: bool

class PreviewCache:
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent / 'cache'
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / 'preview_cache.json'
        self.cache: Dict[str, str] = {}
        self._load_cache()
    
    def _load_cache(self):
        """加载缓存文件"""
        try:
            if not self.cache_dir.exists():
                self.cache_dir.mkdir(parents=True)
                logger.info(f"创建缓存目录: {self.cache_dir}")
            
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"已加载 {len(self.cache)} 个预览图缓存")
            else:
                logger.info("缓存文件不存在，将创建新缓存")
                self.save_cache()
        except Exception as e:
            logger.error(f"加载缓存文件时发生错误: {e}")
            self.cache = {}
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(self.cache)} 个预览图缓存")
        except Exception as e:
            logger.error(f"保存缓存文件时发生错误: {e}")
    
    def get(self, artist_name: str) -> Optional[str]:
        """获取缓存的预览图URL"""
        return self.cache.get(artist_name)
    
    def set(self, artist_name: str, preview_url: str):
        """设置预览图URL缓存"""
        self.cache[artist_name] = preview_url
        self.save_cache()

class ArtistPreviewGenerator:
    def __init__(self, base_url: str = "https://www.wn01.uk", cache_dir: str = None):
        self.base_url = base_url
        self.session = None
        self.processed_count = {'existing': 0, 'new': 0}
        self.success_count = {'existing': 0, 'new': 0}
        self.failed_count = {'existing': 0, 'new': 0}
        self.current_count = 0
        self.total_tasks = 0
        self.cache = PreviewCache(cache_dir)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        logger.info("初始化画师预览生成器会话")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            logger.info("关闭画师预览生成器会话")
            
    async def _get_preview_url(self, artist_name: str) -> Optional[str]:
        """获取画师作品的预览图URL"""
        # 首先检查缓存
        clean_name = artist_name.strip('[]')
        cached_url = self.cache.get(clean_name)
        if cached_url:
            logger.info(f"从缓存获取画师 {clean_name} 的预览图")
            return cached_url
            
        try:
            logger.debug(f"开始获取画师 {clean_name} 的预览图")
            
            # 提取所有可能的搜索关键词
            search_terms = []
            
            # 处理带括号的情况 - 社团(画师)格式
            if '(' in clean_name:
                circle_part = clean_name.split('(')[0].strip()
                artist_part = clean_name.split('(')[1].rstrip(')').strip()
                
                # 添加画师名（按顿号分割）
                artist_names = [n.strip() for n in artist_part.split('、')]
                search_terms.extend(artist_names)
                
                # 添加社团名（按顿号分割）
                circle_names = [n.strip() for n in circle_part.split('、')]
                search_terms.extend(circle_names)
            else:
                # 没有括号的情况，直接按顿号分割
                search_terms = [n.strip() for n in clean_name.split('、')]
            
            # 过滤空字符串并去重
            search_terms = list(set(term for term in search_terms if term))
            
            # 如果没有提取到搜索词，使用完整名称
            if not search_terms:
                search_terms = [clean_name]
            
            logger.debug(f"搜索关键词: {search_terms}")
            
            # 按优先级尝试每个搜索词
            for term in search_terms:
                # 将空格替换为加号
                search_query = term.replace(' ', '+')
                search_url = f"{self.base_url}/search/?q={search_query}"
                
                async with self.session.get(search_url) as response:
                    if response.status != 200:
                        logger.warning(f"搜索画师 {term} 失败: HTTP {response.status}")
                        continue
                        
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    gallery_items = soup.select('.gallary_item')
                    logger.debug(f"使用关键词 '{term}' 找到 {len(gallery_items)} 个预览图项目")
                    
                    for item in gallery_items:
                        img = item.select_one('img')
                        if img and img.get('src'):
                            img_url = f"https:{img['src']}"
                            try:
                                async with self.session.head(img_url) as img_response:
                                    if img_response.status == 200:
                                        logger.info(f"使用关键词 '{term}' 成功获取画师预览图: {img_url}")
                                        # 保存到缓存
                                        self.cache.set(clean_name, img_url)
                                        return img_url
                            except Exception as e:
                                logger.debug(f"验证预览图失败: {img_url}, 错误: {e}")
                                continue
            
            logger.warning(f"未找到画师 {clean_name} 的有效预览图")
            # 缓存空结果
            self.cache.set(clean_name, "")
            return None
        except Exception as e:
            logger.error(f"获取画师 {clean_name} 预览图时发生错误: {e}")
            return None

    async def process_artist(self, folder_name: str, files: List[str], is_existing: bool) -> ArtistPreview:
        """处理单个画师信息"""
        artist_type = "已存在" if is_existing else "新"
        self.processed_count['existing' if is_existing else 'new'] += 1
        
        self.current_count += 1
        logger.info(f"开始处理{artist_type}画师: {folder_name} ({self.current_count}/{self.total_tasks})")
        
        logger.debug(f"画师 {folder_name} 的文件数量: {len(files)}")
        
        try:
            preview_url = "" if is_existing else await self._get_preview_url(folder_name)
            self.success_count['existing' if is_existing else 'new'] += 1
            return ArtistPreview(
                name=folder_name.strip('[]'),
                folder=folder_name,
                preview_url=preview_url,
                files=files,
                is_existing=is_existing
            )
        except Exception as e:
            self.failed_count['existing' if is_existing else 'new'] += 1
            logger.error(f"处理{artist_type}画师 {folder_name} 时发生错误: {e}")
            return ArtistPreview(
                name=folder_name.strip('[]'),
                folder=folder_name,
                preview_url="",
                files=files,
                is_existing=is_existing
            )

    async def process_yaml(self, yaml_path: str) -> Tuple[List[ArtistPreview], List[ArtistPreview]]:
        """处理yaml文件，返回新旧画师预览信息"""
        logger.info(f"开始处理YAML文件: {yaml_path}")
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            existing_artists = data['artists']['existing_artists']
            new_artists = data['artists']['new_artists']
            
            logger.info(f"读取到 {len(existing_artists)} 个已存在画师, {len(new_artists)} 个新画师")
            logger.debug(f"新画师列表: {list(new_artists.keys())}")
            
            existing_tasks = [
                self.process_artist(folder, files, True)
                for folder, files in existing_artists.items()
            ]
            
            new_tasks = [
                self.process_artist(folder, files, False)
                for folder, files in new_artists.items()
            ]
            
            self.total_tasks = len(existing_tasks) + len(new_tasks)
            logger.info(f"总任务数: {self.total_tasks}")
            
            logger.info("开始异步处理所有画师信息")
            existing_previews = await asyncio.gather(*existing_tasks)
            new_previews = await asyncio.gather(*new_tasks)
            
            logger.info(f"""处理完成统计:
            已存在画师: 处理 {self.processed_count['existing']} 个, 成功 {self.success_count['existing']} 个, 失败 {self.failed_count['existing']} 个
            新画师: 处理 {self.processed_count['new']} 个, 成功 {self.success_count['new']} 个, 失败 {self.failed_count['new']} 个""")
            
            return existing_previews, new_previews
            
        except Exception as e:
            logger.error(f"处理YAML文件时发生错误: {e}")
            raise

    def generate_html(self, existing_previews: List[ArtistPreview], 
                     new_previews: List[ArtistPreview], 
                     output_path: str):
        """生成HTML预览页面"""
        try:
            logger.info("开始生成HTML预览页面")
            
            # 生成HTML内容
            html_content = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>画师预览</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/select/1.7.0/css/select.dataTables.min.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            padding-top: 60px;
        }
        .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #fff;
            padding: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 1000;
            text-align: center;
        }
        .btn {
            background-color: #4CAF50;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 0 5px;
        }
        .btn:hover {
            background-color: #45a049;
        }
        .import-container {
            margin: 20px 0;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        .import-textarea {
            width: 100%;
            height: 100px;
            margin-bottom: 10px;
            padding: 8px;
        }
        table {
            width: 100% !important;
            margin-bottom: 20px;
        }
        .preview-img {
            max-width: 150px;
            max-height: 150px;
            display: block;
            margin: 0 auto;
        }
        .files-list {
            margin: 0;
            padding: 0;
            list-style: none;
            max-height: 150px;
            overflow-y: auto;
        }
        .files-list li {
            margin: 2px 0;
        }
        .preview-cell {
            width: 150px;
            text-align: center;
        }
        .name-cell {
            width: 200px;
        }
        .checkbox-cell {
            width: 50px;
            text-align: center;
        }
        .collapsible {
            background-color: #f1f1f1;
            color: #444;
            cursor: pointer;
            padding: 18px;
            width: 100%;
            border: none;
            text-align: left;
            outline: none;
            font-size: 15px;
            margin-bottom: 10px;
        }
        .active, .collapsible:hover {
            background-color: #ddd;
        }
        .content {
            display: none;
            overflow: hidden;
        }
        .checkbox-container {
            margin: 10px 0;
        }
        .dataTables_wrapper {
            margin-bottom: 20px;
        }
        .dataTables_length, .dataTables_filter {
            margin-bottom: 10px;
        }
        .paginate_button {
            padding: 5px 10px;
            margin: 0 2px;
            border: 1px solid #ddd;
            cursor: pointer;
        }
        .paginate_button.current {
            background: #4CAF50;
            color: white;
            border-color: #4CAF50;
        }
        .import-methods {
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }
        .text-import, .file-import {
            flex: 1;
        }
        .preview-container {
            position: relative;
            display: inline-block;
        }
        .preview-actions {
            position: absolute;
            bottom: 5px;
            right: 5px;
            display: flex;
            gap: 5px;
            background: rgba(255, 255, 255, 0.8);
            padding: 3px;
            border-radius: 4px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .preview-container:hover .preview-actions {
            opacity: 1;
        }
        .btn-small {
            padding: 2px 5px;
            font-size: 12px;
            cursor: pointer;
            background: white;
            border: 1px solid #ddd;
            border-radius: 3px;
        }
        .btn-small:hover {
            background: #f0f0f0;
        }
        .back-to-top {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 40px;
            height: 40px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.7;
            transition: opacity 0.3s;
            z-index: 1000;
        }
        .back-to-top:hover {
            opacity: 1;
        }
        .select-all-container {
            padding: 10px;
            background: #f5f5f5;
            border-radius: 4px;
            margin: 10px 0;
        }
        .select-all-label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
        }
        .select-all-label input[type="checkbox"] {
            width: 18px;
            height: 18px;
        }
        .checkbox-cell {
            cursor: pointer;
        }
        .checkbox-cell input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
    </style>
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script type="text/javascript" src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <script type="text/javascript" src="https://cdn.datatables.net/select/1.7.0/js/dataTables.select.min.js"></script>
</head>
<body>
    <div class="fixed-header">
        <button class="btn" onclick="exportSelected('artists')">导出选中画师</button>
        <button class="btn" onclick="exportSelected('files')">导出选中压缩包</button>
        <button class="btn" onclick="selectNoPreviewArtists()">选中无预览画师</button>
    </div>

    <div class="import-container">
        <h3>导入画师列表</h3>
        <div class="import-methods">
            <div class="text-import">
                <textarea id="artist-import" class="import-textarea" placeholder="每行一个画师名称"></textarea>
                <button class="btn" onclick="importArtists()">导入并选中</button>
            </div>
            <div class="file-import">
                <input type="file" id="file-import" accept=".txt" style="display: none;">
                <button class="btn" onclick="document.getElementById('file-import').click()">从文件导入</button>
            </div>
        </div>
    </div>

    <h2>已存在画师</h2>
    <button type="button" class="collapsible">显示/隐藏已存在画师 (已全选)</button>
    <div class="content">
        <div class="select-all-container">
            <label class="select-all-label">
                <input type="checkbox" id="existing-select-all" checked>
                <span>全选/取消全选</span>
            </label>
        </div>
        <table id="existing-table" class="display">
            <thead>
                <tr>
                    <th class="checkbox-cell">选择</th>
                    <th class="name-cell">画师名</th>
                    <th>文件列表</th>
                </tr>
            </thead>
            <tbody>'''

            # 添加已存在画师
            for preview in existing_previews:
                files_html = '\n'.join(f'<li>{file}</li>' for file in preview.files)
                html_content += f'''
                <tr>
                    <td class="checkbox-cell" onclick="toggleCheckbox(event)"><input type="checkbox" checked></td>
                    <td class="name-cell">{preview.folder}</td>
                    <td><ul class="files-list">{files_html}</ul></td>
                </tr>'''

            html_content += '''
            </tbody>
        </table>
    </div>

    <h2>新画师</h2>
    <div class="checkbox-container">
        <input type="checkbox" id="new-select-all">
        <label for="new-select-all">全选/取消全选</label>
    </div>
    <table id="new-table" class="display">
        <thead>
            <tr>
                <th class="checkbox-cell">选择</th>
                <th class="preview-cell">预览图</th>
                <th class="name-cell">画师名</th>
                <th>文件列表</th>
            </tr>
        </thead>
        <tbody>'''

            # 添加新画师
            for preview in new_previews:
                files_html = '\n'.join(f'<li>{file}</li>' for file in preview.files)
                preview_img = f'<img src="{preview.preview_url}" class="preview-img" loading="lazy">' if preview.preview_url else '<span>无预览图</span>'
                
                html_content += f'''
            <tr data-artist="{preview.folder}">
                <td class="checkbox-cell" onclick="toggleCheckbox(event)"><input type="checkbox"></td>
                <td class="preview-cell">
                    <div class="preview-container">
                        {preview_img}
                        <div class="preview-actions">
                            <button class="btn-small" onclick="reloadPreview(this, '{preview.folder}')" title="重新加载预览">🔄</button>
                            <a href="https://www.wn01.uk/search/?q={preview.folder}" class="btn-small" target="_blank" title="在网站查看">🔍</a>
                        </div>
                    </div>
                </td>
                <td class="name-cell">{preview.folder}</td>
                <td><ul class="files-list">{files_html}</ul></td>
            </tr>'''

            html_content += '''
        </tbody>
    </table>

    <script>
        $(document).ready(function() {
            // 回到顶部按钮
            const backToTop = $('<button>')
                .addClass('back-to-top')
                .html('⬆')
                .hide()
                .appendTo('body');
            
            $(window).scroll(function() {
                if ($(this).scrollTop() > 300) {
                    backToTop.fadeIn();
                } else {
                    backToTop.fadeOut();
                }
            });
            
            backToTop.click(function() {
                $('html, body').animate({scrollTop: 0}, 500);
            });
            
            // 初始化DataTables
            $('#existing-table').DataTable({
                pageLength: 25,
                lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "全部"]],
                drawCallback: function() {
                    $('html, body').animate({scrollTop: 0}, 300);
                },
                language: {
                    "sProcessing": "处理中...",
                    "sLengthMenu": "显示 _MENU_ 项结果",
                    "sZeroRecords": "没有匹配结果",
                    "sInfo": "显示第 _START_ 至 _END_ 项结果，共 _TOTAL_ 项",
                    "sInfoEmpty": "显示第 0 至 0 项结果，共 0 项",
                    "sInfoFiltered": "(由 _MAX_ 项结果过滤)",
                    "sInfoPostFix": "",
                    "sSearch": "搜索:",
                    "sUrl": "",
                    "sEmptyTable": "表中数据为空",
                    "sLoadingRecords": "载入中...",
                    "sInfoThousands": ",",
                    "oPaginate": {
                        "sFirst": "首页",
                        "sPrevious": "上页",
                        "sNext": "下页",
                        "sLast": "末页"
                    }
                }
            });

            $('#new-table').DataTable({
                pageLength: 25,
                lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "全部"]],
                drawCallback: function() {
                    $('html, body').animate({scrollTop: 0}, 300);
                },
                language: {
                    "sProcessing": "处理中...",
                    "sLengthMenu": "显示 _MENU_ 项结果",
                    "sZeroRecords": "没有匹配结果",
                    "sInfo": "显示第 _START_ 至 _END_ 项结果，共 _TOTAL_ 项",
                    "sInfoEmpty": "显示第 0 至 0 项结果，共 0 项",
                    "sInfoFiltered": "(由 _MAX_ 项结果过滤)",
                    "sInfoPostFix": "",
                    "sSearch": "搜索:",
                    "sUrl": "",
                    "sEmptyTable": "表中数据为空",
                    "sLoadingRecords": "载入中...",
                    "sInfoThousands": ",",
                    "oPaginate": {
                        "sFirst": "首页",
                        "sPrevious": "上页",
                        "sNext": "下页",
                        "sLast": "末页"
                    }
                }
            });
        });

        // 折叠面板功能
        var coll = document.getElementsByClassName("collapsible");
        for (var i = 0; i < coll.length; i++) {
            coll[i].addEventListener("click", function() {
                this.classList.toggle("active");
                var content = this.nextElementSibling;
                if (content.style.display === "block") {
                    content.style.display = "none";
                } else {
                    content.style.display = "block";
                }
            });
        }

        // 全选功能
        function setupSelectAll(tableId, selectAllId) {
            const selectAll = document.getElementById(selectAllId);
            const table = document.getElementById(tableId);
            if (!selectAll || !table) return;

            // 创建一个额外的全选按钮容器
            const selectAllContainer = document.querySelector(`#${tableId}_wrapper .select-all-container`);
            if (!selectAllContainer) return;
            
            // 添加当前页全选和全部全选按钮
            const selectAllButtonsHTML = `
                <div class="select-buttons" style="margin-top: 8px; display: flex; gap: 10px;">
                    <button class="btn" style="font-size: 12px; padding: 5px 10px;" id="${tableId}-select-page">当前页全选</button>
                    <button class="btn" style="font-size: 12px; padding: 5px 10px;" id="${tableId}-select-all-pages">全部页全选</button>
                    <button class="btn" style="font-size: 12px; padding: 5px 10px;" id="${tableId}-deselect-all">全部取消选择</button>
                </div>
            `;
            
            selectAllContainer.insertAdjacentHTML('beforeend', selectAllButtonsHTML);
            
            // 当前页全选按钮事件
            document.getElementById(`${tableId}-select-page`).addEventListener('click', function() {
                const dataTable = $(`#${tableId}`).DataTable();
                const visibleRows = dataTable.rows({ page: 'current' }).nodes();
                
                for (let i = 0; i < visibleRows.length; i++) {
                    const checkbox = visibleRows[i].querySelector('input[type="checkbox"]');
                    if (checkbox) checkbox.checked = true;
                }
                
                // 更新全选复选框状态
                updatePageSelectAllStatus(tableId, selectAllId);
            });
            
            // 全部页全选按钮事件
            document.getElementById(`${tableId}-select-all-pages`).addEventListener('click', function() {
                const dataTable = $(`#${tableId}`).DataTable();
                const allRows = dataTable.rows().nodes();
                
                for (let i = 0; i < allRows.length; i++) {
                    const checkbox = allRows[i].querySelector('input[type="checkbox"]');
                    if (checkbox) checkbox.checked = true;
                }
                
                // 更新全选复选框状态
                selectAll.checked = true;
            });
            
            // 全部取消选择按钮事件
            document.getElementById(`${tableId}-deselect-all`).addEventListener('click', function() {
                const dataTable = $(`#${tableId}`).DataTable();
                const allRows = dataTable.rows().nodes();
                
                for (let i = 0; i < allRows.length; i++) {
                    const checkbox = allRows[i].querySelector('input[type="checkbox"]');
                    if (checkbox) checkbox.checked = false;
                }
                
                // 更新全选复选框状态
                selectAll.checked = false;
            });

            // 原有的全选/取消全选复选框功能修改为当前页全选
            selectAll.addEventListener('change', function() {
                const dataTable = $(`#${tableId}`).DataTable();
                const visibleRows = dataTable.rows({ page: 'current' }).nodes();
                
                for (let i = 0; i < visibleRows.length; i++) {
                    const checkbox = visibleRows[i].querySelector('input[type="checkbox"]');
                    if (checkbox) checkbox.checked = this.checked;
                }
            });

            // 页面变化时更新全选复选框状态
            $(`#${tableId}`).on('page.dt', function() {
                setTimeout(function() {
                    updatePageSelectAllStatus(tableId, selectAllId);
                }, 100);
            });

            // 行选择变化时更新全选复选框状态
            table.addEventListener('change', function(e) {
                if (e.target.type === 'checkbox' && e.target !== selectAll) {
                    updatePageSelectAllStatus(tableId, selectAllId);
                }
            });
        }

        // 更新当前页全选复选框状态
        function updatePageSelectAllStatus(tableId, selectAllId) {
            const selectAll = document.getElementById(selectAllId);
            if (!selectAll) return;

            const dataTable = $(`#${tableId}`).DataTable();
            const visibleRows = dataTable.rows({ page: 'current' }).nodes();
            const allChecked = Array.from(visibleRows).every(row => {
                const checkbox = row.querySelector('input[type="checkbox"]');
                return checkbox && checkbox.checked;
            });
            
            selectAll.checked = allChecked;
        }

        // 添加"当前页全选"功能到新画师表格
        document.addEventListener('DOMContentLoaded', function() {
            // 先修改已存在画师表格的全选容器
            if (!document.querySelector('#existing-table_wrapper .select-all-container')) {
                const existingSelectAllLabel = document.querySelector('label[for="existing-select-all"]').parentNode;
                if (existingSelectAllLabel) {
                    existingSelectAllLabel.className = 'select-all-container';
                }
            }
            
            // 再修改新画师表格的全选容器
            const newSelectAllContainer = document.querySelector('.checkbox-container');
            if (newSelectAllContainer) {
                newSelectAllContainer.className = 'select-all-container';
                newSelectAllContainer.innerHTML = `
                    <label class="select-all-label">
                        <input type="checkbox" id="new-select-all">
                        <span>全选/取消全选</span>
                    </label>
                `;
            }
            
            // 设置全选功能
            setupSelectAll('existing-table', 'existing-select-all');
            setupSelectAll('new-table', 'new-select-all');
            
            // 内容面板初始显示
            const content = document.querySelector('.content');
            if (content) {
                content.style.display = 'block';
            }
        });

        // 导出功能
        function exportSelected(type) {
            let content = [];
            
            // 获取已存在画师表格中选中的内容
            const existingTable = $('#existing-table').DataTable();
            existingTable.rows().every(function() {
                const row = this.node();
                const checkbox = row.querySelector('input[type="checkbox"]');
                if (checkbox && checkbox.checked) {
                    if (type === 'artists') {
                        const artistName = row.querySelector('.name-cell').textContent.trim();
                        content.push(artistName);
                    } else if (type === 'files') {
                        const filesList = row.querySelector('.files-list').querySelectorAll('li');
                        filesList.forEach(li => content.push(li.textContent.trim()));
                    }
                }
            });
            
            // 获取新画师表格中选中的内容
            const newTable = $('#new-table').DataTable();
            newTable.rows().every(function() {
                const row = this.node();
                const checkbox = row.querySelector('input[type="checkbox"]');
                if (checkbox && checkbox.checked) {
                    if (type === 'artists') {
                        const artistName = row.querySelector('.name-cell').textContent.trim();
                        content.push(artistName);
                    } else if (type === 'files') {
                        const filesList = row.querySelector('.files-list').querySelectorAll('li');
                        filesList.forEach(li => content.push(li.textContent.trim()));
                    }
                }
            });
            
            // 创建并下载文件
            if (content.length > 0) {
                const blob = new Blob([content.join('\\n')], { type: 'text/plain' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = type === 'artists' ? 'selected_artists.txt' : 'selected_files.txt';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            } else {
                alert('请先选择要导出的内容！');
            }
        }

        // 导入画师列表
        function importArtists() {
            const textarea = document.getElementById('artist-import');
            const artists = textarea.value.trim().split('\\n').map(name => name.trim()).filter(name => name);
            
            if (artists.length === 0) {
                alert('请输入画师名称！');
                return;
            }

            // 处理已存在画师表格
            const existingTable = $('#existing-table').DataTable();
            existingTable.rows().every(function() {
                const row = this.node();
                const nameCell = row.querySelector('.name-cell');
                const checkbox = row.querySelector('input[type="checkbox"]');
                if (nameCell && checkbox) {
                    const artistName = nameCell.textContent.trim();
                    checkbox.checked = artists.some(name => 
                        artistName.toLowerCase().includes(name.toLowerCase())
                    );
                }
            });

            // 处理新画师表格
            const newTable = $('#new-table').DataTable();
            newTable.rows().every(function() {
                const row = this.node();
                const nameCell = row.querySelector('.name-cell');
                const checkbox = row.querySelector('input[type="checkbox"]');
                if (nameCell && checkbox) {
                    const artistName = nameCell.textContent.trim();
                    checkbox.checked = artists.some(name => 
                        artistName.toLowerCase().includes(name.toLowerCase())
                    );
                }
            });

            // 更新全选复选框状态
            updateSelectAllStatus('existing-table', 'existing-select-all');
            updateSelectAllStatus('new-table', 'new-select-all');
        }

        function updateSelectAllStatus(tableId, selectAllId) {
            const table = document.getElementById(tableId);
            const selectAll = document.getElementById(selectAllId);
            if (!table || !selectAll) return;

            const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            selectAll.checked = allChecked;
        }

        // 选中无预览画师
        function selectNoPreviewArtists() {
            const newTable = $('#new-table').DataTable();
            newTable.rows().every(function() {
                const row = this.node();
                const previewCell = row.querySelector('.preview-cell');
                const noPreview = previewCell.querySelector('span');
                if (noPreview && noPreview.textContent === '无预览图') {
                    const checkbox = row.querySelector('input[type="checkbox"]');
                    if (checkbox) checkbox.checked = true;
                }
            });

            // 更新全选复选框状态
            updateSelectAllStatus('new-table', 'new-select-all');
        }

        // 文件导入功能
        document.getElementById('file-import').addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('artist-import').value = e.target.result;
                    importArtists();
                };
                reader.readAsText(file);
            }
        });

        // 重新加载预览图
        async function reloadPreview(button, artistName) {
            const cell = button.closest('.preview-cell');
            const img = cell.querySelector('img');
            const span = cell.querySelector('span');
            
            button.disabled = true;
            button.textContent = '⌛';
            
            try {
                // 构造搜索URL
                const searchTerm = artistName.replace(' ', '+');
                const searchUrl = `https://www.wn01.uk/search/?q=${searchTerm}`;
                
                // 获取预览图
                const response = await fetch(searchUrl);
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                
                const galleryItems = doc.querySelectorAll('.gallary_item');
                let found = false;
                
                for (const item of galleryItems) {
                    const imgElement = item.querySelector('img');
                    if (imgElement && imgElement.src) {
                        const imgUrl = imgElement.src.startsWith('https:') ? 
                            imgElement.src : 'https:' + imgElement.src;
                            
                        // 验证图片URL是否有效
                        const imgResponse = await fetch(imgUrl, { method: 'HEAD' });
                        if (imgResponse.ok) {
                            if (img) {
                                img.src = imgUrl;
                            } else if (span) {
                                const newImg = document.createElement('img');
                                newImg.src = imgUrl;
                                newImg.className = 'preview-img';
                                newImg.loading = 'lazy';
                                span.replaceWith(newImg);
                            }
                            found = true;
                            break;
                        }
                    }
                }
                
                if (!found) {
                    if (img) {
                        const newSpan = document.createElement('span');
                        newSpan.textContent = '无预览图';
                        img.replaceWith(newSpan);
                    }
                }
                
                button.textContent = '✓';
                setTimeout(() => {
                    button.textContent = '🔄';
                    button.disabled = false;
                }, 1000);
                
            } catch (error) {
                console.error('重新加载预览图失败:', error);
                button.textContent = '❌';
                setTimeout(() => {
                    button.textContent = '🔄';
                    button.disabled = false;
                }, 1000);
            }
        }

        // 点击单元格切换复选框状态
        function toggleCheckbox(event) {
            const checkbox = event.currentTarget.querySelector('input[type="checkbox"]');
            if (checkbox && event.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                // 触发change事件以更新全选状态
                const changeEvent = new Event('change', { bubbles: true });
                checkbox.dispatchEvent(changeEvent);
            }
        }
    </script>
</body>
</html>'''

            # 保存HTML文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"预览页面已成功生成: {output_path}")
        except Exception as e:
            logger.error(f"生成HTML预览页面时发生错误: {e}")
            raise

async def generate_preview_tables(yaml_path: str, output_path: str = None):
    """生成画师预览表格的主函数"""
    if output_path is None:
        output_path = Path(yaml_path).parent / 'artistpreview.html'
    
    generator = ArtistPreviewGenerator()
    async with generator:
        # 处理yaml文件
        existing_previews, new_previews = await generator.process_yaml(yaml_path)
        
        # 生成HTML页面
        generator.generate_html(existing_previews, new_previews, output_path)

if __name__ == "__main__":
    import argparse
    
    # 设置日志
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='生成画师预览表格')
    parser.add_argument('--test', action='store_true', help='使用测试数据')
    parser.add_argument('--yaml', type=str, help='YAML文件路径')
    args = parser.parse_args()
    
    # 确定YAML文件路径
    if args.test:
        yaml_path = str(Path(__file__).parent / 'test_data.yaml')
        print(f"使用测试数据: {yaml_path}")
    elif args.yaml:
        yaml_path = args.yaml
    else:
        # 默认yaml路径
        default_yaml = r"d:\1VSCODE\GlowToolBox\src\scripts\comic\classify\classified_result.yaml"
        
        # 如果默认文件不存在，提示输入
        if not os.path.exists(default_yaml):
            print(f"默认文件不存在: {default_yaml}")
            yaml_path = input("请输入yaml文件路径（直接回车使用默认路径）: ").strip()
            if not yaml_path:
                yaml_path = default_yaml
        else:
            yaml_path = default_yaml
    
    # 检查文件是否存在
    if not os.path.exists(yaml_path):
        print(f"文件不存在: {yaml_path}")
        sys.exit(1)
    
    # 设置输出路径
    output_path = Path(yaml_path).parent / 'artistpreview.html'
    
    print(f"处理文件: {yaml_path}")
    print(f"输出文件: {output_path}")
    
    try:
        # 安装依赖
        try:
            import aiohttp
            import jinja2
        except ImportError:
            print("正在安装必要的依赖...")
            os.system("pip install aiohttp beautifulsoup4 jinja2")
            import aiohttp
            import jinja2
        
        # 运行生成器
        asyncio.run(generate_preview_tables(yaml_path, str(output_path)))
        print(f"预览页面已生成: {output_path}")
        print(f"请在浏览器中打开预览页面: {output_path}")
        
    except Exception as e:
        print(f"生成预览页面时出错: {e}")
        if input("是否显示详细错误信息？(y/n): ").lower() == 'y':
            import traceback
            traceback.print_exc() 