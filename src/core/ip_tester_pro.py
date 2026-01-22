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
import statistics
import socket
import threading
import urllib.request
import json
import ssl
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入新模块
try:
    from src.config.config import load_config, HTTP_TEST_URLS
    from src.analyzers.statistical_analyzer import StatisticalAnalyzer
    from src.analyzers.proxy_score_calculator import ProxyScoreCalculator
    from src.utils.url_fetcher import fetch_targets_from_urls
except ImportError:
    # 如果导入失败，使用默认值（向后兼容）
    HTTP_TEST_URLS = ['https://cp.cloudflare.com/generate_204']
    StatisticalAnalyzer = None
    ProxyScoreCalculator = None
    # URL获取模块向后兼容
    def fetch_targets_from_urls(urls, config=None):
        print("警告: URL获取模块未安装")
        return []
    def load_config(custom_config=None, test_mode=None):
        return custom_config or {}


class AdvancedIPTester:
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

        # 新增配置参数
        self.enable_quick_check = self.config.get('enable_quick_check', True)
        self.quick_check_workers = self.config.get('quick_check_workers', 50)
        self.quick_ping_count = self.config.get('quick_ping_count', 1)
        self.quick_ping_timeout = self.config.get('quick_ping_timeout', 1)
        self.quick_tcp_timeout = self.config.get('quick_tcp_timeout', 2)
        self.enable_http_test = self.config.get('enable_http_test', True)
        self.http_test_url = self.config.get('http_test_url', HTTP_TEST_URLS[0])
        self.http_timeout = self.config.get('http_timeout', 10)
        self.enable_stability_test = self.config.get('enable_stability_test', True)
        self.stability_attempts = self.config.get('stability_attempts', 10)

        # 流媒体测试配置（新增）
        self.enable_streaming_test = self.config.get('enable_streaming_test', False)
        self.streaming_sites = self.config.get('streaming_sites', [])
        self.streaming_timeout = self.config.get('streaming_timeout', 15)
        self.streaming_concurrent = self.config.get('streaming_concurrent', True)

        # 输出配置（新增）
        self.max_results = self.config.get('max_results', 30)

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
            'total_time': None,  # 总响应时间（ms）
            'status_code': None,
            'error': None
        }

        try:
            start_time = time.time()

            # 创建HTTP请求
            req = urllib.request.Request(
                self.http_test_url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )

            # 创建SSL上下文（忽略证书验证以提高速度）
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # 发送请求
            with urllib.request.urlopen(req, timeout=self.http_timeout, context=ctx) as response:
                # 记录首字节时间
                ttfb_time = time.time()
                result['ttfb'] = (ttfb_time - start_time) * 1000

                # 读取响应
                response.read()

                # 记录总时间
                end_time = time.time()
                result['total_time'] = (end_time - start_time) * 1000
                result['status_code'] = response.status
                result['success'] = True

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

    def test_streaming_sites(self, target: str, port: int = 443) -> Dict:
        """
        测试流媒体网站连通性和延迟

        测试指定代理节点对多个流媒体网站的访问能力。
        注意：当前实现为直连测试，不经过代理。

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
                    executor.submit(self._test_single_streaming_site, site): site
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
                results['sites'][site] = self._test_single_streaming_site(site)

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

    def _test_single_streaming_site(self, site_url: str) -> Dict:
        """
        测试单个流媒体网站

        Args:
            site_url: 网站URL

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
            start_time = time.time()

            # 创建HTTP请求
            req = urllib.request.Request(
                site_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )

            # 创建SSL上下文
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # 发送请求
            with urllib.request.urlopen(req, timeout=self.streaming_timeout, context=ctx) as response:
                # 记录首字节时间
                ttfb_time = time.time()
                result['ttfb'] = (ttfb_time - start_time) * 1000

                # 读取少量数据（不需要完整响应）
                response.read(1024)

                # 记录总时间
                end_time = time.time()
                result['total_time'] = (end_time - start_time) * 1000
                result['status_code'] = response.status
                result['success'] = True

        except urllib.error.HTTPError as e:
            result['status_code'] = e.code
            if e.code in [200, 301, 302, 403]:  # 某些状态码也算可访问
                result['success'] = True
                result['error'] = f'HTTP {e.code}'
            else:
                result['error'] = f'HTTP错误: {e.code}'
        except urllib.error.URLError as e:
            result['error'] = f'URL错误: {str(e.reason)}'
        except socket.timeout:
            result['error'] = '连接超时'
        except Exception as e:
            result['error'] = f'未知错误: {str(e)}'

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
                scores = ProxyScoreCalculator.calculate_proxy_score(result)
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
        # 使用锁确保输出不混乱
        with self.print_lock:
            # 显示进度
            print(f"[{idx+1}/{total}] ", end='', flush=True)
            
            # 执行测试（test_target内部的打印也会受到锁保护）
            result = self.test_target(target)
            
            # 如果测试失败，显示失败信息
            if not result['success']:
                print(f"{target}: 失败 - {result.get('error', '未知错误')}")
        
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

    def sort_results(self, sort_by: str = 'overall') -> List[Dict]:
        """
        对结果进行排序
        
        Args:
            sort_by: 排序依据，可选 'overall', 'streaming', 'gaming', 'rtc', 'delay', 'loss'
            
        Returns:
            排序后的结果列表
        """
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
            
            # 写入列标题
            headers = [
                "排名", "目标", "延迟(ms)", "丢包率(%)", "抖动(ms)",
                "TCP连接(ms)", "综合评分", "流媒体", "游戏", "实时通信", "状态"
            ]
            f.write(f"{headers[0]:<4} {headers[1]:<30} {headers[2]:<10} {headers[3]:<10} "
                   f"{headers[4]:<10} {headers[5]:<12} {headers[6]:<10} {headers[7]:<10} "
                   f"{headers[8]:<10} {headers[9]:<10} {headers[10]:<10}\n")
            f.write("-" * 130 + "\n")
            
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
                    
                    scores = result['scores']
                    overall = str(scores.get('overall', 0))
                    streaming = str(scores.get('streaming', 0))
                    gaming = str(scores.get('gaming', 0))
                    rtc = str(scores.get('rtc', 0))
                    
                    f.write(f"{rank:<4} {target:<30} {delay:<10} {loss:<10} "
                           f"{jitter:<10} {tcp_time:<12} {overall:<10} "
                           f"{streaming:<10} {gaming:<10} {rtc:<10} 成功\n")
                    rank += 1

            # 流媒体测试摘要（如果启用）
            if self.enable_streaming_test and any('streaming_summary' in r for r in sorted_results):
                f.write("\n" + "=" * 100 + "\n")
                f.write("流媒体网站可用性测试摘要:\n")
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
    
    def save_results_md(self, output_file: str = 'result_pro.md'):
        """
        保存结果到markdown格式文件
        
        Args:
            output_file: 输出文件名
        """
        sorted_results = self.sort_results('overall')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # 写入markdown标题
            f.write(f"# IP/域名质量测试报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**测试目标数**: {len(self.results)}\n")
            f.write(f"**成功数**: {len([r for r in self.results if r['success']])}\n")
            f.write(f"**失败数**: {len([r for r in self.results if not r['success']])}\n\n")
            
            f.write("## 排序说明\n")
            f.write("按综合评分降序排列（评分越高表示质量越好）\n\n")
            
            f.write("## 最佳结果（按综合评分排序）\n\n")
            
            # 创建成功结果的表格
            successful_results = [r for r in sorted_results if r['success']]
            if successful_results:
                f.write("| 排名 | 目标 | 延迟(ms) | 丢包率(%) | 抖动(ms) | TCP连接(ms) | 综合评分 | 流媒体 | 游戏 | 实时通信 | 状态 |\n")
                f.write("|------|------|----------|-----------|----------|-------------|----------|--------|------|----------|------|\n")
                
                rank = 1
                for result in successful_results:
                    target = result['original']
                    if len(target) > 30:
                        target = target[:27] + "..."
                    
                    delay = f"{result['ping'].get('avg_delay', 0):.1f}"
                    loss = f"{result['ping'].get('loss_rate', 0):.1f}"
                    jitter = f"{result['ping'].get('jitter', 0):.1f}"
                    
                    tcp_time = "N/A"
                    if result['tcp'].get('success'):
                        tcp_time = f"{result['tcp'].get('connect_time', 0):.1f}"
                    
                    scores = result['scores']
                    overall = scores.get('overall', 0)
                    streaming = scores.get('streaming', 0)
                    gaming = scores.get('gaming', 0)
                    rtc = scores.get('rtc', 0)
                    
                    # 根据评分添加颜色或表情符号
                    def get_score_emoji(score):
                        if score >= 80:
                            return f"{score} 🟢"
                        elif score >= 60:
                            return f"{score} 🟡"
                        elif score >= 40:
                            return f"{score} 🟠"
                        else:
                            return f"{score} 🔴"
                    
                    overall_display = get_score_emoji(overall)
                    streaming_display = get_score_emoji(streaming)
                    gaming_display = get_score_emoji(gaming)
                    rtc_display = get_score_emoji(rtc)
                    
                    f.write(f"| {rank} | {target} | {delay} | {loss} | {jitter} | {tcp_time} | {overall_display} | {streaming_display} | {gaming_display} | {rtc_display} | ✅ |\n")
                    rank += 1
            
            # 失败结果部分
            failed_results = [r for r in sorted_results if not r['success']]
            if failed_results:
                f.write("\n## 测试失败的目标\n\n")
                f.write("| 目标 | 错误信息 |\n")
                f.write("|------|----------|\n")
                
                for result in failed_results:
                    target = result['original']
                    if len(target) > 40:
                        target = target[:37] + "..."
                    error = result.get('error', '未知错误')
                    f.write(f"| {target} | {error} |\n")

            # 流媒体网站测试结果（如果启用）
            if self.enable_streaming_test and any('streaming_summary' in r for r in sorted_results):
                f.write("\n## 流媒体网站可用性测试\n\n")

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

                # 按可用数和平均延迟排序
                streaming_results = [r for r in sorted_results if r.get('streaming_summary')]
                streaming_results.sort(
                    key=lambda x: (
                        -x['streaming_summary']['available_count'],
                        x['streaming_summary'].get('avg_ttfb', 999999) or 999999
                    )
                )

                # 写入数据行
                for rank, result in enumerate(streaming_results, 1):
                    target = result['original']
                    if len(target) > 25:
                        target = target[:22] + "..."

                    row = [str(rank), target]

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

                f.write("\n### 流媒体测试说明\n")
                f.write("- ✅ 表示网站可访问，数字为首字节响应时间（TTFB）\n")
                f.write("- ❌ 表示网站不可访问或超时\n")
                f.write("- 可用率 = 可访问网站数 / 总测试网站数\n\n")

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
    
    def generate_new_alias(self, result: Dict) -> str:
        """
        生成新别名格式: #域名/IP-国家-延迟ms-综合评分
        
        示例: #104.19.174.68-US-64ms-97分
        
        Args:
            result: 测试结果字典
            
        Returns:
            新别名字符串
        """
        # 获取原始目标（包含域名）或清理后的IP
        original_target = result['original']
        clean_target = result['target']
        
        # 从原始目标中提取域名/IP部分（移除端口和注释）
        display_target = clean_target
        if '#' in original_target:
            # 如果有注释，尝试提取注释前的IP/域名部分
            base_part = original_target.split('#')[0].strip()
            # 如果有端口，提取IP/域名部分
            if ':' in base_part and base_part.count(':') <= 1:
                display_target = base_part.split(':')[0].strip()
            else:
                display_target = base_part
        elif ':' in original_target and original_target.count(':') <= 1:
            # 如果有端口但没有注释
            display_target = original_target.split(':')[0].strip()
        
        # 获取地理位置
        country_code, _ = self.get_country_from_ip(clean_target)
        
        # 获取测试数据
        delay = int(result['ping']['avg_delay'])
        score = result['scores']['overall']
        
        # 生成别名（包含IP/域名）
        return f"#{display_target}-{country_code}-{delay}ms-{score}分"
    
    def save_top_results(self, output_file: str = 'ip.txt', top_n: int = 15):
        """
        保存前N名结果到文件（带新别名）
        
        格式: IP:端口#国家-延迟ms-综合评分
        
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
                    if len(parts) == 2 and parts[1].split('#')[0].isdigit():
                        port = f":{parts[1].split('#')[0]}"
                
                # 生成新别名
                new_alias = self.generate_new_alias(result)
                
                # 组合新行: IP:端口#新别名
                new_line = f"{clean_target}{port}{new_alias}\n"
                f.write(new_line)
        
        print(f"[OK] 已将前{len(top_results)}个优质节点保存到 {output_file}")
        print("\n保存的节点:")
        for i, result in enumerate(top_results, 1):
            alias = self.generate_new_alias(result)
            print(f"  {i}. {result['target']}{alias}")

    def save_best_results(self, output_file: str = 'best.txt', top_n: int = 15):
        """
        保存前N名结果到文件（干净格式，无广告）

        格式: IP:端口#国家代码
        示例: 168.138.165.174:443#SG

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

                # 从原始输入中提取国家代码
                country_code = None
                if '#' in original:
                    # 格式: IP:port#Country-频道@kejiland00
                    # 提取#后面的部分
                    comment_part = original.split('#')[1]
                    # 提取国家代码（在-之前）
                    if '-' in comment_part:
                        country_code = comment_part.split('-')[0].strip()
                    else:
                        # 如果没有-，可能是广告信息，忽略
                        if '频道' in comment_part or '@' in comment_part or '加入' in comment_part:
                            country_code = None
                        else:
                            # 否则整个就是国家代码
                            country_code = comment_part.strip()

                # 如果没有从原始输入提取到，尝试查询地理位置
                if not country_code:
                    # 判断是否为域名（包含字母）
                    if any(c.isalpha() for c in clean_target):
                        # 域名直接使用自身作为标识
                        country_code = clean_target
                    else:
                        # IP地址才查询地理位置
                        country_code, _ = self.get_country_from_ip(clean_target)
                        if not country_code:
                            country_code = clean_target  # 如果查询失败，使用IP本身

                # 组合新行: IP:端口#国家代码
                new_line = f"{clean_target}{port}#{country_code}\n"
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

            # 提取国家代码（与保存逻辑一致）
            country_code = None
            if '#' in original:
                comment_part = original.split('#')[1]
                if '-' in comment_part:
                    country_code = comment_part.split('-')[0].strip()
                else:
                    # 如果没有-，可能是广告信息，忽略
                    if '频道' in comment_part or '@' in comment_part or '加入' in comment_part:
                        country_code = None
                    else:
                        country_code = comment_part.strip()

            if not country_code:
                # 判断是否为域名（包含字母）
                if any(c.isalpha() for c in clean_target):
                    # 域名直接使用自身作为标识
                    country_code = clean_target
                else:
                    # IP地址才查询地理位置
                    country_code, _ = self.get_country_from_ip(clean_target)
                    if not country_code:
                        country_code = clean_target

            print(f"  {i}. {clean_target}{port}#{country_code}")

    def display_summary(self, top_n: int = 20):
        """
        显示测试摘要
        
        Args:
            top_n: 显示前N个结果
        """
        sorted_results = self.sort_results('overall')
        successful_results = [r for r in sorted_results if r['success']]
        
        print(f"\n{'='*130}")
        print(f"前{min(top_n, len(successful_results))}个最佳结果（按综合评分排序）:")
        print(f"{'='*130}")
        
        headers = ["目标", "延迟", "丢包率", "抖动", "TCP", "综合", "流媒体", "游戏", "通话"]
        print(f"{headers[0]:<30} {headers[1]:<8} {headers[2]:<10} {headers[3]:<8} "
              f"{headers[4]:<8} {headers[5]:<8} {headers[6]:<10} {headers[7]:<8} {headers[8]:<8}")
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
            overall = str(scores.get('overall', 0))
            streaming = str(scores.get('streaming', 0))
            gaming = str(scores.get('gaming', 0))
            rtc = str(scores.get('rtc', 0))
            
            print(f"{target:<30} {delay:<8} {loss:<10} {jitter:<8} "
                  f"{tcp:<8} {overall:<8} {streaming:<10} {gaming:<8} {rtc:<8}")


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

    # 7. 同时保存一份txt格式作为备份
    tester.save_results('data/output/result_pro.txt')

    # 8. 保存前15名到ip.txt（带地理位置别名）
    print("\n" + "="*60)
    print("筛选质量最好的15个节点并生成地理位置别名...")
    print("="*60 + "\n")
    tester.save_top_results('data/output/ip.txt', 15)

    # 9. 保存干净格式的best.txt（无广告）
    print("\n" + "="*60)
    print("生成干净格式的优质节点列表...")
    print("="*60 + "\n")
    tester.save_best_results('data/output/best.txt', tester.max_results)

    print(f"\n测试完成！")
    print(f"主要结果（Markdown格式，推荐）: data/output/result_pro.md")
    print(f"备份结果（文本格式）: data/output/result_pro.txt")
    print(f"优质节点列表（详细信息）: data/output/ip.txt")
    print(f"优质节点列表（干净格式）: data/output/best.txt")
    print("结果包含：延迟、丢包率、抖动、TCP连接时间、综合评分、流媒体评分、游戏评分、实时通信评分")
    print("Markdown文件可以用浏览器、Markdown编辑器或支持Markdown的文本编辑器查看")
    print("ip.txt包含格式: IP:端口#国家-延迟ms-综合评分")
    print("best.txt包含格式: IP:端口#国家代码（干净格式，无广告）")


if __name__ == '__main__':
    main()