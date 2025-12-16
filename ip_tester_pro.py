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
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


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
        self.results = []
        
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
        delay = ping_result.get('avg_delay', 1000) or 1000
        loss = ping_result.get('loss_rate', 100) or 100
        jitter = ping_result.get('jitter', 100) or 100
        tcp_time = tcp_result.get('connect_time', 1000) or 1000
        
        # 1. 流媒体评分（下载带宽 + 空载延迟 + 丢包率 + 负载延迟差值）
        # 简化版：只考虑延迟、丢包、抖动
        streaming_score = 100
        
        # 延迟扣分（<50ms不扣分，50-100ms扣10分，100-200ms扣30分，>200ms扣50分）
        if delay > 200:
            streaming_score -= 50
        elif delay > 100:
            streaming_score -= 30
        elif delay > 50:
            streaming_score -= 10
        
        # 丢包扣分（<1%不扣分，1-5%扣20分，>5%扣50分）
        if loss > 5:
            streaming_score -= 50
        elif loss > 1:
            streaming_score -= 20
        
        # 抖动扣分（<20ms不扣分，20-50ms扣10分，>50ms扣30分）
        if jitter > 50:
            streaming_score -= 30
        elif jitter > 20:
            streaming_score -= 10
        
        streaming_score = max(0, streaming_score)
        
        # 2. 游戏评分（丢包率 + 空载延迟 + 负载延迟差值）
        gaming_score = 100
        
        # 游戏对丢包敏感
        if loss > 1:
            gaming_score -= 40
        elif loss > 0.5:
            gaming_score -= 20
        
        # 游戏对延迟敏感
        if delay > 100:
            gaming_score -= 40
        elif delay > 50:
            gaming_score -= 20
        
        # 游戏对抖动敏感
        if jitter > 30:
            gaming_score -= 20
        elif jitter > 10:
            gaming_score -= 10
        
        gaming_score = max(0, gaming_score)
        
        # 3. 实时通信评分（丢包率 + 抖动 + 空载延迟 + 负载延迟差值）
        rtc_score = 100
        
        # RTC对丢包非常敏感
        if loss > 2:
            rtc_score -= 50
        elif loss > 1:
            rtc_score -= 30
        elif loss > 0.5:
            rtc_score -= 15
        
        # RTC对抖动非常敏感
        if jitter > 30:
            rtc_score -= 40
        elif jitter > 20:
            rtc_score -= 25
        elif jitter > 10:
            rtc_score -= 10
        
        # RTC对延迟敏感
        if delay > 150:
            rtc_score -= 25
        elif delay > 100:
            rtc_score -= 15
        elif delay > 50:
            rtc_score -= 5
        
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
        """清理目标字符串，移除端口和注释"""
        clean_target = target.strip()
        if '#' in clean_target:
            clean_target = clean_target.split('#')[0].strip()
        if ':' in clean_target:
            clean_target = clean_target.split(':')[0].strip()
        return clean_target
    
    def test_target(self, target: str) -> Dict:
        """
        测试单个目标
        
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
            'scores': {},
            'success': False,
            'error': None
        }
        
        try:
            # 1. Ping测试
            print(f"测试Ping: {result['target']}...")
            ping_result = self._run_ping_test(result['target'])
            result['ping'] = ping_result
            
            # 2. TCP测试（默认测试443端口，如果目标包含其他端口则使用该端口）
            test_port = 443
            if ':' in target:
                try:
                    port_part = target.split(':')[1]
                    if '#' in port_part:
                        port_part = port_part.split('#')[0]
                    test_port = int(port_part)
                except:
                    pass
            
            print(f"测试TCP连接: {result['target']}:{test_port}...")
            tcp_result = self.test_tcp_connection(result['target'], test_port)
            result['tcp'] = tcp_result
            
            # 3. 计算评分
            if ping_result['success']:
                scores = self.calculate_quality_score(ping_result, tcp_result)
                result['scores'] = scores
                result['success'] = True
                
                # 显示测试结果
                print(f"  延迟: {ping_result['avg_delay']:.1f}ms, "
                      f"丢包: {ping_result['loss_rate']:.1f}%, "
                      f"抖动: {ping_result.get('jitter', 0):.1f}ms")
                print(f"  评分: 总体{scores['overall']}, "
                      f"流媒体{scores['streaming']}, "
                      f"游戏{scores['gaming']}, "
                      f"通话{scores['rtc']}")
            else:
                result['error'] = "Ping测试失败"
                
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
        批量测试多个目标
        
        Args:
            targets: 目标列表
            
        Returns:
            测试结果列表
        """
        print(f"开始测试 {len(targets)} 个目标...")
        self.results = []
        
        for i, target in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] ", end='')
            result = self.test_target(target)
            self.results.append(result)
        
        print(f"测试完成，成功: {len([r for r in self.results if r['success']])}/{len(targets)}")
        return self.results
    
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
        sys.exit(1)
    
    return targets


def main():
    """主函数"""
    print("=" * 100)
    print("高级IP/域名质量测试工具 - 专业版")
    print("基于专业网络质量评估算法（延迟、丢包率、抖动、TCP性能、综合评分）")
    print("=" * 100)
    
    # 读取目标列表
    targets = read_targets_from_file('ip.txt')
    print(f"从 ip.txt 读取到 {len(targets)} 个目标")
    
    if not targets:
        print("错误: 没有找到可测试的目标")
        sys.exit(1)
    
    # 配置参数
    config = {
        'ping_count': 10,      # 每个目标ping 10次，以获得准确的抖动计算
        'ping_timeout': 2,     # ping超时2秒
        'tcp_timeout': 5       # TCP连接超时5秒
    }
    
    # 创建测试器
    tester = AdvancedIPTester(config)
    
    # 开始测试
    start_time = time.time()
    tester.test_targets(targets)
    elapsed_time = time.time() - start_time
    
    print(f"\n总测试时间: {elapsed_time:.1f}秒")
    
    # 显示摘要
    tester.display_summary(20)
    
    # 保存结果
    tester.save_results('result_pro.txt')
    
    print(f"\n测试完成！详细结果请查看 result_pro.txt")
    print("结果包含：延迟、丢包率、抖动、TCP连接时间、综合评分、流媒体评分、游戏评分、实时通信评分")


if __name__ == '__main__':
    main()