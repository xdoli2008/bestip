#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL获取模块
从远程URL获取IP列表，支持多URL、重试、编码兼容
"""

import urllib.request
import urllib.error
import time
import sys
from typing import List, Dict, Optional
from datetime import datetime


class URLFetcher:
    """URL获取器，负责从远程URL获取IP列表"""
    
    def __init__(self, config: Dict = None):
        """
        初始化URL获取器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.timeout = self.config.get('url_timeout', 10)
        self.retry_times = self.config.get('url_retry_times', 2)
        self.retry_delay = self.config.get('url_retry_delay', 1)
        
    def fetch_from_url(self, url: str) -> Optional[List[str]]:
        """
        从单个URL获取IP列表
        
        Args:
            url: 目标URL
            
        Returns:
            IP列表，失败返回None
        """
        for attempt in range(self.retry_times + 1):
            try:
                print(f"  正在获取: {url} (尝试 {attempt + 1}/{self.retry_times + 1})")
                
                # 创建请求
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                
                # 发送请求
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    # 读取内容
                    content = response.read()
                    
                    # 尝试UTF-8解码
                    try:
                        text = content.decode('utf-8')
                    except UnicodeDecodeError:
                        # 降级到GBK（Windows兼容）
                        try:
                            text = content.decode('gbk')
                        except UnicodeDecodeError:
                            # 最后尝试latin-1（通常不会失败）
                            text = content.decode('latin-1')
                    
                    # 解析内容
                    targets = self._parse_content(text)

                    if targets:
                        print(f"  [OK] 成功获取 {len(targets)} 个目标")
                        return targets
                    else:
                        print(f"  [WARN] URL内容为空")
                        return []

            except urllib.error.HTTPError as e:
                print(f"  [ERROR] HTTP错误 {e.code}: {e.reason}")
            except urllib.error.URLError as e:
                print(f"  [ERROR] URL错误: {e.reason}")
            except Exception as e:
                print(f"  [ERROR] 未知错误: {str(e)}")

            # 如果不是最后一次尝试，等待后重试
            if attempt < self.retry_times:
                time.sleep(self.retry_delay)

        # 所有尝试都失败
        print(f"  [FAIL] 获取失败，已重试 {self.retry_times} 次")
        return None
    
    def fetch_from_urls(self, urls: List[str]) -> List[str]:
        """
        从多个URL获取IP列表并合并
        
        Args:
            urls: URL列表
            
        Returns:
            合并后的IP列表（去重）
        """
        if not urls:
            print("警告: 未配置URL列表")
            return []
        
        print(f"\n开始从 {len(urls)} 个URL获取IP列表...")
        print("=" * 80)
        
        all_targets = []
        success_count = 0
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] 处理URL:")
            targets = self.fetch_from_url(url)
            
            if targets is not None:
                success_count += 1
                all_targets.extend(targets)
        
        print("\n" + "=" * 80)
        print(f"URL获取完成: 成功 {success_count}/{len(urls)}")
        
        # 去重（保持顺序）
        unique_targets = []
        seen = set()
        for target in all_targets:
            if target not in seen:
                seen.add(target)
                unique_targets.append(target)
        
        if len(all_targets) != len(unique_targets):
            print(f"去重: {len(all_targets)} -> {len(unique_targets)} 个目标")
        
        return unique_targets
    
    def _parse_content(self, text: str) -> List[str]:
        """
        解析文本内容，提取IP列表
        
        Args:
            text: 文本内容
            
        Returns:
            IP列表
        """
        targets = []
        
        for line in text.splitlines():
            line = line.strip()
            # 跳过空行和注释行
            if line and not line.startswith('#'):
                targets.append(line)
        
        return targets


def fetch_targets_from_urls(urls: List[str], config: Dict = None) -> List[str]:
    """
    便捷函数：从URL列表获取目标
    
    Args:
        urls: URL列表
        config: 配置字典
        
    Returns:
        目标列表
    """
    fetcher = URLFetcher(config)
    return fetcher.fetch_from_urls(urls)
