#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理评分计算器模块
提供针对代理服务器/VPN节点的专用评分算法
"""

from typing import Dict, Optional


class ProxyScoreCalculator:
    """代理/VPN专用评分计算器"""

    @staticmethod
    def calculate_proxy_score(test_results: Dict) -> Dict:
        """
        计算代理/VPN专用评分

        评分维度（总分100）：
        1. 可用性评分（20分）：连接成功率
        2. 速度评分（30分）：延迟 + 下载速度
        3. 稳定性评分（30分）：丢包率 + 抖动 + 连接稳定性
        4. 响应性评分（20分）：HTTP TTFB + TCP连接时间

        Args:
            test_results: 测试结果字典

        Returns:
            包含各项评分的字典
        """
        scores = {
            'overall': 0,          # 总体评分
            'availability': 0,     # 可用性
            'speed': 0,           # 速度
            'stability': 0,       # 稳定性
            'responsiveness': 0,  # 响应性
            'streaming': 0,       # 流媒体（保留）
            'gaming': 0,          # 游戏（保留）
            'rtc': 0             # 实时通信（保留）
        }

        # 提取测试数据
        ping_result = test_results.get('ping', {})
        tcp_result = test_results.get('tcp', {})
        http_result = test_results.get('http', {})
        stability_result = test_results.get('stability', {})
        download_result = test_results.get('download', {})

        # 1. 可用性评分（20分）
        availability_score = ProxyScoreCalculator._calculate_availability_score(
            ping_result, tcp_result, stability_result
        )
        scores['availability'] = availability_score

        # 2. 速度评分（30分）
        speed_score = ProxyScoreCalculator._calculate_speed_score(
            ping_result, download_result
        )
        scores['speed'] = speed_score

        # 3. 稳定性评分（30分）
        stability_score = ProxyScoreCalculator._calculate_stability_score(
            ping_result, stability_result
        )
        scores['stability'] = stability_score

        # 4. 响应性评分（20分）
        responsiveness_score = ProxyScoreCalculator._calculate_responsiveness_score(
            tcp_result, http_result
        )
        scores['responsiveness'] = responsiveness_score

        # 计算总体评分
        scores['overall'] = int(
            availability_score + speed_score + stability_score + responsiveness_score
        )

        # 保留原有的流媒体、游戏、实时通信评分（向后兼容）
        scores['streaming'] = ProxyScoreCalculator._calculate_streaming_score(ping_result)
        scores['gaming'] = ProxyScoreCalculator._calculate_gaming_score(ping_result)
        scores['rtc'] = ProxyScoreCalculator._calculate_rtc_score(ping_result)

        return scores

    @staticmethod
    def _calculate_availability_score(ping_result: Dict, tcp_result: Dict,
                                     stability_result: Dict) -> int:
        """
        计算可用性评分（20分）

        基于：
        - Ping成功率
        - TCP连接成功率
        - 连接稳定性成功率
        """
        score = 0

        # Ping成功（10分）
        if ping_result.get('success'):
            score += 10

        # TCP连接成功（5分）
        if tcp_result.get('success'):
            score += 5

        # 连接稳定性（5分）
        if stability_result:
            success_rate = stability_result.get('success_rate', 0)
            # 成功率 > 90%: 5分
            # 成功率 80-90%: 4分
            # 成功率 70-80%: 3分
            # 成功率 < 70%: 按比例
            if success_rate >= 90:
                score += 5
            elif success_rate >= 80:
                score += 4
            elif success_rate >= 70:
                score += 3
            else:
                score += int(success_rate / 20)

        return score

    @staticmethod
    def _calculate_speed_score(ping_result: Dict, download_result: Dict) -> int:
        """
        计算速度评分（30分）

        基于：
        - 延迟（15分）
        - 下载速度（15分，如果有）
        """
        score = 0

        # 延迟评分（15分）
        delay = ping_result.get('avg_delay')
        if delay is not None:
            if delay < 50:
                score += 15
            elif delay < 100:
                score += 12
            elif delay < 150:
                score += 9
            elif delay < 200:
                score += 6
            elif delay < 300:
                score += 3
            else:
                score += 1

        # 下载速度评分（15分）
        if download_result and download_result.get('success'):
            speed_mBps = download_result.get('speed_mBps', 0)
            if speed_mBps >= 5:
                score += 15
            elif speed_mBps >= 2:
                score += 10
            elif speed_mBps >= 1:
                score += 6
            elif speed_mBps >= 0.5:
                score += 3
            else:
                score += 1
        else:
            # 如果没有下载速度测试，延迟评分占满30分
            if delay is not None:
                if delay < 50:
                    score += 15
                elif delay < 100:
                    score += 12
                elif delay < 150:
                    score += 9
                elif delay < 200:
                    score += 6
                else:
                    score += 3

        return score

    @staticmethod
    def _calculate_stability_score(ping_result: Dict, stability_result: Dict) -> int:
        """
        计算稳定性评分（30分）

        基于：
        - 丢包率（10分）
        - 抖动（10分）
        - 连接稳定性（10分）
        """
        score = 0

        # 丢包率评分（10分）
        loss_rate = ping_result.get('loss_rate')
        if loss_rate is not None:
            if loss_rate == 0:
                score += 10
            elif loss_rate < 1:
                score += 8
            elif loss_rate < 3:
                score += 6
            elif loss_rate < 5:
                score += 4
            elif loss_rate < 10:
                score += 2
            else:
                score += 0

        # 抖动评分（10分）
        jitter = ping_result.get('jitter')
        if jitter is not None:
            if jitter < 5:
                score += 10
            elif jitter < 10:
                score += 8
            elif jitter < 20:
                score += 6
            elif jitter < 30:
                score += 4
            elif jitter < 50:
                score += 2
            else:
                score += 0

        # 连接稳定性评分（10分）
        if stability_result:
            stability_score = stability_result.get('stability_score', 0)
            # 直接使用稳定性评分（0-100）映射到0-10分
            score += int(stability_score / 10)

        return score

    @staticmethod
    def _calculate_responsiveness_score(tcp_result: Dict, http_result: Dict) -> int:
        """
        计算响应性评分（20分）

        基于：
        - HTTP TTFB（10分）
        - TCP连接时间（10分）
        """
        score = 0

        # HTTP TTFB评分（10分）
        if http_result and http_result.get('success'):
            ttfb = http_result.get('ttfb')
            if ttfb is not None:
                if ttfb < 100:
                    score += 10
                elif ttfb < 200:
                    score += 8
                elif ttfb < 300:
                    score += 6
                elif ttfb < 500:
                    score += 4
                elif ttfb < 1000:
                    score += 2
                else:
                    score += 0

        # TCP连接时间评分（10分）
        if tcp_result and tcp_result.get('success'):
            connect_time = tcp_result.get('connect_time')
            if connect_time is not None:
                if connect_time < 50:
                    score += 10
                elif connect_time < 100:
                    score += 8
                elif connect_time < 200:
                    score += 6
                elif connect_time < 300:
                    score += 4
                elif connect_time < 500:
                    score += 2
                else:
                    score += 0

        return score

    # 以下是保留的原有评分方法（向后兼容）

    @staticmethod
    def _calculate_streaming_score(ping_result: Dict) -> int:
        """流媒体评分（保留原有算法）"""
        score = 100

        delay = ping_result.get('avg_delay', 1000)
        loss = ping_result.get('loss_rate', 100)
        jitter = ping_result.get('jitter', 100)

        # 延迟扣分
        if delay > 300:
            score -= 50
        elif delay > 200:
            score -= 30
        elif delay > 100:
            score -= 10

        # 丢包扣分
        if loss > 5:
            score -= 40
        elif loss > 3:
            score -= 20
        elif loss > 1:
            score -= 10

        # 抖动扣分
        if jitter > 100:
            score -= 20
        elif jitter > 50:
            score -= 10

        return max(0, score)

    @staticmethod
    def _calculate_gaming_score(ping_result: Dict) -> int:
        """游戏评分（保留原有算法）"""
        score = 100

        delay = ping_result.get('avg_delay', 1000)
        loss = ping_result.get('loss_rate', 100)
        jitter = ping_result.get('jitter', 100)

        # 游戏对丢包非常敏感
        if loss > 2:
            score -= 40
        elif loss > 1:
            score -= 20
        elif loss > 0.5:
            score -= 10

        # 游戏对延迟敏感
        if delay > 150:
            score -= 30
        elif delay > 100:
            score -= 20
        elif delay > 50:
            score -= 10

        # 游戏对抖动敏感
        if jitter > 50:
            score -= 20
        elif jitter > 20:
            score -= 10

        return max(0, score)

    @staticmethod
    def _calculate_rtc_score(ping_result: Dict) -> int:
        """实时通信评分（保留原有算法）"""
        score = 100

        delay = ping_result.get('avg_delay', 1000)
        loss = ping_result.get('loss_rate', 100)
        jitter = ping_result.get('jitter', 100)

        # RTC对丢包非常敏感
        if loss > 1:
            score -= 30
        elif loss > 0.5:
            score -= 20
        elif loss > 0.1:
            score -= 10

        # RTC对抖动非常敏感
        if jitter > 30:
            score -= 30
        elif jitter > 20:
            score -= 20
        elif jitter > 10:
            score -= 10

        # RTC对延迟有一定容忍度
        if delay > 200:
            score -= 20
        elif delay > 150:
            score -= 15
        elif delay > 100:
            score -= 10

        return max(0, score)


if __name__ == '__main__':
    # 测试代理评分计算器
    print("=" * 60)
    print("代理评分计算器测试")
    print("=" * 60)

    # 测试数据1：优质节点
    print("\n1. 优质节点测试:")
    test_results_good = {
        'ping': {
            'success': True,
            'avg_delay': 45.0,
            'loss_rate': 0.0,
            'jitter': 3.5
        },
        'tcp': {
            'success': True,
            'connect_time': 60.0
        },
        'http': {
            'success': True,
            'ttfb': 120.0,
            'total_time': 250.0
        },
        'stability': {
            'success_rate': 100.0,
            'stability_score': 95
        },
        'download': {
            'success': True,
            'speed_mBps': 8.5
        }
    }

    scores_good = ProxyScoreCalculator.calculate_proxy_score(test_results_good)
    print(f"  总体评分: {scores_good['overall']}/100")
    print(f"  可用性: {scores_good['availability']}/20")
    print(f"  速度: {scores_good['speed']}/30")
    print(f"  稳定性: {scores_good['stability']}/30")
    print(f"  响应性: {scores_good['responsiveness']}/20")
    print(f"  流媒体: {scores_good['streaming']}/100")
    print(f"  游戏: {scores_good['gaming']}/100")
    print(f"  实时通信: {scores_good['rtc']}/100")

    # 测试数据2：一般节点
    print("\n2. 一般节点测试:")
    test_results_medium = {
        'ping': {
            'success': True,
            'avg_delay': 120.0,
            'loss_rate': 2.0,
            'jitter': 15.0
        },
        'tcp': {
            'success': True,
            'connect_time': 180.0
        },
        'http': {
            'success': True,
            'ttfb': 280.0,
            'total_time': 500.0
        },
        'stability': {
            'success_rate': 85.0,
            'stability_score': 70
        }
    }

    scores_medium = ProxyScoreCalculator.calculate_proxy_score(test_results_medium)
    print(f"  总体评分: {scores_medium['overall']}/100")
    print(f"  可用性: {scores_medium['availability']}/20")
    print(f"  速度: {scores_medium['speed']}/30")
    print(f"  稳定性: {scores_medium['stability']}/30")
    print(f"  响应性: {scores_medium['responsiveness']}/20")

    # 测试数据3：较差节点
    print("\n3. 较差节点测试:")
    test_results_poor = {
        'ping': {
            'success': True,
            'avg_delay': 280.0,
            'loss_rate': 8.0,
            'jitter': 45.0
        },
        'tcp': {
            'success': True,
            'connect_time': 450.0
        },
        'http': {
            'success': True,
            'ttfb': 800.0,
            'total_time': 1200.0
        },
        'stability': {
            'success_rate': 65.0,
            'stability_score': 40
        }
    }

    scores_poor = ProxyScoreCalculator.calculate_proxy_score(test_results_poor)
    print(f"  总体评分: {scores_poor['overall']}/100")
    print(f"  可用性: {scores_poor['availability']}/20")
    print(f"  速度: {scores_poor['speed']}/30")
    print(f"  稳定性: {scores_poor['stability']}/30")
    print(f"  响应性: {scores_poor['responsiveness']}/20")

    print("\n代理评分计算器测试完成！")
