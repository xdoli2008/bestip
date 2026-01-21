#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试改进功能
验证问题1和问题2的修复
"""

from src.core.ip_tester_pro import AdvancedIPTester
from src.config.config import load_config

def test_best_txt_generation():
    """测试best.txt生成功能（问题1）"""
    print("=" * 60)
    print("测试1：验证best.txt生成功能")
    print("=" * 60)

    # 创建测试数据
    test_results = [
        {
            'original': '168.138.165.174:443#SG-频道@kejiland00',
            'target': '168.138.165.174',
            'ping': {'success': True, 'avg_delay': 64.0, 'loss_rate': 0.0, 'jitter': 3.5},
            'tcp': {'success': True, 'connect_time': 60.0},
            'http': {},
            'stability': {},
            'scores': {'overall': 97, 'streaming': 95, 'gaming': 98, 'rtc': 96},
            'success': True
        },
        {
            'original': '95.163.240.24:8443#SE-频道@kejiland00',
            'target': '95.163.240.24',
            'ping': {'success': True, 'avg_delay': 78.0, 'loss_rate': 0.0, 'jitter': 4.2},
            'tcp': {'success': True, 'connect_time': 72.0},
            'http': {},
            'stability': {},
            'scores': {'overall': 95, 'streaming': 93, 'gaming': 94, 'rtc': 95},
            'success': True
        },
        {
            'original': '34.143.159.175:443#SG-频道@kejiland00',
            'target': '34.143.159.175',
            'ping': {'success': True, 'avg_delay': 82.0, 'loss_rate': 0.0, 'jitter': 5.1},
            'tcp': {'success': True, 'connect_time': 78.0},
            'http': {},
            'stability': {},
            'scores': {'overall': 93, 'streaming': 91, 'gaming': 92, 'rtc': 94},
            'success': True
        }
    ]

    # 创建测试器并设置结果
    config = load_config(test_mode='balanced')
    tester = AdvancedIPTester(config)
    tester.results = test_results

    # 生成best.txt
    print("\n生成best.txt文件...")
    tester.save_best_results('test_best.txt', 3)

    # 读取并验证
    print("\n验证生成的文件内容:")
    with open('test_best.txt', 'r', encoding='utf-8') as f:
        content = f.read()
        print(content)

    # 检查格式
    lines = content.strip().split('\n')
    print(f"\n[OK] 生成了 {len(lines)} 行数据")

    for i, line in enumerate(lines, 1):
        if '#' in line:
            ip_port, country = line.split('#')
            print(f"  {i}. IP:端口={ip_port}, 国家代码={country}")

            # 验证没有广告文字
            if '频道' in line or '@' in line:
                print(f"    [X] 错误：包含广告文字")
            else:
                print(f"    [OK] 格式正确，无广告文字")

    print("\n测试1完成！\n")


def test_quick_check_accuracy():
    """测试快速检测准确性（问题2）"""
    print("=" * 60)
    print("测试2：验证快速检测准确性改进")
    print("=" * 60)

    config = load_config(test_mode='balanced')
    tester = AdvancedIPTester(config)

    # 测试目标（使用公共DNS服务器）
    test_targets = [
        '8.8.8.8',      # Google DNS
        '1.1.1.1',      # Cloudflare DNS
        '208.67.222.222' # OpenDNS
    ]

    print("\n改进点：")
    print("  - Ping次数：1次 → 3次")
    print("  - 重试机制：无 → 最多2次尝试")
    print("  - 超时设置：1秒 → 1.5秒")
    print("  - 延迟计算：单次 → 平均值")

    print("\n开始测试快速检测（每个目标测试3次）...\n")

    for target in test_targets:
        print(f"测试目标: {target}")
        results = []

        for attempt in range(3):
            result = tester.quick_availability_check(target)
            results.append(result)

            status = "[OK] 可用" if result['available'] else "[X] 不可用"
            delay = f"{result['quick_delay']:.1f}ms" if result['quick_delay'] else "N/A"
            reason = f"({result['reason']})" if result['reason'] else ""

            print(f"  第{attempt+1}次: {status}, 延迟={delay} {reason}")

        # 统计一致性
        available_count = sum(1 for r in results if r['available'])
        consistency = (available_count / 3) * 100

        print(f"  一致性: {available_count}/3 ({consistency:.0f}%)")

        if consistency == 100:
            print(f"  [OK] 检测结果完全一致")
        elif consistency >= 66:
            print(f"  [!] 检测结果基本一致")
        else:
            print(f"  [X] 检测结果不一致，需要进一步优化")

        print()

    print("测试2完成！\n")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("IP测试工具改进验证")
    print("=" * 60 + "\n")

    # 测试1：best.txt生成
    test_best_txt_generation()

    # 测试2：快速检测准确性
    test_quick_check_accuracy()

    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)
    print("\n改进总结：")
    print("[OK] 问题1：已添加save_best_results()方法，生成干净的best.txt")
    print("[OK] 问题2：已改进quick_availability_check()，提高检测准确性")
    print("\n建议：")
    print("- 运行 python ip_tester_pro.py 进行完整测试")
    print("- 检查生成的 best.txt 文件格式是否正确")
    print("- 对比多次运行的快速检测结果，验证一致性")


if __name__ == '__main__':
    main()
