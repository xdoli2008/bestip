#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计分析模块
提供异常值过滤、置信区间计算和综合统计分析功能
"""

import statistics
from typing import List, Tuple, Dict, Optional
import math


class StatisticalAnalyzer:
    """统计分析器类"""

    @staticmethod
    def filter_outliers(data: List[float], method: str = 'iqr') -> List[float]:
        """
        过滤异常值

        Args:
            data: 数据列表
            method: 过滤方法 ('iqr', 'zscore', 'mad')

        Returns:
            过滤后的数据列表
        """
        if not data or len(data) < 3:
            return data

        if method == 'iqr':
            return StatisticalAnalyzer._filter_outliers_iqr(data)
        elif method == 'zscore':
            return StatisticalAnalyzer._filter_outliers_zscore(data)
        elif method == 'mad':
            return StatisticalAnalyzer._filter_outliers_mad(data)
        else:
            return data

    @staticmethod
    def _filter_outliers_iqr(data: List[float]) -> List[float]:
        """
        使用IQR方法过滤异常值

        IQR = Q3 - Q1
        过滤范围：[Q1 - 1.5*IQR, Q3 + 1.5*IQR]
        """
        sorted_data = sorted(data)
        n = len(sorted_data)

        # 计算四分位数
        q1_index = n // 4
        q3_index = 3 * n // 4
        q1 = sorted_data[q1_index]
        q3 = sorted_data[q3_index]

        # 计算IQR
        iqr = q3 - q1

        # 计算边界
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # 过滤异常值
        filtered = [x for x in data if lower_bound <= x <= upper_bound]

        return filtered if filtered else data

    @staticmethod
    def _filter_outliers_zscore(data: List[float], threshold: float = 2.5) -> List[float]:
        """
        使用Z-Score方法过滤异常值

        过滤 |z-score| > threshold 的值
        """
        if len(data) < 2:
            return data

        mean = statistics.mean(data)
        stdev = statistics.stdev(data)

        if stdev == 0:
            return data

        # 计算z-score并过滤
        filtered = [x for x in data if abs((x - mean) / stdev) <= threshold]

        return filtered if filtered else data

    @staticmethod
    def _filter_outliers_mad(data: List[float], threshold: float = 3.5) -> List[float]:
        """
        使用MAD（中位数绝对偏差）方法过滤异常值

        MAD = median(|x - median(x)|)
        更稳健的异常值检测方法
        """
        if len(data) < 3:
            return data

        median = statistics.median(data)
        deviations = [abs(x - median) for x in data]
        mad = statistics.median(deviations)

        if mad == 0:
            return data

        # 计算修正的z-score
        modified_z_scores = [0.6745 * (x - median) / mad for x in data]

        # 过滤异常值
        filtered = [data[i] for i in range(len(data)) if abs(modified_z_scores[i]) <= threshold]

        return filtered if filtered else data

    @staticmethod
    def calculate_confidence_interval(data: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """
        计算置信区间

        Args:
            data: 数据列表
            confidence: 置信水平（默认0.95）

        Returns:
            (lower_bound, upper_bound) 置信区间
        """
        if not data or len(data) < 2:
            return (0.0, 0.0)

        n = len(data)
        mean = statistics.mean(data)
        stdev = statistics.stdev(data)

        # 计算标准误差
        se = stdev / math.sqrt(n)

        # 使用t分布的临界值（简化版，使用近似值）
        # 对于大样本（n>30），t分布接近正态分布
        if n > 30:
            # 95%置信区间的z值约为1.96
            # 99%置信区间的z值约为2.576
            if confidence >= 0.99:
                t_value = 2.576
            elif confidence >= 0.95:
                t_value = 1.96
            else:
                t_value = 1.645  # 90%
        else:
            # 小样本使用简化的t值表
            t_values = {
                2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776,
                6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262
            }
            t_value = t_values.get(n, 2.0)

        # 计算置信区间
        margin_of_error = t_value * se
        lower_bound = mean - margin_of_error
        upper_bound = mean + margin_of_error

        return (lower_bound, upper_bound)

    @staticmethod
    def calculate_statistics(data: List[float]) -> Dict:
        """
        计算综合统计信息

        Args:
            data: 数据列表

        Returns:
            包含各种统计指标的字典
        """
        if not data:
            return {
                'count': 0,
                'mean': None,
                'median': None,
                'stdev': None,
                'variance': None,
                'min': None,
                'max': None,
                'range': None,
                'cv': None,  # 变异系数
                'q1': None,
                'q3': None,
                'iqr': None,
            }

        sorted_data = sorted(data)
        n = len(sorted_data)

        # 基本统计量
        mean = statistics.mean(data)
        median = statistics.median(data)
        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val

        # 标准差和方差
        stdev = statistics.stdev(data) if n > 1 else 0.0
        variance = statistics.variance(data) if n > 1 else 0.0

        # 变异系数（CV）：标准差/平均值，用于评估稳定性
        cv = (stdev / mean * 100) if mean != 0 else 0.0

        # 四分位数
        q1_index = n // 4
        q3_index = 3 * n // 4
        q1 = sorted_data[q1_index] if n > 1 else min_val
        q3 = sorted_data[q3_index] if n > 1 else max_val
        iqr = q3 - q1

        return {
            'count': n,
            'mean': mean,
            'median': median,
            'stdev': stdev,
            'variance': variance,
            'min': min_val,
            'max': max_val,
            'range': range_val,
            'cv': cv,  # 变异系数（百分比）
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
        }

    @staticmethod
    def aggregate_multi_round_data(rounds_data: List[Dict], metric: str, filter_method: str = 'iqr') -> Dict:
        """
        聚合多轮测试数据

        Args:
            rounds_data: 多轮测试数据列表
            metric: 要聚合的指标名称（如 'avg_delay', 'loss_rate'）
            filter_method: 异常值过滤方法

        Returns:
            聚合后的统计结果
        """
        # 提取指标值
        values = []
        for round_data in rounds_data:
            if metric in round_data and round_data[metric] is not None:
                values.append(round_data[metric])

        if not values:
            return {
                'value': None,
                'confidence_interval': (None, None),
                'statistics': {},
                'filtered_count': 0,
                'original_count': 0,
            }

        original_count = len(values)

        # 过滤异常值
        filtered_values = StatisticalAnalyzer.filter_outliers(values, method=filter_method)
        filtered_count = len(filtered_values)

        # 计算统计信息
        stats = StatisticalAnalyzer.calculate_statistics(filtered_values)

        # 计算置信区间
        ci = StatisticalAnalyzer.calculate_confidence_interval(filtered_values)

        return {
            'value': stats['mean'],  # 使用平均值作为最终值
            'confidence_interval': ci,
            'statistics': stats,
            'filtered_count': filtered_count,
            'original_count': original_count,
        }

    @staticmethod
    def calculate_stability_score(cv: float) -> int:
        """
        根据变异系数计算稳定性评分

        Args:
            cv: 变异系数（百分比）

        Returns:
            稳定性评分（0-100）
        """
        # CV越小，稳定性越高
        # CV < 5%: 非常稳定（90-100分）
        # CV 5-10%: 稳定（80-90分）
        # CV 10-20%: 一般（60-80分）
        # CV 20-30%: 不稳定（40-60分）
        # CV > 30%: 非常不稳定（0-40分）

        if cv < 5:
            score = 100 - cv
        elif cv < 10:
            score = 90 - (cv - 5) * 2
        elif cv < 20:
            score = 80 - (cv - 10) * 2
        elif cv < 30:
            score = 60 - (cv - 20) * 2
        else:
            score = max(0, 40 - (cv - 30))

        return int(max(0, min(100, score)))


if __name__ == '__main__':
    # 测试统计分析模块
    print("=" * 60)
    print("统计分析模块测试")
    print("=" * 60)

    # 测试数据（包含异常值）
    test_data = [100, 102, 98, 105, 103, 99, 101, 104, 200, 97, 102, 100]

    print("\n1. 原始数据:")
    print(f"  数据: {test_data}")

    # 测试IQR方法
    print("\n2. IQR方法过滤异常值:")
    filtered_iqr = StatisticalAnalyzer.filter_outliers(test_data, method='iqr')
    print(f"  过滤后: {filtered_iqr}")
    print(f"  移除了: {set(test_data) - set(filtered_iqr)}")

    # 测试Z-Score方法
    print("\n3. Z-Score方法过滤异常值:")
    filtered_zscore = StatisticalAnalyzer.filter_outliers(test_data, method='zscore')
    print(f"  过滤后: {filtered_zscore}")

    # 测试MAD方法
    print("\n4. MAD方法过滤异常值:")
    filtered_mad = StatisticalAnalyzer.filter_outliers(test_data, method='mad')
    print(f"  过滤后: {filtered_mad}")

    # 测试置信区间
    print("\n5. 置信区间计算:")
    ci = StatisticalAnalyzer.calculate_confidence_interval(filtered_iqr)
    print(f"  95%置信区间: [{ci[0]:.2f}, {ci[1]:.2f}]")

    # 测试综合统计
    print("\n6. 综合统计信息:")
    stats = StatisticalAnalyzer.calculate_statistics(filtered_iqr)
    print(f"  样本数: {stats['count']}")
    print(f"  平均值: {stats['mean']:.2f}")
    print(f"  中位数: {stats['median']:.2f}")
    print(f"  标准差: {stats['stdev']:.2f}")
    print(f"  变异系数: {stats['cv']:.2f}%")
    print(f"  最小值: {stats['min']:.2f}")
    print(f"  最大值: {stats['max']:.2f}")
    print(f"  四分位距: {stats['iqr']:.2f}")

    # 测试稳定性评分
    print("\n7. 稳定性评分:")
    stability_score = StatisticalAnalyzer.calculate_stability_score(stats['cv'])
    print(f"  变异系数: {stats['cv']:.2f}%")
    print(f"  稳定性评分: {stability_score}/100")

    # 测试多轮数据聚合
    print("\n8. 多轮数据聚合测试:")
    rounds_data = [
        {'avg_delay': 100, 'loss_rate': 0.5},
        {'avg_delay': 102, 'loss_rate': 0.3},
        {'avg_delay': 98, 'loss_rate': 0.4},
        {'avg_delay': 200, 'loss_rate': 5.0},  # 异常值
        {'avg_delay': 101, 'loss_rate': 0.6},
    ]
    aggregated = StatisticalAnalyzer.aggregate_multi_round_data(rounds_data, 'avg_delay')
    print(f"  原始轮数: {aggregated['original_count']}")
    print(f"  过滤后轮数: {aggregated['filtered_count']}")
    print(f"  聚合延迟: {aggregated['value']:.2f}ms")
    print(f"  置信区间: [{aggregated['confidence_interval'][0]:.2f}, {aggregated['confidence_interval'][1]:.2f}]")
    print(f"  变异系数: {aggregated['statistics']['cv']:.2f}%")

    print("\n统计分析模块测试完成！")
