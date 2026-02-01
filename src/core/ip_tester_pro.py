#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级IP/域名质量测试程序
基于专业网络质量评估算法实现，包含延迟、丢包率、抖动、TCP性能测试和综合评分
"""

import subprocess
import re
import time
import sys
import os
import statistics
import socket
import threading
import urllib.request
import json
import ssl
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入新模块
try:
    from src.config.config import load_config, HTTP_TEST_URLS
    from src.analyzers.statistical_analyzer import StatisticalAnalyzer
    from src.analyzers.proxy_score_calculator import ProxyScoreCalculator
    from src.utils.url_fetcher import fetch_targets_from_urls
    from src.utils.ip_info_client import IPInfoClient
except ImportError:
    # 如果导入失败，使用默认值（向后兼容）
    HTTP_TEST_URLS = ['https://cp.cloudflare.com/generate_204']
    StatisticalAnalyzer = None
    ProxyScoreCalculator = None
    IPInfoClient = None
    # URL获取模块向后兼容
    def fetch_targets_from_urls(urls, config=None):
        print("警告: URL获取模块未安装")
        return []
    def load_config(custom_config=None, test_mode=None):
        return custom_config or {}


class AdvancedIPTester:
    HISTORY_VERSION = 1
    def __init__(self, config: Dict = None):
        """
        初始化高级测试器

        Args:
            config: 配置字典，包含测试参数
        """
        self.config = config or {}
        self.ping_count = self.config.get('ping_count', 10)  # 增加ping次数以获得更准确的抖动计算
        self.ping_timeout = self.config.get('ping_timeout', 2)  # ping超时时间（秒）
        self.tcp_timeout = self.config.get('tcp_timeout', 5)  # TCP连接超时时间（秒）
        self.max_workers = self.config.get('max_workers', 10)  # 并发线程数，默认10
        self.print_lock = threading.Lock()  # 打印锁，用于同步输出
        self.results = []

        # 颜色常量 (ANSI)
        self.CLR_G = "\033[92m"  # Green
        self.CLR_Y = "\033[93m"  # Yellow
        self.CLR_R = "\033[91m"  # Red
        self.CLR_B = "\033[94m"  # Blue
        self.CLR_C = "\033[96m"  # Cyan
        self.CLR_0 = "\033[0m"   # Reset
        self.CLR_BOLD = "\033[1m"

        # 新增配置参数
        self.enable_quick_check = self.config.get('enable_quick_check', True)
        self.quick_check_workers = self.config.get('quick_check_workers', 50)
        self.quick_ping_count = self.config.get('quick_ping_count', 1)
        self.quick_ping_timeout = self.config.get('quick_ping_timeout', 1)
        self.quick_tcp_timeout = self.config.get('quick_tcp_timeout', 2)
        self.enable_http_test = self.config.get('enable_http_test', True)
        self.http_test_url = self.config.get('http_test_url', HTTP_TEST_URLS[0])
        self.http_timeout = self.config.get('http_timeout', 10)
        self.score_include_http = self.config.get('score_include_http', True)
        self.enable_stability_test = self.config.get('enable_stability_test', True)
        self.stability_attempts = self.config.get('stability_attempts', 10)

        # 流媒体测试配置（新增）
        self.enable_streaming_test = self.config.get('enable_streaming_test', False)
        self.streaming_sites = self.config.get('streaming_sites', [])
        self.streaming_timeout = self.config.get('streaming_timeout', 15)
        self.streaming_concurrent = self.config.get('streaming_concurrent', True)

        # 输出配置（新增）
        self.max_results = self.config.get('max_results', 30)

        # IP 信息查询客户端（新增）
        self.ipinfo_client = None
        if IPInfoClient and self.config.get('enable_ipinfo', False):
            api_key = self.config.get('ipinfo_api_key', '')
            if api_key and api_key != 'your_api_key_here':
                try:
                    self.ipinfo_client = IPInfoClient(api_key, self.config)
                    print(f"{self.CLR_G}[OK] IP 信息查询服务已启用{self.CLR_0}")
                except Exception as e:
                    print(f"{self.CLR_Y}[WARNING] IP 信息查询服务初始化失败: {e}{self.CLR_0}")
            else:
                print(f"{self.CLR_Y}[提示] IP 信息查询服务未配置 API Key{self.CLR_0}")

    def _get_score_color(self, score: int) -> str:
        """根据评分获取颜色"""
        if score >= 80: return self.CLR_G
        if score >= 60: return self.CLR_Y
        if score >= 40: return self.CLR_B
        return self.CLR_R

    def _get_score_emoji(self, score: int) -> str:
        """根据评分获取 Emoji"""
        if score >= 90: return "🚀"
        if score >= 80: return "✅"
        if score >= 60: return "⚡"
        if score >= 40: return "⚠️"
        return "❌"

    def parse_ping_output_detailed(self, output: str) -> Dict:
        """
        详细解析ping命令输出，提取所有延迟样本和统计信息
        
        Args:
            output: ping命令的输出文本
            
        Returns:
            包含详细统计信息的字典
        """
        result = {
            'delays': [],      # 所有延迟样本（ms）
            'avg_delay': None, # 平均延迟
            'min_delay': None, # 最小延迟
            'max_delay': None, # 最大延迟
            'loss_rate': None, # 丢包率
            'jitter': None,    # 抖动（标准差）
            'success': False   # 是否成功
        }
        
        # 匹配延迟样本行（Windows中文版）
        delay_pattern = r'来自.*的回复.*时间[=<](\d+)ms'
        delays = re.findall(delay_pattern, output)
        
        # 匹配延迟样本行（Windows英文版）
        if not delays:
            delay_pattern = r'Reply from .* time[=<](\d+)ms'
            delays = re.findall(delay_pattern, output)
        
        # 匹配延迟样本行（另一种格式）
        if not delays:
            delay_pattern = r'bytes from .* time[=<](\d+)ms'
            delays = re.findall(delay_pattern, output)
        
        # 转换延迟为浮点数
        if delays:
            result['delays'] = [float(d) for d in delays]
            result['avg_delay'] = statistics.mean(result['delays'])
            result['min_delay'] = min(result['delays'])
            result['max_delay'] = max(result['delays'])
            
            # 计算抖动（标准差）
            if len(result['delays']) > 1:
                result['jitter'] = statistics.stdev(result['delays'])
            else:
                result['jitter'] = 0.0
        
        # 匹配丢包率（Windows中文版）
        loss_pattern = r'丢失 = (\d+)'
        loss_match = re.search(loss_pattern, output)
        if not loss_match:
            loss_pattern = r'Lost = (\d+)'
            loss_match = re.search(loss_pattern, output)
        
        if loss_match:
            lost_packets = int(loss_match.group(1))
            total_packets = self.ping_count
            result['loss_rate'] = (lost_packets / total_packets) * 100.0
        else:
            # 尝试匹配百分比格式
            loss_percent_pattern = r'\((\d+)% 丢失\)'
            loss_percent_match = re.search(loss_percent_pattern, output)
            if not loss_percent_match:
                loss_percent_pattern = r'\((\d+)% loss\)'
                loss_percent_match = re.search(loss_percent_pattern, output)
            
            if loss_percent_match:
                result['loss_rate'] = float(loss_percent_match.group(1))
        
        result['success'] = len(result['delays']) > 0
        
        return result
    
    def test_tcp_connection(self, target: str, port: int = 443) -> Dict:
        """
        测试TCP连接性能
        
        Args:
            target: 目标主机
            port: 测试端口（默认443）
            
        Returns:
            TCP连接测试结果
        """
        result = {
            'success': False,
            'connect_time': None,  # 连接建立时间（ms）
            'error': None
        }
        
        clean_target = self._clean_target(target)
        
        try:
            start_time = time.time()
            
            # 创建socket并设置超时
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.tcp_timeout)
            
            # 尝试连接
            sock.connect((clean_target, port))
            sock.close()
            
            end_time = time.time()
            result['connect_time'] = (end_time - start_time) * 1000  # 转换为ms
            result['success'] = True
            
        except socket.timeout:
            result['error'] = "TCP连接超时"
        except socket.gaierror:
            result['error'] = "无法解析主机名"
        except ConnectionRefusedError:
            result['error'] = "连接被拒绝"
        except Exception as e:
            result['error'] = str(e)

        return result

    def quick_availability_check(self, target: str, port: int = 443) -> Dict:
        """
        快速可用性检测（改进版，提高准确性）

        改进点：
        - 增加ping次数到3次（提高可靠性）
        - 添加重试机制（最多2次重试）
        - 更合理的超时设置

        Args:
            target: 目标主机
            port: 测试端口（默认443）

        Returns:
            快速检测结果
        """
        result = {
            'available': False,
            'quick_delay': None,
            'reason': None
        }

        clean_target = self._clean_target(target)

        # 最多尝试2次（首次+1次重试）
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # 1. Ping测试（3次，超时1.5秒）
                ping_count = 3
                ping_timeout = 1500  # Windows使用毫秒

                if sys.platform == 'win32':
                    cmd = ['ping', '-n', str(ping_count), '-w', str(ping_timeout), clean_target]
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        encoding='gbk',
                        timeout=6  # 总超时：3次 × 1.5秒 + 缓冲
                    )
                else:
                    cmd = ['ping', '-c', str(ping_count), '-W', '1', clean_target]
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=6
                    )

                if process.returncode in [0, 1]:  # 0=成功，1=部分丢包
                    # 提取所有延迟样本
                    delay_pattern = r'时间[=<](\d+)ms|time[=<](\d+)ms'
                    delays = re.findall(delay_pattern, process.stdout)

                    if delays:
                        # 计算平均延迟（提高准确性）
                        delay_values = []
                        for d in delays:
                            delay_val = d[0] if d[0] else d[1]
                            if delay_val:
                                delay_values.append(float(delay_val))

                        if delay_values:
                            result['quick_delay'] = sum(delay_values) / len(delay_values)

                            # 2. TCP连接测试（超时2.5秒）
                            try:
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.settimeout(2.5)
                                sock.connect((clean_target, port))
                                sock.close()
                                result['available'] = True
                                return result  # 成功则立即返回
                            except socket.timeout:
                                result['reason'] = "TCP连接超时"
                            except ConnectionRefusedError:
                                result['reason'] = "TCP连接被拒绝"
                            except Exception as e:
                                result['reason'] = f"TCP连接失败: {str(e)}"
                        else:
                            result['reason'] = "无法提取延迟数据"
                    else:
                        result['reason'] = "Ping无响应"
                else:
                    result['reason'] = "Ping失败"

            except subprocess.TimeoutExpired:
                result['reason'] = "Ping超时"
            except Exception as e:
                result['reason'] = f"检测异常: {str(e)}"

            # 如果第一次失败且还有重试机会，等待0.5秒后重试
            if not result['available'] and attempt < max_attempts - 1:
                time.sleep(0.5)
                continue
            else:
                break

        return result

    def test_http_performance(self, target: str, port: int = 443) -> Dict:
        """
        HTTP/HTTPS性能测试

        Args:
            target: 目标主机
            port: 测试端口（默认443）

        Returns:
            HTTP性能测试结果
        """
        result = {
            'success': False,
            'tls_handshake_time': None,  # TLS握手时间（ms）
            'ttfb': None,  # 首字节时间（ms）
            'total_time': None,  # 响应头接收完成时间（ms）
            'status_code': None,
            'error': None
        }

        try:
            # Cloudflare优选IP场景：连接到目标IP，但用URL里的域名做SNI/Host，测"通过该IP访问站点"的TTFB。
            metrics = self._http_request_via_ip(
                ip=target,
                port=port,
                url=self.http_test_url,
                timeout=self.http_timeout,
            )
            result.update(metrics)

        except urllib.error.HTTPError as e:
            result['status_code'] = e.code
            result['error'] = f"HTTP错误: {e.code}"
        except urllib.error.URLError as e:
            result['error'] = f"URL错误: {str(e.reason)}"
        except socket.timeout:
            result['error'] = "HTTP请求超时"
        except Exception as e:
            result['error'] = str(e)

        return result

    def _http_request_via_ip(self, ip: str, port: int, url: str, timeout: int) -> Dict:
        """
        通过指定IP建立连接，并以URL中的域名作为SNI/Host发送HTTP请求。

        适用于 Cloudflare 优选 IP：同一个站点(域名)可以通过不同的边缘IP接入，
        这里强制连到指定IP以评估该IP的应用层延迟（TTFB）。

        注意：这测的是"本机 -> 目标IP(边缘) -> 站点响应"的端到端时间，
        不是在目标IP上真实发起的"IP到站点"网络路径。
        """
        parsed = urlparse(url)
        scheme = (parsed.scheme or 'https').lower()
        host = parsed.hostname
        if not host:
            return {
                'success': False,
                'tls_handshake_time': None,
                'ttfb': None,
                'total_time': None,
                'status_code': None,
                'error': f'无效URL: {url}'
            }

        path = parsed.path or '/'
        if parsed.query:
            path = f"{path}?{parsed.query}"

        # 端口使用目标的端口（来自目标IP:port），URL里若显式指定端口则仅作为参考。
        connect_port = port or (443 if scheme == 'https' else 80)

        # 仅测响应头，避免下载大内容导致时间不稳定。
        max_header_bytes = 16 * 1024

        result = {
            'success': False,
            'tls_handshake_time': None,
            'ttfb': None,
            'total_time': None,
            'status_code': None,
            'error': None,
        }

        sock = None
        try:
            start_time = time.time()

            sock = socket.create_connection((ip, connect_port), timeout=timeout)
            sock.settimeout(timeout)

            tls_start = time.time()
            if scheme == 'https':
                # 这里使用URL域名做SNI，证书校验默认开启（更能反映真实可用性）。
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)
                tls_end = time.time()
                result['tls_handshake_time'] = (tls_end - tls_start) * 1000
            else:
                tls_end = tls_start

            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "User-Agent: bestip/2.x\r\n"
                "Accept: */*\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode('ascii', errors='ignore')
            sock.sendall(req)

            # 读到首字节
            first_chunk = sock.recv(1)
            if not first_chunk:
                result['error'] = "无响应数据"
                return result

            first_byte_time = time.time()
            result['ttfb'] = (first_byte_time - start_time) * 1000

            # 继续读取到响应头结束（\r\n\r\n），用于更稳定的"total_time"
            buf = bytearray(first_chunk)
            while len(buf) < max_header_bytes and b"\r\n\r\n" not in buf:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf.extend(chunk)

            end_time = time.time()
            result['total_time'] = (end_time - start_time) * 1000

            # 解析状态码
            try:
                header_text = bytes(buf).split(b"\r\n", 1)[0].decode('ascii', errors='ignore')
                # e.g. HTTP/1.1 200 OK
                parts = header_text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    result['status_code'] = int(parts[1])
            except Exception:
                pass

            result['success'] = True
            return result

        except ssl.SSLError as e:
            result['error'] = f"TLS错误: {e}"
            return result
        except socket.timeout:
            result['error'] = "连接超时"
            return result
        except Exception as e:
            result['error'] = str(e)
            return result
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass

    def test_streaming_sites(self, target: str, port: int = 443) -> Dict:
        """
        测试流媒体网站连通性和延迟

        Cloudflare优选IP场景：对每个站点URL，连接到目标IP，但使用站点域名做SNI/Host，
        测量"通过该IP访问该站点"的TTFB/响应头时间。

        Args:
            target: 目标主机（代理节点IP或域名）
            port: 测试端口（默认443）

        Returns:
            包含所有网站测试结果和摘要的字典
        """
        results = {
            'sites': {},
            'summary': {
                'available_count': 0,
                'total_count': 0,
                'avg_ttfb': None,
                'availability_rate': 0.0
            }
        }

        if not self.streaming_sites:
            return results

        results['summary']['total_count'] = len(self.streaming_sites)

        # 如果启用并发测试
        if self.streaming_concurrent and len(self.streaming_sites) > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=min(4, len(self.streaming_sites))) as executor:
                future_to_site = {
                    executor.submit(self._test_single_streaming_site, target, port, site): site
                    for site in self.streaming_sites
                }

                for future in as_completed(future_to_site):
                    site = future_to_site[future]
                    try:
                        site_result = future.result()
                        results['sites'][site] = site_result
                    except Exception as e:
                        results['sites'][site] = {
                            'success': False,
                            'ttfb': None,
                            'total_time': None,
                            'status_code': None,
                            'error': f'测试异常: {str(e)}'
                        }
        else:
            # 串行测试
            for site in self.streaming_sites:
                results['sites'][site] = self._test_single_streaming_site(target, port, site)

        # 计算摘要统计
        successful_sites = [r for r in results['sites'].values() if r['success']]
        results['summary']['available_count'] = len(successful_sites)
        results['summary']['availability_rate'] = (
            len(successful_sites) / len(self.streaming_sites) * 100
            if self.streaming_sites else 0.0
        )

        if successful_sites:
            ttfb_values = [r['ttfb'] for r in successful_sites if r['ttfb'] is not None]
            if ttfb_values:
                results['summary']['avg_ttfb'] = statistics.mean(ttfb_values)

        return results

    def _test_single_streaming_site(self, target: str, port: int, site_url: str) -> Dict:
        """
        测试单个流媒体网站

        Args:
            target: 目标IP/域名（Cloudflare边缘IP）
            port: 目标端口
            site_url: 网站URL（用于提取Host/SNI与路径）

        Returns:
            单个网站的测试结果
        """
        result = {
            'success': False,
            'ttfb': None,
            'total_time': None,
            'status_code': None,
            'error': None
        }

        try:
            metrics = self._http_request_via_ip(
                ip=self._clean_target(target),
                port=port,
                url=site_url,
                timeout=self.streaming_timeout,
            )
            result['success'] = metrics.get('success', False)
            result['ttfb'] = metrics.get('ttfb')
            result['total_time'] = metrics.get('total_time')
            result['status_code'] = metrics.get('status_code')
            result['error'] = metrics.get('error')

            # 部分站点会返回403/302等，但对"可达"来说仍算成功
            if not result['success'] and result['status_code'] in [200, 301, 302, 403]:
                result['success'] = True
                if not result['error']:
                    result['error'] = f"HTTP {result['status_code']}"
        except Exception as e:
            result['error'] = f"测试异常: {str(e)}"

        return result

    def test_download_speed(self, ip: str, port: int = 443, duration: int = 10) -> Dict:
        """
        测试实际下载速度

        使用 Cloudflare 的测试 URL 进行真实文件下载测试，真实反映带宽质量。
        默认使用 HTTPS (443端口) + TLS + SNI。

        Args:
            ip: IP地址
            port: 端口（默认443，使用TLS）
            duration: 测试时长（秒），默认10秒

        Returns:
            {
                'success': bool,
                'speed_mbps': float,      # 下载速度(Mbps)
                'total_bytes': int,       # 总下载字节数
                'duration': float,        # 实际测试时长
                'status_code': int,       # HTTP状态码
                'error': str              # 错误信息
            }
        """
        result = {
            'success': False,
            'speed_mbps': 0.0,
            'total_bytes': 0,
            'duration': 0.0,
            'status_code': None,
            'error': None
        }

        clean_ip = self._clean_target(ip)

        # 获取配置的超时时间
        download_timeout = self.config.get('download_timeout', 15)

        # 校验：确保 timeout >= duration + buffer，避免测速被提前中断
        if download_timeout < duration + 2:
            download_timeout = duration + 2
            self.logger.warning(f"download_timeout 过小，已自动调整为 {download_timeout}秒")

        sock = None
        try:
            start_time = time.time()

            # 创建 socket 连接
            sock = socket.create_connection((clean_ip, port), timeout=download_timeout)
            sock.settimeout(download_timeout)

            # 如果是443端口，使用TLS+SNI
            if port == 443:
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname='speed.cloudflare.com')

            # 构造 HTTP 请求
            req = (
                f"GET /__down?bytes=100000000 HTTP/1.1\r\n"
                f"Host: speed.cloudflare.com\r\n"
                "User-Agent: bestip/2.x\r\n"
                "Accept: */*\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode('ascii', errors='ignore')
            sock.sendall(req)

            # 读取并解析 HTTP 响应头
            header_buf = bytearray()
            while b"\r\n\r\n" not in header_buf:
                chunk = sock.recv(1024)
                if not chunk:
                    result['error'] = "无响应数据"
                    return result
                header_buf.extend(chunk)

            # 解析状态码
            try:
                header_text = bytes(header_buf).split(b"\r\n", 1)[0].decode('ascii', errors='ignore')
                # e.g. HTTP/1.1 200 OK
                parts = header_text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    result['status_code'] = int(parts[1])
            except Exception:
                pass

            # 校验状态码
            if result['status_code'] not in [200, 206]:
                result['error'] = f"HTTP错误: {result['status_code']}"
                return result

            # 找到响应体开始位置
            header_end = header_buf.find(b"\r\n\r\n") + 4
            body_start = header_buf[header_end:]

            # 开始计时和统计下载字节数
            # 注意：不计入响应头阶段的 body_start，只统计纯下载阶段的字节数
            total_bytes = 0
            download_start = time.time()

            # 先处理响应头中已读取的body部分
            if body_start:
                total_bytes += len(body_start)

            # 流式下载，避免内存占用过大
            while True:
                elapsed = time.time() - download_start
                if elapsed >= duration:
                    break

                try:
                    chunk = sock.recv(8192)  # 8KB 缓冲区
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                except socket.timeout:
                    break

            end_time = time.time()
            actual_duration = end_time - download_start

            if actual_duration > 0 and total_bytes > 0:
                # 计算速度（Mbps = Megabits per second）
                speed_mbps = (total_bytes * 8 / 1000000) / actual_duration
                result['success'] = True
                result['speed_mbps'] = round(speed_mbps, 2)
                result['total_bytes'] = total_bytes
                result['duration'] = round(actual_duration, 2)
            else:
                result['error'] = "下载数据不足"

        except ssl.SSLError as e:
            result['error'] = f"TLS错误: {e}"
        except socket.timeout:
            result['error'] = "下载超时"
        except Exception as e:
            result['error'] = str(e)
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass

        return result

    def get_ip_location(self, ip: str, port: int = 443) -> Dict:
        """
        获取IP的地理位置信息

        优先使用 ipinfo.dkly.net API 获取详细信息，
        如果 API 不可用则回退到 Cloudflare trace 接口。

        Args:
            ip: IP地址
            port: 端口（默认443，使用TLS）

        Returns:
            {
                'success': bool,
                'colo': str,              # 机场代码（如SG、NL）
                'country': str,           # 国家代码（如US、CN）
                'ip': str,                # 实际IP地址
                'region': str,            # 区域信息
                'city': str,              # 城市（新增）
                'asn': str,               # ASN（新增）
                'organization': str,      # 组织/运营商（新增）
                'proxy_type': str,        # 代理类型（新增）
                'is_vpn': bool,           # 是否VPN（新增）
                'is_proxy': bool,         # 是否代理（新增）
                'is_tor': bool,           # 是否Tor（新增）
                'error': str              # 错误信息
            }
        """
        result = {
            'success': False,
            'colo': 'Unknown',
            'country': 'Unknown',
            'ip': 'Unknown',
            'region': 'Unknown',
            'city': 'Unknown',
            'display_location': 'Unknown',  # 新增：格式化的位置字符串（仅用于展示）
            'asn': 'Unknown',
            'organization': 'Unknown',
            'proxy_type': 'Unknown',
            'is_vpn': False,
            'is_proxy': False,
            'is_tor': False,
            'error': None
        }

        clean_ip = self._clean_target(ip)

        # 优先使用 IP 信息 API
        if self.ipinfo_client:
            try:
                api_data = self.ipinfo_client.query_ip(clean_ip)

                if api_data:
                    # 提取地理位置信息
                    location_info = self.ipinfo_client.extract_location_info(api_data)
                    result['country'] = location_info.get('country', 'Unknown')
                    result['region'] = location_info.get('region', 'Unknown')
                    result['city'] = location_info.get('city', 'Unknown')

                    # 提取网络信息
                    network_info = self.ipinfo_client.extract_network_info(api_data)
                    result['asn'] = network_info.get('asn', 'Unknown')
                    result['organization'] = network_info.get('organization', 'Unknown')

                    # 提取安全信息
                    security_info = self.ipinfo_client.extract_security_info(api_data)
                    result['is_vpn'] = security_info.get('is_vpn', False)
                    result['is_proxy'] = security_info.get('is_proxy', False)
                    result['is_tor'] = security_info.get('is_tor', False)

                    # 获取代理类型字符串
                    result['proxy_type'] = self.ipinfo_client.get_proxy_type_string(api_data)

                    # 获取格式化的位置字符串（用于展示）
                    location_str = self.ipinfo_client.get_location_string(api_data)
                    if location_str != "未知":
                        result['display_location'] = location_str
                    else:
                        result['display_location'] = result['region']

                    result['ip'] = api_data.get('ip', clean_ip)
                    result['success'] = True

                    return result

            except Exception as e:
                # API 失败，记录错误但继续使用备用方法
                print(f"{self.CLR_Y}[WARNING] IP 信息 API 查询失败: {e}，使用备用方法{self.CLR_0}")

        # 回退到 Cloudflare trace 接口
        location_timeout = self.config.get('location_timeout', 5)

        sock = None
        try:
            # 创建 socket 连接
            sock = socket.create_connection((clean_ip, port), timeout=location_timeout)
            sock.settimeout(location_timeout)

            # 如果是443端口，使用TLS+SNI
            if port == 443:
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname='speed.cloudflare.com')

            # 构造 HTTP 请求
            req = (
                f"GET /cdn-cgi/trace HTTP/1.1\r\n"
                f"Host: speed.cloudflare.com\r\n"
                "User-Agent: bestip/2.x\r\n"
                "Accept: */*\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode('ascii', errors='ignore')
            sock.sendall(req)

            # 读取响应
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk

            # 解析响应
            response_text = response.decode('utf-8', errors='ignore')

            # 跳过 HTTP 响应头
            if "\r\n\r\n" in response_text:
                body = response_text.split("\r\n\r\n", 1)[1]
            else:
                body = response_text

            # 解析键值对
            for line in body.split('\n'):
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'colo':
                        result['colo'] = value
                    elif key == 'loc':
                        result['country'] = value
                    elif key == 'ip':
                        result['ip'] = value

            # 构造区域信息和展示字符串
            if result['colo'] != 'Unknown' and result['country'] != 'Unknown':
                result['region'] = result['country']  # region 保持为国家代码
                result['display_location'] = f"{result['colo']}/{result['country']}"  # 展示用
                result['success'] = True
            elif result['colo'] != 'Unknown':
                result['region'] = result['colo']
                result['display_location'] = result['colo']
                result['success'] = True
            elif result['country'] != 'Unknown':
                result['region'] = result['country']
                result['display_location'] = result['country']
                result['success'] = True

        except ssl.SSLError as e:
            result['error'] = f"TLS错误: {e}"
        except socket.timeout:
            result['error'] = "位置检测超时"
        except Exception as e:
            result['error'] = str(e)
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass

        return result

    def test_connection_stability(self, target: str, port: int = 443) -> Dict:
        """
        连接稳定性测试

        Args:
            target: 目标主机
            port: 测试端口（默认443）

        Returns:
            稳定性测试结果
        """
        result = {
            'success_rate': 0.0,
            'avg_connect_time': None,
            'failed_attempts': 0,
            'stability_score': 0
        }

        clean_target = self._clean_target(target)
        connect_times = []
        failed_count = 0

        # 连续测试多次
        for i in range(self.stability_attempts):
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.tcp_timeout)
                sock.connect((clean_target, port))
                sock.close()

                connect_time = (time.time() - start_time) * 1000
                connect_times.append(connect_time)
            except:
                failed_count += 1

        # 计算统计信息
        success_count = self.stability_attempts - failed_count
        result['success_rate'] = (success_count / self.stability_attempts) * 100
        result['failed_attempts'] = failed_count

        if connect_times:
            result['avg_connect_time'] = statistics.mean(connect_times)

        # 计算稳定性评分（0-100）
        # 基于成功率和连接时间变异系数
        if result['success_rate'] >= 90:
            base_score = 90 + (result['success_rate'] - 90)
        elif result['success_rate'] >= 80:
            base_score = 70 + (result['success_rate'] - 80) * 2
        elif result['success_rate'] >= 70:
            base_score = 50 + (result['success_rate'] - 70) * 2
        else:
            base_score = result['success_rate'] * 0.7

        # 如果有连接时间数据，考虑变异系数
        if len(connect_times) > 1:
            cv = (statistics.stdev(connect_times) / statistics.mean(connect_times)) * 100
            if cv < 10:
                cv_penalty = 0
            elif cv < 20:
                cv_penalty = 5
            elif cv < 30:
                cv_penalty = 10
            else:
                cv_penalty = 15
            base_score -= cv_penalty

        result['stability_score'] = int(max(0, min(100, base_score)))

        return result
    
    def calculate_quality_score(self, ping_result: Dict, tcp_result: Dict) -> Dict:
        """
        计算综合质量评分（基于Cloudflare AIM模型）
        
        Args:
            ping_result: Ping测试结果
            tcp_result: TCP测试结果
            
        Returns:
            包含各项评分的字典
        """
        scores = {
            'streaming': 0,  # 流媒体评分（0-100）
            'gaming': 0,     # 游戏评分（0-100）
            'rtc': 0,        # 实时通信评分（0-100）
            'overall': 0     # 总体评分
        }
        
        if not ping_result['success']:
            return scores
        
        # 获取指标值，处理None值
        delay = ping_result.get('avg_delay', 1000)
        loss = ping_result.get('loss_rate', 100)
        jitter = ping_result.get('jitter', 100)
        tcp_time = tcp_result.get('connect_time', 1000)
        
        # 1. 流媒体评分（下载带宽 + 空载延迟 + 丢包率 + 负载延迟差值）
        # 简化版：只考虑延迟、丢包、抖动
        streaming_score = 100
        
        # 延迟扣分（针对国际连接调整阈值）
        # <100ms不扣分，100-200ms扣10分，200-300ms扣30分，>300ms扣50分
        if delay > 300:
            streaming_score -= 50
        elif delay > 200:
            streaming_score -= 30
        elif delay > 100:
            streaming_score -= 10
        
        # 丢包扣分（流媒体对丢包有一定容忍度）
        # <1%不扣分，1-3%扣10分，3-5%扣20分，>5%扣40分
        if loss > 5:
            streaming_score -= 40
        elif loss > 3:
            streaming_score -= 20
        elif loss > 1:
            streaming_score -= 10
        
        # 抖动扣分（流媒体对抖动不敏感）
        # <50ms不扣分，50-100ms扣10分，>100ms扣20分
        if jitter > 100:
            streaming_score -= 20
        elif jitter > 50:
            streaming_score -= 10
        
        streaming_score = max(0, streaming_score)
        
        # 2. 游戏评分（丢包率 + 空载延迟 + 负载延迟差值）
        gaming_score = 100
        
        # 游戏对丢包非常敏感
        if loss > 2:
            gaming_score -= 40
        elif loss > 1:
            gaming_score -= 20
        elif loss > 0.5:
            gaming_score -= 10
        
        # 游戏对延迟敏感（国际游戏服务器通常延迟较高）
        if delay > 150:
            gaming_score -= 30
        elif delay > 100:
            gaming_score -= 20
        elif delay > 50:
            gaming_score -= 10
        
        # 游戏对抖动敏感
        if jitter > 50:
            gaming_score -= 20
        elif jitter > 20:
            gaming_score -= 10
        
        gaming_score = max(0, gaming_score)
        
        # 3. 实时通信评分（丢包率 + 抖动 + 空载延迟 + 负载延迟差值）
        rtc_score = 100
        
        # RTC对丢包非常敏感
        if loss > 1:
            rtc_score -= 30
        elif loss > 0.5:
            rtc_score -= 20
        elif loss > 0.1:
            rtc_score -= 10
        
        # RTC对抖动非常敏感
        if jitter > 30:
            rtc_score -= 30
        elif jitter > 20:
            rtc_score -= 20
        elif jitter > 10:
            rtc_score -= 10
        
        # RTC对延迟有一定容忍度
        if delay > 200:
            rtc_score -= 20
        elif delay > 150:
            rtc_score -= 15
        elif delay > 100:
            rtc_score -= 10
        
        rtc_score = max(0, rtc_score)
        
        # 4. 总体评分（加权平均）
        overall_score = int((streaming_score * 0.3 + gaming_score * 0.3 + rtc_score * 0.4))
        
        scores.update({
            'streaming': streaming_score,
            'gaming': gaming_score,
            'rtc': rtc_score,
            'overall': overall_score
        })
        
        return scores
    
    def _clean_target(self, target: str) -> str:
        """清理目标字符串，移除端口和注释，返回纯净的IP或域名"""
        clean_target = target.strip()
        
        # 先处理注释部分（#之后的内容）
        if '#' in clean_target:
            clean_target = clean_target.split('#')[0].strip()
        
        # 处理端口部分（:之后的内容）
        # 但要注意IPv6地址中也有冒号，需要小心处理
        if ':' in clean_target:
            # 简单判断：如果包含多个冒号，可能是IPv6地址，不处理
            if clean_target.count(':') <= 1:
                # 可能是IPv4地址加端口或域名加端口
                # 检查是否是有效的端口格式（冒号后是数字）
                parts = clean_target.split(':')
                if len(parts) == 2:
                    ip_part, port_part = parts
                    # 检查端口部分是否是数字
                    if port_part.isdigit():
                        clean_target = ip_part.strip()
                    else:
                        # 可能不是端口，保持原样
                        clean_target = clean_target
                else:
                    # 多个冒号，可能是IPv6地址，保持原样
                    clean_target = clean_target
            else:
                # IPv6地址，保持原样
                clean_target = clean_target
        
        return clean_target
    
    def test_target(self, target: str) -> Dict:
        """
        测试单个目标（增强版，包含所有新测试）

        Args:
            target: 域名或IP地址

        Returns:
            完整的测试结果
        """
        result = {
            'original': target.strip(),
            'target': self._clean_target(target),
            'ping': {},
            'tcp': {},
            'http': {},
            'stability': {},
            'scores': {},
            'success': False,
            'error': None
        }

        # 提取端口
        test_port = 443
        if ':' in target:
            try:
                port_part = target.split(':')[1]
                if '#' in port_part:
                    port_part = port_part.split('#')[0]
                test_port = int(port_part)
            except:
                pass

        try:
            # 1. Ping测试
            print(f"测试Ping: {result['target']}...")
            ping_result = self._run_ping_test(result['target'])
            result['ping'] = ping_result

            if not ping_result['success']:
                result['error'] = "Ping测试失败"
                return result

            # 2. TCP测试
            print(f"测试TCP连接: {result['target']}:{test_port}...")
            tcp_result = self.test_tcp_connection(result['target'], test_port)
            result['tcp'] = tcp_result

            # 3. HTTP性能测试（如果启用）
            if self.enable_http_test:
                print(f"测试HTTP性能: {result['target']}...")
                http_result = self.test_http_performance(result['target'], test_port)
                result['http'] = http_result

            # 3.5. 地理位置检测（如果启用）
            enable_location = self.config.get('enable_location_test', True)
            if enable_location:
                print(f"检测地理位置: {result['target']}...")
                # 强制使用443端口，因为 Cloudflare 的服务只在443端口上可用
                location_result = self.get_ip_location(result['target'], 443)
                result['location'] = location_result
                if location_result.get('success'):
                    print(f"  位置: {location_result['region']}")

            # 3.6. 下载速度测试（如果启用）
            enable_download = self.config.get('enable_download_test', False)
            if enable_download:
                print(f"测试下载速度: {result['target']}...")
                download_duration = self.config.get('download_test_duration', 10)
                # 强制使用443端口，因为 Cloudflare 的服务只在443端口上可用
                download_result = self.test_download_speed(result['target'], 443, download_duration)
                result['download'] = download_result
                if download_result.get('success'):
                    print(f"  下载速度: {download_result['speed_mbps']:.2f} Mbps")

            # 4. 流媒体网站测试（如果启用）
            if self.enable_streaming_test:
                print(f"测试流媒体网站可用性: {result['target']}...")
                streaming_result = self.test_streaming_sites(result['target'], test_port)
                result['streaming_sites'] = streaming_result['sites']
                result['streaming_summary'] = streaming_result['summary']

                # 显示摘要
                summary = streaming_result['summary']
                print(f"  流媒体: {summary['available_count']}/{summary['total_count']} 可用", end='')
                if summary['avg_ttfb']:
                    print(f", 平均延迟: {summary['avg_ttfb']:.1f}ms")
                else:
                    print()

            # 5. 连接稳定性测试（如果启用）
            if self.enable_stability_test:
                print(f"测试连接稳定性: {result['target']}...")
                stability_result = self.test_connection_stability(result['target'], test_port)
                result['stability'] = stability_result

            # 5. 计算评分
            if ProxyScoreCalculator:
                # 使用新的代理评分算法
                scoring_input = dict(result)
                if not self.score_include_http:
                    scoring_input['http'] = {}
                scores = ProxyScoreCalculator.calculate_proxy_score(scoring_input)
            else:
                # 使用原有评分算法（向后兼容）
                scores = self.calculate_quality_score(ping_result, tcp_result)

            result['scores'] = scores
            result['success'] = True

            # 显示测试结果
            print(f"  延迟: {ping_result['avg_delay']:.1f}ms, "
                  f"丢包: {ping_result['loss_rate']:.1f}%, "
                  f"抖动: {ping_result.get('jitter', 0):.1f}ms")

            if result['http'].get('success'):
                print(f"  HTTP TTFB: {result['http']['ttfb']:.1f}ms")

            if result['stability']:
                print(f"  稳定性: {result['stability']['success_rate']:.1f}%")

            print(f"  评分: 总体{scores.get('overall', 0)}")

        except Exception as e:
            result['error'] = str(e)

        return result

    def _run_ping_test(self, target: str) -> Dict:
        """执行Ping测试并返回结果"""
        try:
            if sys.platform == 'win32':
                cmd = ['ping', '-n', str(self.ping_count), '-w', str(self.ping_timeout * 1000), target]
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    timeout=self.ping_timeout * self.ping_count + 5
                )
            else:
                cmd = ['ping', '-c', str(self.ping_count), '-W', str(self.ping_timeout), target]
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.ping_timeout * self.ping_count + 5
                )
            
            if process.returncode in [0, 1]:  # 0=成功，1=有丢包
                return self.parse_ping_output_detailed(process.stdout)
            else:
                return {'success': False}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': '超时'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_targets(self, targets: List[str]) -> List[Dict]:
        """
        批量测试多个目标（并发执行）
        
        Args:
            targets: 目标列表
            
        Returns:
            测试结果列表
        """
        print(f"开始测试 {len(targets)} 个目标（并发数: {self.max_workers}）...")
        self.results = []
        
        # 创建线程池
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_target = {
                executor.submit(self._test_target_with_progress, target, idx, len(targets)): (target, idx)
                for idx, target in enumerate(targets)
            }
            
            # 收集结果
            for future in as_completed(future_to_target):
                target, idx = future_to_target[future]
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    print(f"\n目标 {target} 测试时发生异常: {e}")
                    self.results.append({
                        'original': target,
                        'target': self._clean_target(target),
                        'ping': {},
                        'tcp': {},
                        'scores': {},
                        'success': False,
                        'error': str(e)
                    })
        
        successful = len([r for r in self.results if r['success']])
        print(f"\n测试完成，成功: {successful}/{len(targets)}")
        return self.results
    
    def _test_target_with_progress(self, target: str, idx: int, total: int) -> Dict:
        """
        包装test_target方法，添加进度显示（线程安全版本）
        
        Args:
            target: 目标
            idx: 目标索引
            total: 总目标数
            
        Returns:
            测试结果
        """
        # 只保护输出，不要把整个测试流程锁住（否则并发会退化为串行）
        with self.print_lock:
            print(f"[{idx+1}/{total}] 开始: {self._clean_target(target)}")

        result = self.test_target(target)

        if not result['success']:
            with self.print_lock:
                print(f"[{idx+1}/{total}] 失败: {self._clean_target(target)} - {result.get('error', '未知错误')}")

        return result

    def test_targets_two_phase(self, targets: List[str]) -> List[Dict]:
        """
        两阶段测试流程（快速筛选 + 深度测试）

        Args:
            targets: 目标列表

        Returns:
            测试结果列表
        """
        if not self.enable_quick_check:
            # 如果未启用快速检测，使用原有方法
            return self.test_targets(targets)

        print("=" * 60)
        print("阶段1：快速可用性检测")
        print("=" * 60)
        print(f"开始快速检测 {len(targets)} 个目标（并发数: {self.quick_check_workers}）...")

        available_targets = []
        unavailable_count = 0

        # 阶段1：快速检测
        with ThreadPoolExecutor(max_workers=self.quick_check_workers) as executor:
            future_to_target = {
                executor.submit(self.quick_availability_check, target): target
                for target in targets
            }

            for idx, future in enumerate(as_completed(future_to_target), 1):
                target = future_to_target[future]
                try:
                    result = future.result()
                    if result['available']:
                        available_targets.append(target)
                        delay_info = f", 延迟={result['quick_delay']:.0f}ms" if result['quick_delay'] else ""
                        print(f"[{idx}/{len(targets)}] {self._clean_target(target)}: 可用{delay_info}")
                    else:
                        unavailable_count += 1
                        reason = result.get('reason', '未知原因')
                        print(f"[{idx}/{len(targets)}] {self._clean_target(target)}: 不可用 ({reason})")
                except Exception as e:
                    unavailable_count += 1
                    print(f"[{idx}/{len(targets)}] {target}: 检测异常 - {str(e)}")

        print(f"\n快速检测完成: 可用 {len(available_targets)}/{len(targets)}, "
              f"不可用 {unavailable_count}/{len(targets)}")

        if not available_targets:
            print("\n没有可用的节点，测试结束。")
            self.results = []
            return self.results

        # 阶段2：深度测试
        print("\n" + "=" * 60)
        print("阶段2：深度质量测试")
        print("=" * 60)
        print(f"开始深度测试 {len(available_targets)} 个可用目标（并发数: {self.max_workers}）...")

        return self.test_targets(available_targets)

    def sort_results(self, sort_by: str = None) -> List[Dict]:
        """
        对结果进行排序

        Args:
            sort_by: 排序依据，可选 'quality', 'overall', 'streaming', 'gaming', 'rtc', 'delay', 'loss'
                    如果为None，使用配置中的sort_by

        Returns:
            排序后的结果列表
        """
        # 如果未指定sort_by，使用配置中的值
        if sort_by is None:
            sort_by = self.config.get('sort_by', 'overall')

        # 如果是quality排序，使用新的排序算法
        if sort_by == 'quality':
            return self.sort_results_by_quality()

        # 否则使用原有的排序算法
        def get_sort_key(result):
            if not result['success']:
                return (float('inf'), float('inf'), float('inf'))

            if sort_by in ['overall', 'streaming', 'gaming', 'rtc']:
                score = result['scores'].get(sort_by, 0)
                # 按评分降序排列
                return (-score,
                        result['ping'].get('loss_rate', 100) or 100,
                        result['ping'].get('avg_delay', 1000) or 1000)
            elif sort_by == 'delay':
                delay = result['ping'].get('avg_delay', 1000) or 1000
                loss = result['ping'].get('loss_rate', 100) or 100
                return (delay, loss)
            elif sort_by == 'loss':
                loss = result['ping'].get('loss_rate', 100) or 100
                delay = result['ping'].get('avg_delay', 1000) or 1000
                return (loss, delay)
            else:
                return (float('inf'), float('inf'), float('inf'))

        return sorted(self.results, key=get_sort_key)

    def sort_results_by_quality(self, results: List[Dict] = None) -> List[Dict]:
        """
        按质量排序：先按丢包率分组，再按延迟排序，最后按速度排序

        排序策略（避免高丢包低延迟IP排前面）：
        1. 按丢包率分为4组：perfect(0%), good(<5%), acceptable(<10%), poor(>=10%)
        2. 每组内按延迟升序排序
        3. 取前N个候选进行下载速度测试（如果启用且未测试）
        4. 重新分组并在每组内按延迟和速度排序

        Args:
            results: 测试结果列表（如果为None，使用self.results）

        Returns:
            排序后的结果列表
        """
        if results is None:
            results = self.results

        # 过滤出成功的结果
        success_results = [r for r in results if r.get('success')]
        failed_results = [r for r in results if not r.get('success')]

        # 按丢包率分组
        perfect = []    # 0% 丢包
        good = []       # <5% 丢包
        acceptable = [] # <10% 丢包
        poor = []       # >=10% 丢包

        for result in success_results:
            loss_rate = result.get('ping', {}).get('loss_rate', 100)
            # 处理None值，避免TypeError
            if loss_rate is None:
                loss_rate = 100

            if loss_rate == 0:
                perfect.append(result)
            elif loss_rate < 5:
                good.append(result)
            elif loss_rate < 10:
                acceptable.append(result)
            else:
                poor.append(result)

        # 定义排序键函数（仅按延迟排序）
        def get_delay_sort_key(result):
            delay = result.get('ping', {}).get('avg_delay', 1000)
            # 处理None值
            if delay is None:
                delay = 1000
            return delay

        # 每组内先按延迟排序
        perfect.sort(key=get_delay_sort_key)
        good.sort(key=get_delay_sort_key)
        acceptable.sort(key=get_delay_sort_key)
        poor.sort(key=get_delay_sort_key)

        # 合并结果（按质量分组顺序）
        sorted_by_delay = perfect + good + acceptable + poor

        # 定义最终排序键函数（延迟升序，速度降序）
        def get_quality_sort_key(result):
            delay = result.get('ping', {}).get('avg_delay', 1000)
            # 处理None值
            if delay is None:
                delay = 1000

            # 下载速度（如果有）
            download = result.get('download', {})
            if download.get('success'):
                speed = download.get('speed_mbps', 0)
                if speed is None:
                    speed = 0
            else:
                speed = 0
            # 返回：延迟升序，速度降序
            return (delay, -speed)

        # 每组内按延迟和速度排序
        perfect.sort(key=get_quality_sort_key)
        good.sort(key=get_quality_sort_key)
        acceptable.sort(key=get_quality_sort_key)
        poor.sort(key=get_quality_sort_key)

        # 合并结果：perfect -> good -> acceptable -> poor -> failed
        return perfect + good + acceptable + poor + failed_results

    def save_results(self, output_file: str = 'result_pro.txt'):
        """
        保存结果到文件
        
        Args:
            output_file: 输出文件名
        """
        sorted_results = self.sort_results('overall')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # 写入表头
            f.write("=" * 100 + "\n")
            f.write("高级IP/域名质量测试报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            
            f.write("排序说明: 按综合评分降序排列（评分越高质量越好）\n\n")
            if self.enable_streaming_test:
                f.write("说明: 网站连通性测试（streaming_sites）仅用于展示，不参与综合评分与排序。\n\n")
            if self.enable_http_test and not self.score_include_http:
                f.write("说明: HTTP性能测试（http_test_url）仅用于展示，不参与综合评分与排序。\n\n")
            
            # 写入列标题
            headers = [
                "排名", "目标", "延迟(ms)", "丢包率(%)", "抖动(ms)",
                "TCP连接(ms)", "下载速度", "地理位置", "综合评分", "流媒体", "游戏", "实时通信", "状态"
            ]
            f.write(f"{headers[0]:<4} {headers[1]:<30} {headers[2]:<10} {headers[3]:<10} "
                   f"{headers[4]:<10} {headers[5]:<12} {headers[6]:<12} {headers[7]:<15} {headers[8]:<10} "
                   f"{headers[9]:<10} {headers[10]:<10} {headers[11]:<10} {headers[12]:<10}\n")
            f.write("-" * 160 + "\n")

            # 写入成功的结果
            rank = 1
            for result in sorted_results:
                if result['success']:
                    target = result['original'][:30]
                    delay = f"{result['ping'].get('avg_delay', 0):.1f}"
                    loss = f"{result['ping'].get('loss_rate', 0):.1f}"
                    jitter = f"{result['ping'].get('jitter', 0):.1f}"

                    tcp_time = "N/A"
                    if result['tcp'].get('success'):
                        tcp_time = f"{result['tcp'].get('connect_time', 0):.1f}"

                    # 下载速度
                    download_speed = "N/A"
                    download_result = result.get('download', {})
                    if download_result and download_result.get('success'):
                        download_speed = f"{download_result.get('speed_mbps', 0):.2f} Mbps"

                    # 地理位置（优先使用 display_location）
                    location = "Unknown"
                    location_result = result.get('location', {})
                    if location_result and location_result.get('success'):
                        location = location_result.get('display_location', location_result.get('region', 'Unknown'))[:15]

                    scores = result['scores']
                    overall = str(scores.get('overall', 0))
                    streaming = str(scores.get('streaming', 0))
                    gaming = str(scores.get('gaming', 0))
                    rtc = str(scores.get('rtc', 0))

                    f.write(f"{rank:<4} {target:<30} {delay:<10} {loss:<10} "
                           f"{jitter:<10} {tcp_time:<12} {download_speed:<12} {location:<15} {overall:<10} "
                           f"{streaming:<10} {gaming:<10} {rtc:<10} 成功\n")
                    rank += 1

            # 流媒体测试摘要（如果启用）
            if self.enable_streaming_test and any('streaming_summary' in r for r in sorted_results):
                f.write("\n" + "=" * 100 + "\n")
                f.write("网站连通性测试摘要（仅展示，不参与综合评分与排序）:\n")
                f.write("-" * 100 + "\n")

                streaming_results = [r for r in sorted_results if r.get('streaming_summary') and r['success']]
                for result in streaming_results[:10]:  # 只显示前10个
                    target = result['original'][:40]
                    summary = result['streaming_summary']
                    available = summary['available_count']
                    total = summary['total_count']
                    rate = summary['availability_rate']
                    avg_ttfb = summary.get('avg_ttfb')

                    ttfb_str = f", 平均延迟: {avg_ttfb:.1f}ms" if avg_ttfb else ""
                    f.write(f"{target:<40} 可用: {available}/{total} ({rate:.0f}%){ttfb_str}\n")

            # 写入失败的结果
            if any(not r['success'] for r in sorted_results):
                f.write("\n" + "=" * 100 + "\n")
                f.write("测试失败的目标:\n")
                f.write("-" * 100 + "\n")
                
                for result in sorted_results:
                    if not result['success']:
                        target = result['original'][:30]
                        error = result.get('error', '未知错误')
                        f.write(f"{target:<40} {error}\n")
        
        print(f"详细结果已保存到: {output_file}")

    def _make_history_key(self, target: Optional[str], original: Optional[str]) -> str:
        if isinstance(original, str):
            base = original.split('#', 1)[0].strip()
            if base:
                return base
        if isinstance(target, str):
            return target.strip()
        return ""

    def _coerce_number(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def _format_number(self, value: Optional[float], precision: int = 1, suffix: str = "") -> str:
        if value is None:
            return "N/A"
        return f"{value:.{precision}f}{suffix}"

    def _format_score(self, value: Optional[float], bold: bool = False) -> str:
        if value is None:
            return "N/A"
        formatted = f"{value:.0f}"
        return f"**{formatted}**" if bold else formatted

    def _escape_md_cell(self, value: str) -> str:
        """
        转义 Markdown 表格单元格内容，避免破坏表格结构

        Args:
            value: 要转义的字符串

        Returns:
            转义后的字符串（安全用于 Markdown 表格）
        """
        if value is None:
            return ""
        text = str(value).replace("\n", " ").replace("\r", " ")
        # 替换反引号为单引号，避免行内代码块冲突
        text = text.replace("`", "'")
        # 转义管道符
        text = text.replace("|", "\\|")
        return text

    def _extract_location_tag_from_comment(self, original: Optional[str]) -> Optional[str]:
        """
        从原始字符串的注释中提取地区标识（可能是国家码、地区名或其他标签）

        Args:
            original: 原始字符串，格式如 "IP:port#地区-其他信息"

        Returns:
            地区标识字符串，如果无法提取则返回 None
        """
        if not isinstance(original, str) or "#" not in original:
            return None
        comment_part = original.split("#", 1)[1].strip()
        if not comment_part:
            return None
        # 提取 "-" 之前的部分作为地区标识
        candidate = comment_part.split("-", 1)[0].strip()
        if not candidate:
            return None
        # 过滤广告性质的标签（包含频道、@、加入等关键词）
        if any(token in candidate for token in ("频道", "@", "加入")):
            return None
        return candidate

    def _resolve_location_tag(self, target: Optional[str], original: Optional[str] = None, result: Optional[Dict] = None) -> str:
        """
        解析地区标识：优先从测试结果提取，其次从注释提取，最后使用地理位置查询

        Args:
            target: 清理后的目标（IP或域名）
            original: 原始输入字符串
            result: 测试结果字典（包含地理位置信息）

        Returns:
            地区标识字符串（测试结果 > 注释标签 > 地理查询结果 > 目标本身 > "未知"）
        """
        # 优先使用测试结果中的地理位置信息
        if result and result.get('location', {}).get('success'):
            location_data = result.get('location', {})
            # 优先使用 colo（机场代码）
            location_tag = location_data.get('colo', '')
            if location_tag and location_tag != 'Unknown':
                return location_tag
            # 回退到 country（国家代码）
            location_tag = location_data.get('country', '')
            if location_tag and location_tag != 'Unknown':
                return location_tag
            # 最后回退到 region（组合信息）
            location_tag = location_data.get('region', '')
            if location_tag and location_tag != 'Unknown':
                return location_tag

        # 其次使用注释中的地区标识
        comment_tag = self._extract_location_tag_from_comment(original)
        if comment_tag:
            return comment_tag

        # 如果没有目标信息，返回"未知"
        if not target:
            return "未知"

        # 尝试地理位置查询（仅在启用时）
        if self.config.get('enable_location_test', True):
            country_code, _ = self.get_country_from_ip(target)
            if country_code and country_code not in ("未知", "Unknown"):
                return country_code

        # 如果目标包含字母（域名），返回目标本身作为标识
        if any(c.isalpha() for c in str(target)):
            return str(target)

        # 否则返回目标本身（IP地址）
        return str(target)

    def load_history(self, history_file: str = 'data/output/result_history.json') -> Optional[Dict]:
        """
        加载历史测试结果

        Args:
            history_file: 历史文件路径

        Returns:
            历史结果字典，如果文件不存在则返回None
        """
        if not os.path.exists(history_file):
            return None

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"警告: 读取历史文件失败: {e}")
            return None

        if not isinstance(data, dict):
            print("警告: 历史文件格式异常，已跳过对比")
            return None

        version = data.get('version', 0)
        if version not in (0, self.HISTORY_VERSION):
            print(f"警告: 历史文件版本不兼容({version})，已跳过对比")
            return None

        results = data.get('results', [])
        if not isinstance(results, list):
            print("警告: 历史文件结构异常，已跳过对比")
            return None

        return data

    def save_history(self, history_file: str = 'data/output/result_history.json'):
        """
        保存当前测试结果到历史文件

        Args:
            history_file: 历史文件路径
        """
        sorted_results = self.sort_results('overall')
        successful_results = [r for r in sorted_results if r['success']]

        # 提取关键信息
        history_data = {
            'version': self.HISTORY_VERSION,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_count': len(self.results),
            'success_count': len(successful_results),
            'results': []
        }

        for rank, result in enumerate(successful_results, 1):
            key = self._make_history_key(result.get('target'), result.get('original'))
            history_data['results'].append({
                'rank': rank,
                'key': key,
                'target': result.get('target'),
                'original': result.get('original'),
                'score': self._coerce_number(result.get('scores', {}).get('overall')),
                'delay': self._coerce_number(result.get('ping', {}).get('avg_delay')),
                'loss_rate': self._coerce_number(result.get('ping', {}).get('loss_rate')),
                'jitter': self._coerce_number(result.get('ping', {}).get('jitter'))
            })

        try:
            history_dir = os.path.dirname(history_file)
            if history_dir:
                os.makedirs(history_dir, exist_ok=True)
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"警告: 保存历史文件失败: {e}")

    def compare_with_history(self, history: Dict) -> Dict:
        """
        对比当前结果与历史结果

        Args:
            history: 历史结果字典

        Returns:
            对比结果字典
        """
        sorted_results = self.sort_results('overall')
        successful_results = [r for r in sorted_results if r['success']]

        # 构建当前结果映射（支持同一 key 多个目标的情况）
        current_map = {}
        for rank, result in enumerate(successful_results, 1):
            key = self._make_history_key(result.get('target'), result.get('original'))
            if not key:
                continue

            # 确保 original 始终为字符串（避免后续处理时出错）
            original = result.get('original')
            if original is None:
                original = result.get('target', '')

            # 如果 key 已存在，保留第一个（排名更高的）
            if key not in current_map:
                current_map[key] = {
                    'rank': rank,
                    'score': self._coerce_number(result.get('scores', {}).get('overall')),
                    'delay': self._coerce_number(result.get('ping', {}).get('avg_delay')),
                    'original': str(original)  # 确保为字符串
                }

        # 构建历史结果映射（增强兼容性）
        history_map = {}
        history_results = history.get('results', [])
        if not isinstance(history_results, list):
            history_results = []
        for item in history_results:
            if not isinstance(item, dict):
                continue
            target = item.get('target')
            original = item.get('original')
            key = item.get('key') or self._make_history_key(target, original)
            if not key:
                continue

            # 宽松转换 rank（兼容字符串格式的历史数据）
            rank_value = item.get('rank')
            try:
                rank = int(rank_value) if rank_value is not None else None
            except (ValueError, TypeError):
                continue  # 无效的 rank，跳过该条记录

            if rank is None:
                continue

            # 确保 original 为字符串
            if original is None:
                original = target or ''

            history_map[key] = {
                'rank': rank,
                'score': self._coerce_number(item.get('score')),
                'delay': self._coerce_number(item.get('delay')),
                'original': str(original)  # 确保为字符串
            }

        # 分析变化
        current_keys = set(current_map.keys())
        history_keys = set(history_map.keys())

        # 新增的IP
        new_ips = current_keys - history_keys
        # 移除的IP
        removed_ips = history_keys - current_keys
        # 共同的IP
        common_ips = current_keys & history_keys

        # 排名变化
        rank_changes = []
        score_changes = []

        for key in common_ips:
            current = current_map[key]
            history_item = history_map[key]

            rank_diff = history_item['rank'] - current['rank']  # 正数表示排名上升
            score_diff = None
            if current['score'] is not None and history_item['score'] is not None:
                score_diff = current['score'] - history_item['score']

            if rank_diff != 0:
                rank_changes.append({
                    'target': key,
                    'original': current['original'],
                    'old_rank': history_item['rank'],
                    'new_rank': current['rank'],
                    'rank_diff': rank_diff,
                    'score': current['score']
                })

            if score_diff is not None and abs(score_diff) >= 5:  # 评分变化超过5分才记录
                score_changes.append({
                    'target': key,
                    'original': current['original'],
                    'old_score': history_item['score'],
                    'new_score': current['score'],
                    'score_diff': score_diff
                })

        # 按排名变化幅度排序
        rank_changes.sort(key=lambda x: abs(x['rank_diff']), reverse=True)
        # 按评分变化幅度排序
        score_changes.sort(key=lambda x: abs(x['score_diff']), reverse=True)

        # 计算整体趋势
        score_diffs = [
            current_map[k]['score'] - history_map[k]['score']
            for k in common_ips
            if current_map[k]['score'] is not None and history_map[k]['score'] is not None
        ]
        avg_score_change = sum(score_diffs) / len(score_diffs) if score_diffs else 0

        return {
            'has_history': True,
            'history_time': history.get('timestamp', '未知'),
            'new_ips': sorted([(key, current_map[key]) for key in new_ips],
                            key=lambda x: x[1]['rank']),
            'removed_ips': sorted([(key, history_map[key]) for key in removed_ips],
                                key=lambda x: x[1]['rank']),
            'rank_changes': rank_changes[:10],  # 只显示前10个变化
            'score_changes': score_changes[:10],
            'avg_score_change': avg_score_change,
            'total_current': len(successful_results),
            'total_history': len(history_results)
        }

    def save_results_md(self, output_file: str = 'result_pro.md'):
        """
        保存结果到markdown格式文件

        Args:
            output_file: 输出文件名
        """
        sorted_results = self.sort_results('overall')

        # 加载历史结果并进行对比
        history = self.load_history()
        comparison = None
        if history:
            comparison = self.compare_with_history(history)

        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            # 写入markdown标题
            f.write(f"# 🚀 IP/域名质量测试报告\n\n")
            f.write(f"📅 **生成时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n")

            # 如果有历史记录，显示变动对比
            if comparison and comparison['has_history']:
                f.write("## 📊 变动对比分析\n\n")
                f.write(f"> 📅 **上次测试时间**: `{comparison['history_time']}`\n\n")

                # 整体趋势
                avg_change = comparison['avg_score_change']
                if avg_change > 2:
                    trend_emoji = "📈"
                    trend_text = f"整体质量提升 (+{avg_change:.1f}分)"
                    trend_color = "🟢"
                elif avg_change < -2:
                    trend_emoji = "📉"
                    trend_text = f"整体质量下降 ({avg_change:.1f}分)"
                    trend_color = "🔴"
                else:
                    trend_emoji = "➡️"
                    trend_text = f"整体质量稳定 ({avg_change:+.1f}分)"
                    trend_color = "🟡"

                f.write(f"### {trend_emoji} 质量趋势\n\n")
                f.write(f"{trend_color} **{trend_text}**\n\n")

                # 新增IP
                if comparison['new_ips']:
                    f.write(f"### 🆕 新增优质节点 ({len(comparison['new_ips'])}个)\n\n")
                    f.write("| 排名 | IP地址 | 评分 | 延迟 |\n")
                    f.write("|:---:|:---|:---:|:---:|\n")
                    for ip, info in comparison['new_ips'][:5]:  # 只显示前5个
                        # 确保 original 为字符串并安全截断
                        original = str(info.get('original', ip))
                        if len(original) > 30:
                            original = original[:27] + "..."
                        original = self._escape_md_cell(original)
                        score_display = self._format_score(info.get('score'), bold=True)
                        delay_display = self._format_number(info.get('delay'), precision=1, suffix="ms")
                        f.write(f"| {info['rank']} | `{original}` | {score_display} | {delay_display} |\n")
                    if len(comparison['new_ips']) > 5:
                        f.write(f"\n*还有 {len(comparison['new_ips']) - 5} 个新增节点未显示*\n")
                    f.write("\n")

                # 移除IP
                if comparison['removed_ips']:
                    f.write(f"### ❌ 移除的节点 ({len(comparison['removed_ips'])}个)\n\n")
                    f.write("| 原排名 | IP地址 | 原评分 |\n")
                    f.write("|:---:|:---|:---:|\n")
                    for ip, info in comparison['removed_ips'][:5]:
                        # 确保 original 为字符串并安全截断
                        original = str(info.get('original', ip))
                        if len(original) > 30:
                            original = original[:27] + "..."
                        original = self._escape_md_cell(original)
                        score_display = self._format_score(info.get('score'))
                        f.write(f"| {info['rank']} | `{original}` | {score_display} |\n")
                    if len(comparison['removed_ips']) > 5:
                        f.write(f"\n*还有 {len(comparison['removed_ips']) - 5} 个移除节点未显示*\n")
                    f.write("\n")

                # 排名变化
                if comparison['rank_changes']:
                    f.write(f"### 📊 排名变化 (Top 10)\n\n")
                    f.write("| IP地址 | 原排名 | 新排名 | 变化 | 当前评分 |\n")
                    f.write("|:---|:---:|:---:|:---:|:---:|\n")
                    for change in comparison['rank_changes']:
                        # 确保 original 为字符串并安全截断
                        original = str(change.get('original', ''))
                        if len(original) > 25:
                            original = original[:22] + "..."
                        original = self._escape_md_cell(original)

                        if change['rank_diff'] > 0:
                            change_str = f"⬆️ +{change['rank_diff']}"
                        else:
                            change_str = f"⬇️ {change['rank_diff']}"

                        score_display = self._format_score(change.get('score'), bold=True)
                        f.write(f"| `{original}` | {change['old_rank']} | {change['new_rank']} | {change_str} | {score_display} |\n")
                    f.write("\n")

                # 评分变化
                if comparison['score_changes']:
                    f.write(f"### 📈 评分变化 (变化≥5分)\n\n")
                    f.write("| IP地址 | 原评分 | 新评分 | 变化 |\n")
                    f.write("|:---|:---:|:---:|:---:|\n")
                    for change in comparison['score_changes']:
                        # 确保 original 为字符串并安全截断
                        original = str(change.get('original', ''))
                        if len(original) > 30:
                            original = original[:27] + "..."
                        original = self._escape_md_cell(original)

                        score_diff = change.get('score_diff')
                        if score_diff is None:
                            change_str = "N/A"
                        elif score_diff > 0:
                            change_str = f"🟢 +{score_diff:.0f}"
                        else:
                            change_str = f"🔴 {score_diff:.0f}"

                        old_score = self._format_score(change.get('old_score'))
                        new_score = self._format_score(change.get('new_score'))
                        f.write(f"| `{original}` | {old_score} | {new_score} | {change_str} |\n")
                    f.write("\n")

                # 决策建议
                f.write("### 💡 更新建议\n\n")

                new_count = len(comparison['new_ips'])
                removed_count = len(comparison['removed_ips'])
                significant_changes = len([c for c in comparison['rank_changes'] if abs(c['rank_diff']) >= 3])

                if new_count >= 3 or removed_count >= 3 or significant_changes >= 3:
                    f.write("🔴 **建议立即更新代理配置**\n\n")
                    reasons = []
                    if new_count >= 3:
                        reasons.append(f"- 新增了 {new_count} 个优质节点")
                    if removed_count >= 3:
                        reasons.append(f"- 有 {removed_count} 个节点已失效")
                    if significant_changes >= 3:
                        reasons.append(f"- 有 {significant_changes} 个节点排名显著变化")
                    f.write("\n".join(reasons) + "\n\n")
                elif new_count > 0 or removed_count > 0:
                    f.write("🟡 **建议考虑更新代理配置**\n\n")
                    f.write(f"- 有少量节点变动（新增{new_count}个，移除{removed_count}个）\n\n")
                else:
                    f.write("🟢 **当前配置稳定，暂无需更新**\n\n")
                    f.write("- 节点列表无变化，质量稳定\n\n")

                f.write("---\n\n")
            
            # 摘要卡片
            success_count = len([r for r in self.results if r['success']])
            fail_count = len(self.results) - success_count
            f.write("> **📊 测试统计**\n")
            f.write(f"> - 总目标数: `{len(self.results)}`\n")
            f.write(f"> - 成功节点: `{success_count}` ✅\n")
            f.write(f"> - 失败节点: `{fail_count}` ❌\n\n")
            
            f.write("## 📝 排序说明\n")
            f.write("按综合评分降序排列（评分越高表示质量越好）。\n")
            if self.enable_streaming_test:
                f.write("- **网站连通性测试**：仅用于展示，不参与综合评分与排序。\n")
            if self.enable_http_test and not self.score_include_http:
                f.write("- **HTTP性能测试**：仅用于展示，不参与综合评分与排序。\n")
            f.write("\n")
            
            f.write("## 🏆 最佳结果（Top 优质节点）\n\n")
            
            # 创建成功结果的表格
            successful_results = [r for r in sorted_results if r['success']]
            if successful_results:
                f.write("| 排名 | 目标 | 延迟 | 丢包 | 抖动 | TCP连接 | 下载速度 | 地理位置 | 综合评分 | 状态 |\n")
                f.write("|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---:|\n")

                rank = 1
                for result in successful_results:
                    target = result['original']
                    if len(target) > 35:
                        target = target[:32] + "..."
                    target = self._escape_md_cell(target)

                    delay = self._format_number(
                        self._coerce_number(result.get('ping', {}).get('avg_delay')),
                        precision=1,
                        suffix="ms"
                    )
                    loss = self._format_number(
                        self._coerce_number(result.get('ping', {}).get('loss_rate')),
                        precision=1,
                        suffix="%"
                    )
                    jitter = self._format_number(
                        self._coerce_number(result.get('ping', {}).get('jitter')),
                        precision=1,
                        suffix="ms"
                    )

                    tcp_time = "N/A"
                    if result.get('tcp', {}).get('success'):
                        tcp_time = self._format_number(
                            self._coerce_number(result.get('tcp', {}).get('connect_time')),
                            precision=1,
                            suffix="ms"
                        )

                    # 下载速度
                    download_speed = "N/A"
                    download_result = result.get('download', {})
                    if download_result and download_result.get('success'):
                        speed = download_result.get('speed_mbps', 0)
                        download_speed = self._format_number(
                            self._coerce_number(speed),
                            precision=2,
                            suffix=" MB/s"
                        )

                    # 地理位置（优先使用 display_location）
                    location = "Unknown"
                    location_result = result.get('location', {})
                    if location_result and location_result.get('success'):
                        location = location_result.get('display_location', location_result.get('region', 'Unknown'))

                    scores = result.get('scores', {})
                    overall = self._coerce_number(scores.get('overall'))
                    overall_value = overall if overall is not None else 0

                    # 评分条
                    def get_progress_bar(score):
                        filled = int(score / 10)
                        bar = "█" * filled + "░" * (10 - filled)
                        emoji = self._get_score_emoji(score)
                        return f"`{bar}` **{score}** {emoji}"

                    overall_display = get_progress_bar(overall_value)

                    # 前三名高亮
                    rank_str = str(rank)
                    if rank == 1: rank_str = "🥇"
                    elif rank == 2: rank_str = "🥈"
                    elif rank == 3: rank_str = "🥉"

                    f.write(f"| {rank_str} | `{target}` | {delay} | {loss} | {jitter} | {tcp_time} | {download_speed} | `{location}` | {overall_display} | ✅ |\n")
                    rank += 1
            
            # 详细评分表
            if successful_results:
                f.write("\n## 📋 详细场景评分\n\n")
                f.write("| 排名 | 目标 | 综合 | 流媒体 | 游戏 | 实时通信 |\n")
                f.write("|:---:|:---|:---:|:---:|:---:|:---:|\n")
                
                rank = 1
                for result in successful_results:
                    target = result['original']
                    if len(target) > 25: target = target[:22] + "..."
                    target = self._escape_md_cell(target)
                    
                    scores = result.get('scores', {})
                    
                    def fmt_score(s):
                        value = self._coerce_number(s)
                        if value is None:
                            return "N/A"
                        if value >= 80:
                            return f"**{value:.0f}** 🟢"
                        if value >= 60:
                            return f"{value:.0f} 🟡"
                        return f"{value:.0f} 🔴"

                    f.write(f"| {rank} | `{target}` | {fmt_score(scores.get('overall', 0))} | {fmt_score(scores.get('streaming', 0))} | {fmt_score(scores.get('gaming', 0))} | {fmt_score(scores.get('rtc', 0))} |\n")
                    rank += 1

            # IP 详细信息表（如果启用了 IP 信息查询）
            if self.ipinfo_client and successful_results:
                # 检查是否有任何结果包含详细的 IP 信息
                has_detailed_info = any(
                    r.get('location', {}).get('asn') not in ['Unknown', None] or
                    r.get('location', {}).get('organization') not in ['Unknown', None]
                    for r in successful_results
                )

                if has_detailed_info:
                    f.write("\n## 🌐 IP 详细信息\n\n")
                    f.write("| 排名 | 目标 | 地理位置 | ASN | 运营商/组织 | 代理类型 |\n")
                    f.write("|:---:|:---|:---|:---|:---|:---:|\n")

                    rank = 1
                    for result in successful_results:
                        target = result['original']
                        if len(target) > 25:
                            target = target[:22] + "..."
                        target = self._escape_md_cell(target)

                        location_result = result.get('location', {})
                        if location_result and location_result.get('success'):
                            # 地理位置（使用 display_location 或构造）
                            display_loc = location_result.get('display_location', 'Unknown')
                            if display_loc == 'Unknown':
                                region = location_result.get('region', 'Unknown')
                                city = location_result.get('city', '')
                                if city and city != 'Unknown' and city not in region:
                                    display_loc = f"{region}/{city}"
                                else:
                                    display_loc = region

                            # 转义地理位置字符串
                            location_str = self._escape_md_cell(display_loc)

                            # ASN
                            asn = location_result.get('asn', 'Unknown')
                            if asn and asn != 'Unknown':
                                asn_display = f"`{self._escape_md_cell(asn)}`"
                            else:
                                asn_display = "N/A"

                            # 运营商/组织
                            org = location_result.get('organization', 'Unknown')
                            if org and org != 'Unknown':
                                if len(org) > 30:
                                    org = org[:27] + "..."
                                org_display = self._escape_md_cell(org)
                            else:
                                org_display = "N/A"

                            # 代理类型
                            proxy_type = location_result.get('proxy_type', 'Unknown')
                            if proxy_type and proxy_type != 'Unknown':
                                # 转义代理类型
                                proxy_type_escaped = self._escape_md_cell(proxy_type)
                                # 添加图标
                                if 'VPN' in proxy_type:
                                    proxy_display = f"🔒 {proxy_type_escaped}"
                                elif 'Proxy' in proxy_type:
                                    proxy_display = f"🌐 {proxy_type_escaped}"
                                elif 'Tor' in proxy_type:
                                    proxy_display = f"🧅 {proxy_type_escaped}"
                                elif proxy_type == '直连':
                                    proxy_display = "✅ 直连"
                                else:
                                    proxy_display = proxy_type_escaped
                            else:
                                proxy_display = "N/A"

                            f.write(f"| {rank} | `{target}` | {location_str} | {asn_display} | {org_display} | {proxy_display} |\n")
                        else:
                            f.write(f"| {rank} | `{target}` | N/A | N/A | N/A | N/A |\n")

                        rank += 1

            # 失败结果部分
            failed_results = [r for r in sorted_results if not r['success']]
            if failed_results:
                f.write("\n## ❌ 测试失败的目标\n\n")
                f.write("| 目标 | 错误信息 |\n")
                f.write("|:---|:---|\n")
                
                for result in failed_results:
                    target = result['original']
                    error = result.get('error', '未知错误')
                    target = self._escape_md_cell(target)
                    error = self._escape_md_cell(error)
                    f.write(f"| `{target}` | {error} |\n")

            # 流媒体网站测试结果（如果启用）
            if self.enable_streaming_test and any('streaming_summary' in r for r in sorted_results):
                f.write("\n## 网站连通性测试（仅展示）\n\n")
                f.write("说明：该部分用于展示每个IP对指定网站的可达性/TTFB，不参与综合评分与排序。\n\n")

                # 提取网站名称（简化显示）
                site_names = {}
                if self.streaming_sites:
                    for site in self.streaming_sites:
                        # 提取域名作为简称
                        from urllib.parse import urlparse
                        parsed = urlparse(site)
                        domain = parsed.netloc.replace('www.', '')
                        # 进一步简化
                        if 'chatgpt' in domain:
                            site_names[site] = 'ChatGPT'
                        elif 'grok' in domain:
                            site_names[site] = 'Grok'
                        elif 'gemini' in domain:
                            site_names[site] = 'Gemini'
                        elif 'youtube' in domain:
                            site_names[site] = 'YouTube'
                        else:
                            site_names[site] = domain.split('.')[0].title()

                # 创建表头
                header_cols = ['排名', '目标']
                for site in self.streaming_sites:
                    header_cols.append(site_names.get(site, site))
                header_cols.extend(['可用数', '可用率'])

                f.write('| ' + ' | '.join(header_cols) + ' |\n')
                f.write('|' + '|'.join(['------' for _ in header_cols]) + '|\n')

                # 保持与综合评分排序一致：仅展示，不对网站可用性再排序
                overall_rank = 0

                # 写入数据行（排名使用综合评分的排名）
                for result in sorted_results:
                    if not result.get('success'):
                        continue

                    overall_rank += 1

                    if not result.get('streaming_summary'):
                        continue
                    target = result['original']
                    if len(target) > 25:
                        target = target[:22] + "..."
                    target = self._escape_md_cell(target)

                    row = [str(overall_rank), target]

                    # 每个网站的测试结果
                    sites_data = result.get('streaming_sites', {})
                    for site in self.streaming_sites:
                        site_result = sites_data.get(site, {})
                        if site_result.get('success'):
                            ttfb = site_result.get('ttfb')
                            if ttfb:
                                row.append(f"✅ {ttfb:.0f}ms")
                            else:
                                row.append("✅")
                        else:
                            error = site_result.get('error', '失败')
                            # 简化错误信息
                            if '超时' in error:
                                row.append("❌ 超时")
                            elif 'HTTP' in error:
                                row.append(f"❌ {error}")
                            else:
                                row.append("❌ 失败")

                    # 可用数和可用率
                    summary = result['streaming_summary']
                    available = summary['available_count']
                    total = summary['total_count']
                    rate = summary['availability_rate']
                    row.append(f"{available}/{total}")
                    row.append(f"{rate:.0f}%")

                    f.write('| ' + ' | '.join(row) + ' |\n')

                f.write("\n### 网站连通性说明\n")
                f.write("- ✅ 表示网站可访问，数字为首字节响应时间（TTFB）\n")
                f.write("- ❌ 表示网站不可访问或超时\n")
                f.write("- 可用率 = 可访问网站数 / 总测试网站数\n")
                f.write("- 该部分不参与综合评分与排序\n\n")

            # 添加评分说明
            f.write("\n## 评分说明\n\n")
            f.write("评分范围：0-100分，分数越高表示质量越好\n\n")
            f.write("- 🟢 优秀 (80-100): 网络质量很好，适合所有应用\n")
            f.write("- 🟡 良好 (60-79): 网络质量良好，大部分应用运行流畅\n")
            f.write("- 🟠 一般 (40-59): 网络质量一般，某些应用可能会有问题\n")
            f.write("- 🔴 较差 (0-39): 网络质量较差，建议更换节点或优化网络\n\n")
            
            f.write("### 各项评分含义\n")
            f.write("- **综合评分**: 总体网络质量评估（加权平均）\n")
            f.write("- **流媒体评分**: 适合视频流媒体、大文件下载\n")
            f.write("- **游戏评分**: 适合在线游戏、实时对战\n")
            f.write("- **实时通信评分**: 适合视频通话、语音聊天\n\n")
            
            f.write("### 指标说明\n")
            f.write("- **延迟**: 数据包往返时间，越低越好\n")
            f.write("- **丢包率**: 数据包丢失比例，越低越好\n")
            f.write("- **抖动**: 延迟的变化程度，越低越稳定\n")
            f.write("- **TCP连接时间**: TCP握手建立时间，反映连接速度\n")
        
        print(f"Markdown格式结果已保存到: {output_file}")
    
    def get_country_from_ip(self, ip: str) -> Tuple[str, str]:
        """
        查询IP的国家信息（支持多个API源）
        
        Args:
            ip: IP地址或域名
            
        Returns:
            Tuple[国家代码, 国家名称] 例如: ('KR', 'South Korea')
            查询失败时返回 ('未知', 'Unknown')
        """
        # 先检查是否是域名，如果是则解析为IP
        target_ip = ip
        if not self._is_valid_ip(ip):
            try:
                target_ip = socket.gethostbyname(ip)
            except socket.gaierror:
                return ('未知', 'Unknown')
        
        # API列表，按优先级排序
        apis = [
            {
                'name': 'ipapi.co',
                'url': f'https://ipapi.co/{target_ip}/json/',
                'code_key': 'country_code',
                'name_key': 'country_name'
            },
            {
                'name': 'ipinfo.io',
                'url': f'https://ipinfo.io/{target_ip}/json',
                'code_key': 'country',
                'name_key': 'country'
            },
            {
                'name': 'freegeoip.app',
                'url': f'https://freegeoip.app/json/{target_ip}',
                'code_key': 'country_code',
                'name_key': 'country_name'
            }
        ]
        
        # 尝试每个API
        for api in apis:
            try:
                with urllib.request.urlopen(api['url'], timeout=5) as response:
                    data = json.load(response)
                    
                    # 获取国家代码和名称
                    code = data.get(api['code_key'], '未知')
                    name = data.get(api['name_key'], 'Unknown')
                    
                    # 如果获取到有效数据，返回结果
                    if code and code != '未知' and code != 'Unknown':
                        return (code, name)
            except Exception:
                continue
        
        # 所有API都失败，返回未知
        return ('未知', 'Unknown')
    
    def _is_valid_ip(self, address: str) -> bool:
        """
        检查字符串是否为有效的IP地址
        
        Args:
            address: 要检查的字符串
            
        Returns:
            True如果是有效IP，False否则
        """
        try:
            socket.inet_aton(address)
            return True
        except socket.error:
            try:
                socket.inet_pton(socket.AF_INET6, address)
                return True
            except:
                return False

    def save_best_results(self, output_file: str = 'best.txt', top_n: int = 15):
        """
        保存前N名结果到文件（干净格式，无广告）

        格式: IP:端口#地区标识
        示例: 168.138.165.174:443#SG

        地区标识优先从输入注释提取（#后、-前的部分），
        否则使用地理位置查询结果

        Args:
            output_file: 输出文件名
            top_n: 保存前N个结果
        """
        # 按综合评分排序
        sorted_results = self.sort_results('overall')

        # 过滤成功的结果，取前N个
        top_results = [r for r in sorted_results if r['success']][:top_n]

        if not top_results:
            print(f"警告: 没有成功的测试结果，{output_file}未更新")
            return

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for result in top_results:
                # 获取基础信息
                original = result['original']
                clean_target = result['target']

                # 提取端口（如果有）
                port = ""
                if ':' in original and original.count(':') <= 1:
                    parts = original.split(':')
                    if len(parts) == 2:
                        port_part = parts[1].split('#')[0]
                        if port_part.isdigit():
                            port = f":{port_part}"

                # 解析地区标识（优先测试结果，其次注释，最后地理查询）
                location_tag = self._resolve_location_tag(clean_target, original, result)

                # 组合新行: IP:端口#地区标识
                new_line = f"{clean_target}{port}#{location_tag}\n"
                f.write(new_line)

        print(f"[OK] 已将前{len(top_results)}个优质节点保存到 {output_file}（干净格式）")
        print("\n保存的节点:")
        for i, result in enumerate(top_results, 1):
            original = result['original']
            clean_target = result['target']

            # 提取端口
            port = ""
            if ':' in original and original.count(':') <= 1:
                parts = original.split(':')
                if len(parts) == 2:
                    port_part = parts[1].split('#')[0]
                    if port_part.isdigit():
                        port = f":{port_part}"

            # 提取地区标识（与保存逻辑一致）
            location_tag = self._resolve_location_tag(clean_target, original, result)

            print(f"  {i}. {clean_target}{port}#{location_tag}")

    def display_summary(self, top_n: int = 20):
        """
        显示测试摘要
        
        Args:
            top_n: 显示前N个结果
        """
        sorted_results = self.sort_results('overall')
        successful_results = [r for r in sorted_results if r['success']]
        
        print(f"\n{self.CLR_BOLD}{self.CLR_C}{'='*130}{self.CLR_0}")
        print(f"{self.CLR_BOLD}{self.CLR_C}前{min(top_n, len(successful_results))}个最佳结果（按综合评分排序）:{self.CLR_0}")
        print(f"{self.CLR_BOLD}{self.CLR_C}{'='*130}{self.CLR_0}")
        
        headers = ["目标", "延迟", "丢包率", "抖动", "TCP", "综合", "流媒体", "游戏", "通话"]
        print(f"{self.CLR_BOLD}{headers[0]:<30} {headers[1]:<8} {headers[2]:<10} {headers[3]:<8} "
              f"{headers[4]:<8} {headers[5]:<8} {headers[6]:<10} {headers[7]:<8} {headers[8]:<8}{self.CLR_0}")
        print(f"{'-'*130}")
        
        for i, result in enumerate(successful_results[:top_n]):
            target = result['original'][:28] + ".." if len(result['original']) > 28 else result['original']
            delay = f"{result['ping'].get('avg_delay', 0):.1f}"
            loss = f"{result['ping'].get('loss_rate', 0):.1f}%"
            jitter = f"{result['ping'].get('jitter', 0):.1f}"
            
            tcp = "N/A"
            if result['tcp'].get('success'):
                tcp = f"{result['tcp'].get('connect_time', 0):.1f}"
            
            scores = result['scores']
            overall = scores.get('overall', 0)
            streaming = scores.get('streaming', 0)
            gaming = scores.get('gaming', 0)
            rtc = scores.get('rtc', 0)
            
            # 使用颜色
            color = self._get_score_color(overall)
            emoji = self._get_score_emoji(overall)
            
            print(f"{color}{target:<30} {delay:<8} {loss:<10} {jitter:<8} "
                  f"{tcp:<8} {overall:<8} {streaming:<10} {gaming:<8} {rtc:<8} {emoji}{self.CLR_0}")


def read_targets_from_file(filename: str = 'ip.txt') -> List[str]:
    """
    从文件读取目标列表
    
    Args:
        filename: 输入文件名
        
    Returns:
        目标列表
    """
    targets = []
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    targets.append(line)
    except UnicodeDecodeError:
        with open(filename, 'r', encoding='gbk') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    targets.append(line)
    except FileNotFoundError:
        print(f"错误: 文件 {filename} 不存在")
        return []  # 改为返回空列表而不是退出，允许URL获取继续

    return targets


def load_targets(config: Dict) -> List[str]:
    """
    统一的目标加载函数，支持文件、URL和自定义文件三种方式

    Args:
        config: 配置字典

    Returns:
        目标列表
    """
    targets = []

    # ========== 新增：自定义文件配置 ==========
    enable_custom = config.get('enable_custom_file', False)
    custom_file = config.get('custom_file_path', 'data/input/custom.txt')
    custom_priority = config.get('custom_file_priority', 'before_url')

    custom_targets = []
    if enable_custom:
        print("\n" + "=" * 100)
        print("读取自定义文件")
        print("=" * 100)

        custom_targets = read_targets_from_file(custom_file)

        if custom_targets:
            print(f"\n[OK] 从自定义文件成功读取 {len(custom_targets)} 个目标")

            # 如果优先级是before_url，立即合并
            if custom_priority == 'before_url':
                targets.extend(custom_targets)
        else:
            print(f"\n[WARN] 自定义文件读取失败或为空")
    # ========== 自定义文件配置结束 ==========

    # 1. 检查是否启用URL获取
    enable_url = config.get('enable_url_fetch', False)
    url_sources = config.get('url_sources', [])
    merge_mode = config.get('merge_file_and_url', False)
    fallback_to_file = config.get('fallback_to_file', True)

    # 2. 从URL获取
    if enable_url and url_sources:
        print("\n" + "=" * 100)
        print("从URL获取IP列表")
        print("=" * 100)

        url_targets = fetch_targets_from_urls(url_sources, config)

        if url_targets:
            print(f"\n[OK] 从URL成功获取 {len(url_targets)} 个目标")
            targets.extend(url_targets)
        else:
            print("\n[WARN] 从URL获取失败或结果为空")

    # ========== 新增：处理after_url优先级 ==========
    if enable_custom and custom_priority == 'after_url' and custom_targets:
        targets.extend(custom_targets)
    # ========== 优先级处理结束 ==========

    # 3. 从文件获取
    file_path = 'data/input/testip.txt'

    # 决定是否读取文件
    should_read_file = False
    if not enable_url and not enable_custom:
        # 未启用URL和自定义文件，使用文件（默认行为）
        should_read_file = True
    elif merge_mode or (enable_custom and config.get('merge_custom_with_url', True)):
        # 合并模式，同时读取文件
        should_read_file = True
    elif not targets and fallback_to_file:
        # URL失败且启用回退
        should_read_file = True
        print("\n回退到文件读取模式...")

    if should_read_file:
        print(f"\n读取测试目标文件: {file_path}")
        file_targets = read_targets_from_file(file_path)

        if file_targets:
            print(f"[OK] 从文件成功读取 {len(file_targets)} 个目标")
            targets.extend(file_targets)
        else:
            print(f"[WARN] 文件读取失败或为空")

    # 4. 去重
    if targets:
        unique_targets = []
        seen = set()
        for target in targets:
            if target not in seen:
                seen.add(target)
                unique_targets.append(target)

        if len(targets) != len(unique_targets):
            print(f"\n去重: {len(targets)} -> {len(unique_targets)} 个目标")

        return unique_targets

    return targets


def main():
    """主函数（增强版）"""
    print("=" * 100)
    print("高级IP/域名质量测试工具 - 代理/VPN专用优化版")
    print("基于专业网络质量评估算法（延迟、丢包率、抖动、TCP、HTTP、稳定性、综合评分）")
    print("=" * 100)

    # 1. 加载配置（使用balanced模式）
    config = load_config(test_mode='balanced')

    # 2. 加载测试目标（统一接口，支持文件和URL）
    targets = load_targets(config)

    if not targets:
        print("\n错误: 没有找到可测试的目标")
        print("请检查:")
        print("  1. 配置文件中的URL列表是否正确")
        print("  2. data/input/testip.txt 文件是否存在且包含有效数据")
        sys.exit(1)

    print(f"\n总计: {len(targets)} 个测试目标")
    print("=" * 100)

    # 3. 显示测试配置
    print(f"\n测试模式: {config['test_mode']}")
    print(f"  - 快速检测: {'启用' if config['enable_quick_check'] else '禁用'}")
    print(f"  - HTTP测试: {'启用' if config['enable_http_test'] else '禁用'}")
    if config.get('enable_http_test') and not config.get('score_include_http', True):
        print("  - HTTP计分: 不参与（仅展示）")
    print(f"  - 稳定性测试: {'启用' if config['enable_stability_test'] else '禁用'}")
    print(f"  - 并发数: 快速检测{config['quick_check_workers']}，深度测试{config['max_workers']}")
    print()

    # 4. 创建测试器
    tester = AdvancedIPTester(config)

    # 5. 开始测试（使用两阶段测试流程）
    start_time = time.time()
    tester.test_targets_two_phase(targets)
    elapsed_time = time.time() - start_time

    print(f"\n总测试时间: {elapsed_time:.1f}秒")

    # 5. 显示摘要
    tester.display_summary(20)

    # 6. 保存完整结果（Markdown格式，更易查看）
    tester.save_results_md('data/output/result_pro.md')

    # 7. 保存历史记录（用于下次对比）
    print("\n" + "="*60)
    print("保存历史记录用于下次对比...")
    print("="*60 + "\n")
    tester.save_history('data/output/result_history.json')
    print("[OK] 历史记录已保存到 data/output/result_history.json")

    # 8. 同时保存一份txt格式作为备份
    tester.save_results('data/output/result_pro.txt')

    # 9. 保存干净格式的best.txt（使用地区标识，注释优先）
    print("\n" + "="*60)
    print("生成优质节点列表（干净格式）...")
    print("="*60 + "\n")
    tester.save_best_results('data/output/best.txt', tester.max_results)

    print(f"\n测试完成！")
    print(f"主要结果（Markdown格式，推荐）: data/output/result_pro.md")
    print(f"备份结果（文本格式）: data/output/result_pro.txt")
    print(f"优质节点列表（干净格式）: data/output/best.txt")
    print(f"历史记录（用于对比）: data/output/result_history.json")
    print("结果包含：延迟、丢包率、抖动、TCP连接时间、综合评分、流媒体评分、游戏评分、实时通信评分")
    print("Markdown文件可以用浏览器、Markdown编辑器或支持Markdown的文本编辑器查看")
    print("best.txt包含格式: IP:端口#地区标识（注释优先，否则使用地理查询结果）")
    print("\n💡 提示：下次运行时会自动对比历史记录，显示IP变动情况！")


if __name__ == '__main__':
    main()
