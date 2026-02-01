#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 信息查询客户端
使用 ipinfo.dkly.net API 获取 IP 地理位置、代理类型等信息
"""

import urllib.request
import json
import time
import threading
from typing import Dict, Optional, List
from datetime import datetime, timedelta


class IPInfoClient:
    """IP 信息查询客户端"""

    def __init__(self, api_key: str, config: Dict = None):
        """
        初始化 IP 信息查询客户端

        Args:
            api_key: API 密钥
            config: 配置字典
        """
        self.api_key = api_key
        self.config = config or {}
        self.base_url = "https://ipinfo.dkly.net/api/"

        # 请求限流配置（60请求/分钟）
        self.rate_limit = self.config.get('ipinfo_rate_limit', 60)
        self.rate_window = 60  # 时间窗口（秒）

        # 请求记录（用于限流）
        self.request_times = []
        self.request_lock = threading.Lock()

        # 缓存配置
        self.enable_cache = self.config.get('ipinfo_enable_cache', True)
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.cache_ttl = self.config.get('ipinfo_cache_ttl', 3600)  # 缓存1小时

        # 超时配置
        self.timeout = self.config.get('ipinfo_timeout', 10)

        # 重试配置
        self.max_retries = self.config.get('ipinfo_max_retries', 3)
        self.retry_delay = self.config.get('ipinfo_retry_delay', 1)

    def _wait_for_rate_limit(self):
        """等待满足速率限制"""
        with self.request_lock:
            now = time.time()

            # 清理过期的请求记录
            self.request_times = [t for t in self.request_times if now - t < self.rate_window]

            # 如果达到速率限制，等待
            if len(self.request_times) >= self.rate_limit:
                oldest_request = self.request_times[0]
                wait_time = self.rate_window - (now - oldest_request)
                if wait_time > 0:
                    time.sleep(wait_time + 0.1)  # 额外等待0.1秒确保安全
                    # 重新清理
                    now = time.time()
                    self.request_times = [t for t in self.request_times if now - t < self.rate_window]

            # 记录本次请求时间
            self.request_times.append(time.time())

    def _get_from_cache(self, ip: str) -> Optional[Dict]:
        """从缓存获取数据"""
        if not self.enable_cache:
            return None

        with self.cache_lock:
            if ip in self.cache:
                cached_data, cached_time = self.cache[ip]
                # 检查缓存是否过期
                if time.time() - cached_time < self.cache_ttl:
                    return cached_data
                else:
                    # 删除过期缓存
                    del self.cache[ip]

        return None

    def _save_to_cache(self, ip: str, data: Dict):
        """保存数据到缓存"""
        if not self.enable_cache:
            return

        with self.cache_lock:
            self.cache[ip] = (data, time.time())

    def _make_request(self, ip: str = None) -> Optional[Dict]:
        """
        发起 API 请求

        Args:
            ip: IP 地址，如果为 None 则查询请求者自己的 IP

        Returns:
            API 响应数据，失败返回 None
        """
        # 等待满足速率限制
        self._wait_for_rate_limit()

        # 构建请求 URL
        if ip:
            url = f"{self.base_url}?ip={ip}"
        else:
            url = self.base_url

        # 构建请求
        req = urllib.request.Request(url)
        req.add_header('X-API-Key', self.api_key)
        req.add_header('User-Agent', 'BestIP/1.0')

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8') if e.fp else str(e)
            if e.code == 401:
                print(f"[ERROR] API 认证失败: API Key 无效")
            elif e.code == 429:
                print(f"[WARNING] API 请求过于频繁，已达到速率限制")
            elif e.code == 400:
                print(f"[ERROR] 无效的 IP 地址: {ip}")
            else:
                print(f"[ERROR] API 请求失败 (HTTP {e.code}): {error_msg}")
            return None
        except urllib.error.URLError as e:
            print(f"[ERROR] 网络请求失败: {e.reason}")
            return None
        except Exception as e:
            print(f"[ERROR] 请求异常: {e}")
            return None

    def query_ip(self, ip: str, use_cache: bool = True) -> Optional[Dict]:
        """
        查询单个 IP 的信息

        Args:
            ip: IP 地址
            use_cache: 是否使用缓存

        Returns:
            IP 信息字典，失败返回 None
        """
        # 尝试从缓存获取
        if use_cache:
            cached_data = self._get_from_cache(ip)
            if cached_data:
                return cached_data

        # 重试机制
        for attempt in range(self.max_retries):
            data = self._make_request(ip)

            if data:
                # 保存到缓存
                self._save_to_cache(ip, data)
                return data

            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))

        return None

    def query_batch(self, ips: List[str], use_cache: bool = True) -> Dict[str, Optional[Dict]]:
        """
        批量查询 IP 信息（串行，遵守速率限制）

        Args:
            ips: IP 地址列表
            use_cache: 是否使用缓存

        Returns:
            IP 到信息的映射字典
        """
        results = {}

        for ip in ips:
            results[ip] = self.query_ip(ip, use_cache=use_cache)

        return results

    def extract_location_info(self, data: Dict) -> Dict:
        """
        从 API 响应中提取地理位置信息

        Args:
            data: API 响应数据

        Returns:
            地理位置信息字典
        """
        if not data:
            return {}

        return {
            'country': data.get('country', ''),
            'region': data.get('region', ''),
            'city': data.get('city', ''),
            'continent': data.get('continent', ''),
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude'),
            'timezone': data.get('timezone', {}).get('id', ''),
        }

    def extract_network_info(self, data: Dict) -> Dict:
        """
        从 API 响应中提取网络信息

        Args:
            data: API 响应数据

        Returns:
            网络信息字典
        """
        if not data:
            return {}

        return {
            'asn': data.get('asn', ''),
            'organization': data.get('organization', ''),
            'connection_type': data.get('connection_type', ''),
            'hostname': data.get('hostname', ''),
        }

    def extract_security_info(self, data: Dict) -> Dict:
        """
        从 API 响应中提取安全信息

        Args:
            data: API 响应数据

        Returns:
            安全信息字典
        """
        if not data:
            return {}

        return {
            'is_vpn': data.get('is_vpn', False),
            'is_proxy': data.get('is_proxy', False),
            'is_tor': data.get('is_tor', False),
            'is_threat': data.get('is_threat', False),
        }

    def get_location_string(self, data: Dict) -> str:
        """
        获取格式化的地理位置字符串

        Args:
            data: API 响应数据

        Returns:
            格式化的地理位置字符串，如 "中国-广东-深圳"
        """
        if not data:
            return "未知"

        location_parts = []

        country = data.get('country', '')
        region = data.get('region', '')
        city = data.get('city', '')

        if country:
            location_parts.append(country)
        if region and region != country:
            location_parts.append(region)
        if city and city != region:
            location_parts.append(city)

        return '-'.join(location_parts) if location_parts else "未知"

    def get_proxy_type_string(self, data: Dict) -> str:
        """
        获取代理类型字符串

        Args:
            data: API 响应数据

        Returns:
            代理类型字符串
        """
        if not data:
            return "未知"

        types = []
        if data.get('is_vpn'):
            types.append('VPN')
        if data.get('is_proxy'):
            types.append('Proxy')
        if data.get('is_tor'):
            types.append('Tor')
        if data.get('is_threat'):
            types.append('Threat')

        return '/'.join(types) if types else "直连"

    def clear_cache(self):
        """清空缓存"""
        with self.cache_lock:
            self.cache.clear()

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        with self.cache_lock:
            return {
                'cache_size': len(self.cache),
                'cache_enabled': self.enable_cache,
                'cache_ttl': self.cache_ttl,
            }


if __name__ == '__main__':
    # 测试代码
    print("=" * 60)
    print("IP 信息查询客户端测试")
    print("=" * 60)

    # 注意：需要替换为真实的 API Key
    api_key = "your_api_key_here"

    # 创建客户端
    client = IPInfoClient(api_key)

    # 测试查询单个 IP
    print("\n1. 查询单个 IP:")
    test_ip = "8.8.8.8"
    data = client.query_ip(test_ip)

    if data:
        print(f"  IP: {test_ip}")
        print(f"  位置: {client.get_location_string(data)}")
        print(f"  类型: {client.get_proxy_type_string(data)}")
        print(f"  组织: {data.get('organization', '未知')}")
    else:
        print("  查询失败")

    # 测试缓存
    print("\n2. 测试缓存:")
    print(f"  缓存统计: {client.get_cache_stats()}")

    print("\nIP 信息查询客户端测试完成！")
