#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量测试IP/域名质量检测程序
从ip.txt读取域名和IP列表，测试延迟和丢包率，按延迟和丢包率排序输出到result.txt
"""

import subprocess
import re
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Optional
import socket


class IPTester:
    def __init__(self, ping_count: int = 4, timeout: int = 2):
        """
        初始化测试器
        
        Args:
            ping_count: 每个目标的ping次数
            timeout: 每次ping的超时时间（秒）
        """
        self.ping_count = ping_count
        self.timeout = timeout
        self.results = []
        
    def parse_ping_output(self, output: str) -> Tuple[Optional[float], Optional[float]]:
        """
        解析ping命令输出，提取延迟和丢包率
        
        Args:
            output: ping命令的输出文本
            
        Returns:
            (平均延迟ms, 丢包率%)
        """
        # 匹配延迟模式（Windows中文版）
        delay_pattern = r'平均 = (\d+)ms'
        delay_match = re.search(delay_pattern, output)
        
        # 匹配延迟模式（Windows英文版）
        if not delay_match:
            delay_pattern = r'Average = (\d+)ms'
            delay_match = re.search(delay_pattern, output)
            
        # 匹配丢包率模式
        loss_pattern = r'\((\d+)% 丢失\)'
        loss_match = re.search(loss_pattern, output)
        
        if not loss_match:
            loss_pattern = r'\((\d+)% loss\)'
            loss_match = re.search(loss_pattern, output)
        
        avg_delay = None
        loss_rate = None
        
        if delay_match:
            avg_delay = float(delay_match.group(1))
            
        if loss_match:
            loss_rate = float(loss_match.group(1))
            
        return avg_delay, loss_rate
    
    def ping_target(self, target: str) -> Dict:
        """
        对单个目标进行ping测试
        
        Args:
            target: 域名或IP地址
            
        Returns:
            包含测试结果的字典
        """
        # 清理目标字符串（移除注释等）
        clean_target = target.strip()
        if '#' in clean_target:
            clean_target = clean_target.split('#')[0].strip()
        
        result = {
            'original': target.strip(),
            'target': clean_target,
            'delay': None,
            'loss': None,
            'success': False,
            'error': None
        }
        
        try:
            # 构建ping命令
            if sys.platform == 'win32':
                cmd = ['ping', '-n', str(self.ping_count), '-w', str(self.timeout * 1000), clean_target]
            else:
                cmd = ['ping', '-c', str(self.ping_count), '-W', str(self.timeout), clean_target]
            
            # 执行ping命令
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='gbk' if sys.platform == 'win32' else 'utf-8',
                timeout=self.timeout * self.ping_count + 5
            )
            
            if process.returncode == 0 or process.returncode == 1:  # 0=成功，1=有丢包
                avg_delay, loss_rate = self.parse_ping_output(process.stdout)
                result['delay'] = avg_delay
                result['loss'] = loss_rate if loss_rate is not None else 100.0
                result['success'] = True
            else:
                result['error'] = f"Ping命令失败，返回码: {process.returncode}"
                result['loss'] = 100.0
                
        except subprocess.TimeoutExpired:
            result['error'] = "测试超时"
            result['loss'] = 100.0
        except Exception as e:
            result['error'] = str(e)
            result['loss'] = 100.0
            
        return result
    
    def test_targets(self, targets: List[str], max_workers: int = 10) -> List[Dict]:
        """
        批量测试多个目标
        
        Args:
            targets: 目标列表
            max_workers: 最大并发线程数
            
        Returns:
            测试结果列表
        """
        print(f"开始测试 {len(targets)} 个目标...")
        self.results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_target = {executor.submit(self.ping_target, target): target for target in targets}
            
            for i, future in enumerate(as_completed(future_to_target)):
                target = future_to_target[future]
                try:
                    result = future.result()
                    self.results.append(result)
                    
                    # 显示进度
                    if result['success']:
                        print(f"[{i+1}/{len(targets)}] {result['target']}: 延迟={result['delay']}ms, 丢包={result['loss']}%")
                    else:
                        print(f"[{i+1}/{len(targets)}] {result['target']}: 失败 - {result['error']}")
                        
                except Exception as e:
                    print(f"[{i+1}/{len(targets)}] {target}: 异常 - {str(e)}")
                    self.results.append({
                        'original': target,
                        'target': target,
                        'delay': None,
                        'loss': 100.0,
                        'success': False,
                        'error': str(e)
                    })
        
        print(f"测试完成，成功: {len([r for r in self.results if r['success']])}/{len(targets)}")
        return self.results
    
    def sort_results(self) -> List[Dict]:
        """
        对结果进行排序：先按丢包率升序，再按延迟升序
        
        Returns:
            排序后的结果列表
        """
        def sort_key(result):
            # 处理None值，使其排在最后
            loss = result['loss'] if result['loss'] is not None else 101.0
            delay = result['delay'] if result['delay'] is not None else float('inf')
            return (loss, delay)
        
        sorted_results = sorted(self.results, key=sort_key)
        return sorted_results
    
    def save_results(self, output_file: str = 'result.txt'):
        """
        保存结果到文件
        
        Args:
            output_file: 输出文件名
        """
        sorted_results = self.sort_results()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # 写入表头
            f.write(f"{'目标':<30} {'延迟(ms)':<12} {'丢包率(%)':<12} {'状态':<10}\n")
            f.write("-" * 70 + "\n")
            
            # 写入结果
            for result in sorted_results:
                target = result['original']
                delay = f"{result['delay']:.1f}" if result['delay'] is not None else "超时"
                loss = f"{result['loss']:.1f}" if result['loss'] is not None else "100.0"
                status = "成功" if result['success'] else "失败"
                
                f.write(f"{target:<30} {delay:<12} {loss:<12} {status:<10}\n")
        
        print(f"结果已保存到: {output_file}")
        
    def display_top_results(self, top_n: int = 20):
        """
        显示前N个最佳结果
        
        Args:
            top_n: 显示的数量
        """
        sorted_results = self.sort_results()
        successful_results = [r for r in sorted_results if r['success']]
        
        print(f"\n{'='*70}")
        print(f"前{min(top_n, len(successful_results))}个最佳结果:")
        print(f"{'='*70}")
        print(f"{'目标':<30} {'延迟(ms)':<12} {'丢包率(%)':<12}")
        print(f"{'-'*70}")
        
        for i, result in enumerate(successful_results[:top_n]):
            target = result['original']
            delay = f"{result['delay']:.1f}"
            loss = f"{result['loss']:.1f}"
            print(f"{target:<30} {delay:<12} {loss:<12}")


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
                if line and not line.startswith('#'):  # 跳过空行和注释
                    targets.append(line)
    except UnicodeDecodeError:
        # 尝试其他编码
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
    print("=" * 70)
    print("批量IP/域名质量测试工具")
    print("=" * 70)
    
    # 读取目标列表
    targets = read_targets_from_file('ip.txt')
    print(f"从 ip.txt 读取到 {len(targets)} 个目标")
    
    if not targets:
        print("错误: 没有找到可测试的目标")
        sys.exit(1)
    
    # 创建测试器
    tester = IPTester(ping_count=4, timeout=2)
    
    # 开始测试
    start_time = time.time()
    tester.test_targets(targets, max_workers=20)
    elapsed_time = time.time() - start_time
    
    print(f"\n总测试时间: {elapsed_time:.1f}秒")
    
    # 显示最佳结果
    tester.display_top_results(20)
    
    # 保存结果
    tester.save_results('result.txt')
    
    print(f"\n测试完成！详细结果请查看 result.txt")


if __name__ == '__main__':
    main()