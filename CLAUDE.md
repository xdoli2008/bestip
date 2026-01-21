# CLAUDE.md

Claude Code开发指南 - 仅包含必需的上下文信息

## 项目概述

IP/域名质量测试工具，专为代理/VPN节点优化。两阶段测试策略（快速筛选 + 深度测试），支持延迟、丢包、抖动、TCP、HTTP、稳定性等多维度评估。

## 快速运行

```bash
# 推荐方式
python main.py

# 或使用脚本
scripts/run_pro.bat
```

## 项目结构

```
bestip/
├── main.py                    # 主入口
├── src/
│   ├── core/                  # 核心测试逻辑
│   │   ├── ip_tester.py       # 基础版
│   │   └── ip_tester_pro.py   # 专业版（主要）
│   ├── analyzers/             # 分析模块
│   │   ├── statistical_analyzer.py
│   │   └── proxy_score_calculator.py
│   └── config/
│       └── config.py          # 配置管理
├── data/
│   ├── input/testip.txt       # 输入：测试目标列表
│   └── output/                # 输出：测试结果
├── tests/                     # 测试代码
└── docs/                      # 详细文档
```

## 核心架构

### 主要类
- **AdvancedIPTester** (`src/core/ip_tester_pro.py`) - 专业版测试器
  - 两阶段测试：快速筛选（50并发）→ 深度测试（10并发）
  - 测试方法：ping、TCP、HTTP、稳定性
  - 评分算法：代理专用（可用性20% + 速度30% + 稳定性30% + 响应性20%）

### 配置
```python
from src.config.config import load_config

# 三种模式：fast/balanced/thorough
config = load_config(test_mode='balanced')
```

## 关键文件路径

**输入：** `data/input/testip.txt`
**输出：** `data/output/` 目录
- `result_pro.md` - 详细报告
- `best.txt` - 干净格式（IP:端口#国家）
- `ip.txt` - 详细信息

## 开发原则

1. **跨平台兼容**：Windows用gbk编码，Linux用utf-8
2. **线程安全**：使用`threading.Lock`保护共享资源
3. **错误处理**：网络操作必须有完善的异常处理
4. **路径使用**：所有路径相对于项目根目录

## 导入路径

```python
# 正确的导入方式
from src.core.ip_tester_pro import AdvancedIPTester
from src.config.config import load_config
from src.analyzers.statistical_analyzer import StatisticalAnalyzer
from src.analyzers.proxy_score_calculator import ProxyScoreCalculator
```

## 详细文档

更多信息请查看 `docs/` 目录：
- **README.md** - 完整使用说明
- **TECHNICAL.md** - 技术细节和算法说明
- **RESTRUCTURE_REPORT.md** - 项目重构报告
- **PROJECT_RESTRUCTURE.md** - 重构方案详情

---

**注意**：本文件仅包含开发必需信息。详细说明、配置参数、版本历史等请查看docs目录。
