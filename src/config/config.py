#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
定义所有测试配置参数和测试模式预设
"""

import json
import os
from typing import Dict


# 默认配置
DEFAULT_CONFIG = {
    # 原有配置
    'ping_count': 10,              # Ping次数
    'ping_timeout': 2,             # Ping超时时间（秒）
    'tcp_timeout': 5,              # TCP连接超时时间（秒）
    'max_workers': 10,             # 并发线程数

    # 新增配置 - 速度优化
    'enable_quick_check': True,    # 启用快速检测
    'quick_check_workers': 50,     # 快速检测并发数
    'quick_ping_count': 1,         # 快速检测ping次数
    'quick_ping_timeout': 1,       # 快速检测ping超时（秒）
    'quick_tcp_timeout': 2,        # 快速检测TCP超时（秒）

    # 新增配置 - 准确性提升
    'enable_multi_round': True,    # 启用多轮测试
    'test_rounds': 3,              # 测试轮数
    'outlier_filter_method': 'iqr',  # 异常值过滤方法：'iqr', 'zscore', 'mad'
    'confidence_level': 0.95,      # 置信水平
    'enable_smart_retry': True,    # 启用智能重试
    'max_retries': 3,              # 最大重试次数

    # 新增配置 - 测试指标
    'enable_http_test': True,      # 启用HTTP性能测试
    'http_test_url': 'https://cp.cloudflare.com/generate_204',  # HTTP测试URL
    'http_timeout': 10,            # HTTP测试超时（秒）
    'enable_download_test': False, # 启用下载速度测试
    'download_test_size_kb': 100,  # 下载测试文件大小（KB）
    'download_timeout': 10,        # 下载测试超时（秒）
    'enable_stability_test': True, # 启用连接稳定性测试
    'stability_attempts': 10,      # 稳定性测试连接次数

    # 新增配置 - 评分模式
    'scoring_mode': 'proxy',       # 评分模式：'proxy', 'vpn', 'general'
    'test_mode': 'balanced',       # 测试模式：'fast', 'balanced', 'thorough'

    # URL获取配置（新增）
    'enable_url_fetch': False,     # 是否启用URL获取（默认关闭，保持向后兼容）
    'url_sources': [],             # URL列表
    'url_timeout': 10,             # URL获取超时时间（秒）
    'url_retry_times': 2,          # URL获取失败重试次数
    'url_retry_delay': 1,          # 重试间隔（秒）
    'fallback_to_file': True,      # URL全部失败时是否回退到文件读取
    'merge_file_and_url': False,   # 是否合并文件和URL的结果

    # 自定义文件配置（新增）
    'enable_custom_file': False,          # 是否启用自定义文件（默认关闭）
    'custom_file_path': 'data/input/custom.txt',  # 自定义文件路径
    'merge_custom_with_url': True,        # 是否合并自定义文件和URL结果
    'custom_file_priority': 'before_url', # 自定义文件优先级：'before_url' 或 'after_url'
}


# 测试模式预设
TEST_MODES = {
    'fast': {
        'enable_quick_check': True,
        'enable_multi_round': False,
        'test_rounds': 1,
        'enable_http_test': True,
        'enable_download_test': False,
        'enable_stability_test': False,
        'ping_count': 5,
        'max_workers': 20,
        'quick_check_workers': 50,
    },
    'balanced': {
        'enable_quick_check': True,
        'enable_multi_round': True,
        'test_rounds': 2,
        'enable_http_test': True,
        'enable_download_test': False,
        'enable_stability_test': True,
        'ping_count': 10,
        'max_workers': 10,
        'quick_check_workers': 50,
        'stability_attempts': 10,
    },
    'thorough': {
        'enable_quick_check': True,
        'enable_multi_round': True,
        'test_rounds': 3,
        'enable_http_test': True,
        'enable_download_test': True,
        'enable_stability_test': True,
        'ping_count': 15,
        'max_workers': 5,
        'quick_check_workers': 30,
        'stability_attempts': 15,
    }
}


# HTTP测试URL备选列表（按优先级）
HTTP_TEST_URLS = [
    'https://cp.cloudflare.com/generate_204',  # Cloudflare（优先）
    'http://www.gstatic.com/generate_204',     # Google
    'http://captive.apple.com/hotspot-detect.html',  # Apple
    'http://www.msftconnecttest.com/connecttest.txt',  # Microsoft
]


def load_config_from_file(config_file: str = 'config.json') -> Dict:
    """
    从JSON配置文件加载配置

    Args:
        config_file: 配置文件路径（相对于项目根目录）

    Returns:
        配置字典，如果文件不存在则返回空字典
    """
    # 获取项目根目录（config.py所在目录的上两级）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_path = os.path.join(project_root, config_file)

    if not os.path.exists(config_path):
        print(f"提示: 配置文件 {config_file} 不存在，使用默认配置")
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            file_config = json.load(f)

        # 展平配置结构
        flat_config = {}

        # 合并url_config
        if 'url_config' in file_config:
            flat_config.update(file_config['url_config'])

        # 合并custom_file_config
        if 'custom_file_config' in file_config:
            flat_config.update(file_config['custom_file_config'])

        # 合并test_config
        if 'test_config' in file_config:
            flat_config.update(file_config['test_config'])

        # 合并quick_check_config
        if 'quick_check_config' in file_config:
            flat_config.update(file_config['quick_check_config'])

        # 合并advanced_config
        if 'advanced_config' in file_config:
            flat_config.update(file_config['advanced_config'])

        print(f"[OK] 成功加载配置文件: {config_file}")
        return flat_config

    except json.JSONDecodeError as e:
        print(f"[ERROR] 配置文件格式错误: {e}")
        return {}
    except Exception as e:
        print(f"[ERROR] 读取配置文件失败: {e}")
        return {}


def load_config(custom_config: Dict = None, test_mode: str = None, config_file: str = 'config.json') -> Dict:
    """
    加载配置（优先级：自定义配置 > 配置文件 > 测试模式 > 默认配置）

    Args:
        custom_config: 自定义配置字典（优先级最高）
        test_mode: 测试模式（'fast', 'balanced', 'thorough'）
        config_file: 配置文件路径（相对于项目根目录）

    Returns:
        合并后的配置字典
    """
    # 1. 从默认配置开始
    config = DEFAULT_CONFIG.copy()

    # 2. 如果指定了测试模式，应用模式预设
    if test_mode and test_mode in TEST_MODES:
        mode_config = TEST_MODES[test_mode]
        config.update(mode_config)

    # 3. 从配置文件加载（优先级高于测试模式）
    file_config = load_config_from_file(config_file)
    if file_config:
        config.update(file_config)

    # 4. 应用自定义配置（优先级最高）
    if custom_config:
        config.update(custom_config)

    return config


def validate_config(config: Dict) -> bool:
    """
    验证配置参数的有效性

    Args:
        config: 配置字典

    Returns:
        配置是否有效
    """
    # 验证数值范围
    if config.get('ping_count', 0) < 1:
        print("警告: ping_count 必须大于0，已重置为默认值10")
        config['ping_count'] = 10

    if config.get('test_rounds', 0) < 1:
        print("警告: test_rounds 必须大于0，已重置为默认值3")
        config['test_rounds'] = 3

    if config.get('max_workers', 0) < 1:
        print("警告: max_workers 必须大于0，已重置为默认值10")
        config['max_workers'] = 10

    # 验证评分模式
    valid_scoring_modes = ['proxy', 'vpn', 'general']
    if config.get('scoring_mode') not in valid_scoring_modes:
        print(f"警告: scoring_mode 必须是 {valid_scoring_modes} 之一，已重置为'proxy'")
        config['scoring_mode'] = 'proxy'

    # 验证异常值过滤方法
    valid_filter_methods = ['iqr', 'zscore', 'mad']
    if config.get('outlier_filter_method') not in valid_filter_methods:
        print(f"警告: outlier_filter_method 必须是 {valid_filter_methods} 之一，已重置为'iqr'")
        config['outlier_filter_method'] = 'iqr'

    return True


def get_test_mode_description(mode: str) -> str:
    """
    获取测试模式的描述

    Args:
        mode: 测试模式名称

    Returns:
        模式描述
    """
    descriptions = {
        'fast': '快速模式：单轮测试，快速筛选，适合快速评估大量节点',
        'balanced': '平衡模式：两轮测试，包含HTTP和稳定性测试，推荐使用',
        'thorough': '彻底模式：三轮测试，包含所有测试项，最准确但最慢'
    }
    return descriptions.get(mode, '未知模式')


if __name__ == '__main__':
    # 测试配置加载
    print("=" * 60)
    print("配置管理模块测试")
    print("=" * 60)

    # 测试默认配置
    print("\n1. 默认配置:")
    default_config = load_config()
    for key, value in default_config.items():
        print(f"  {key}: {value}")

    # 测试快速模式
    print("\n2. 快速模式配置:")
    fast_config = load_config(test_mode='fast')
    print(f"  测试模式: {fast_config['test_mode']}")
    print(f"  描述: {get_test_mode_description('fast')}")
    print(f"  多轮测试: {fast_config['enable_multi_round']}")
    print(f"  测试轮数: {fast_config['test_rounds']}")
    print(f"  并发数: {fast_config['max_workers']}")

    # 测试平衡模式
    print("\n3. 平衡模式配置:")
    balanced_config = load_config(test_mode='balanced')
    print(f"  测试模式: {balanced_config['test_mode']}")
    print(f"  描述: {get_test_mode_description('balanced')}")
    print(f"  多轮测试: {balanced_config['enable_multi_round']}")
    print(f"  测试轮数: {balanced_config['test_rounds']}")
    print(f"  并发数: {balanced_config['max_workers']}")

    # 测试自定义配置
    print("\n4. 自定义配置:")
    custom_config = load_config(
        custom_config={'ping_count': 20, 'max_workers': 15},
        test_mode='balanced'
    )
    print(f"  Ping次数: {custom_config['ping_count']}")
    print(f"  并发数: {custom_config['max_workers']}")

    # 测试配置验证
    print("\n5. 配置验证测试:")
    invalid_config = {
        'ping_count': -1,
        'scoring_mode': 'invalid',
        'outlier_filter_method': 'unknown'
    }
    validate_config(invalid_config)

    print("\n配置管理模块测试完成！")
