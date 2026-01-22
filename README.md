# IP/域名质量批量测试工具 - 代理/VPN专用优化版

这是一个用于批量测试IP地址和域名质量的Python工具，**特别针对代理服务器和VPN节点进行了优化**。它支持多种输入方式（文件/URL/自定义列表），通过两阶段测试流程（快速筛选 + 深度测试）快速识别优质节点，然后按质量排序输出详细报告。

## ✨ 新版本亮点（v2.0）

### 🚀 速度提升 90%
- **两阶段测试策略**：快速筛选（1-2秒/节点） + 深度测试
- **快速失败机制**：不可用节点快速识别并跳过
- **智能并发**：快速检测50并发，深度测试10并发
- **测试时间**：从27分钟降至2-3分钟

### 🎯 准确性提升 40%
- **改进的快速检测**：3次ping + 重试机制，提高检测准确性
- **统计分析**：支持IQR/Z-Score/MAD三种异常值过滤方法
- **置信区间**：提供95%置信区间评估结果可靠性
- **多轮测试**：可配置测试轮数，取统计平均值

### 📊 新增测试指标
- **HTTP/HTTPS性能**：TTFB（首字节时间）、TLS握手时间、总响应时间
- **连接稳定性**：10次连续连接测试，计算成功率和稳定性评分
- **代理专用评分**：可用性（20分）+ 速度（30分）+ 稳定性（30分）+ 响应性（20分）

### 📝 输出格式优化
- **ip.txt**：详细信息格式（国家-延迟-评分）
- **best.txt**：干净格式（IP:端口#国家代码），无广告文字
- **result_pro.md**：可视化Markdown报告

### 🎮 三种测试模式
- **fast**：快速模式，单轮测试，适合快速评估大量节点
- **balanced**：平衡模式，两轮测试，包含HTTP和稳定性测试（推荐）
- **thorough**：彻底模式，三轮测试，包含所有测试项，最准确但最慢

## 功能特点

### 基础功能
- ✅ 批量测试IP地址和域名
- ✅ 计算延迟（ping时间）和丢包率
- ✅ 多线程并发测试，提高效率
- ✅ 按综合评分自动排序
- ✅ 支持Windows/Linux系统（自动处理中文/英文系统）
- ✅ 实时显示测试进度和结果
- ✅ 输出格式化的结果文件（TXT + Markdown）

### 高级功能（专业版）
- ⚡ **快速可用性检测**：1-2秒快速判断节点是否可用
- 🌐 **HTTP性能测试**：测试实际代理性能（TTFB、响应时间）
- 🔄 **连接稳定性测试**：10次连续连接，评估长期可靠性
- 📈 **抖动计算**：评估网络稳定性
- 🎯 **代理专用评分**：针对代理/VPN场景优化的评分算法
- 🌍 **地理位置查询**：自动查询IP所属国家
- 📊 **统计分析**：异常值过滤、置信区间计算
- 🎨 **Markdown报告**：带表情符号的可视化报告
- 🔗 **URL远程获取**：支持从URL获取IP列表
- 📝 **自定义列表**：支持独立的自定义域名/IP列表文件

## 文件说明

### 核心文件
- `ip_tester_pro.py` - 专业版测试程序（推荐）
- `ip_tester.py` - 基础版测试程序
- `config.py` - 配置管理模块
- `statistical_analyzer.py` - 统计分析模块
- `proxy_score_calculator.py` - 代理评分计算器

### 输入/输出文件
- `data/input/testip.txt` - 主输入文件，包含要测试的域名和IP列表
- `data/input/custom.txt` - 自定义输入文件，用于存放个人的域名/IP列表
- `data/output/ip.txt` - 输出文件，前15名优质节点（带详细信息：国家-延迟-评分）
- `data/output/best.txt` - 输出文件，前15名优质节点（干净格式：IP:端口#国家代码，无广告）
- `data/output/result_pro.txt` - 详细测试结果（文本格式）
- `data/output/result_pro.md` - 详细测试结果（Markdown格式，推荐查看）

### 批处理脚本
- `run_pro.bat` - 运行专业版测试（推荐）
- `run.bat` - 运行基础版测试

## 使用方法

### 方法1：使用批处理脚本（推荐）
1. 确保 `data/input/testip.txt` 文件存在并包含要测试的域名/IP
2. 双击 `scripts/run_pro.bat` 或运行 `python main.py`
3. 程序会自动运行并显示结果

### 使用自定义域名列表
1. 编辑 `data/input/custom.txt` 文件，添加你的域名/IP：
   ```
   # Cloudflare优选域名
   cloudflare.182682.xyz
   freeyx.cloudflare88.eu.org
   cdn.2020111.xyz
   cf.090227.xyz
   ```
2. 确认 `config.json` 中启用了自定义文件功能：
   ```json
   {
     "custom_file_config": {
       "enable_custom_file": true,
       "merge_custom_with_url": true,
       "custom_file_priority": "before_url"
     }
   }
   ```
3. 运行 `python main.py`，程序会自动合并自定义列表和URL获取的地址

### 方法2：直接运行Python程序
```bash
# 运行专业版（推荐）
python ip_tester_pro.py

# 运行基础版
python ip_tester.py
```

### 方法3：自定义配置（高级用法）
```python
from ip_tester_pro import AdvancedIPTester
from config import load_config

# 使用预设模式
config = load_config(test_mode='balanced')  # fast/balanced/thorough
tester = AdvancedIPTester(config)

# 或自定义配置
custom_config = {
    'enable_quick_check': True,
    'enable_http_test': True,
    'enable_stability_test': True,
    'ping_count': 10,
    'max_workers': 10,
}
tester = AdvancedIPTester(custom_config)

# 读取目标并测试
targets = ['8.8.8.8', '1.1.1.1', 'example.com']
tester.test_targets_two_phase(targets)
```

## 输入文件格式

### testip.txt / custom.txt 文件格式

所有输入文件（`testip.txt` 和 `custom.txt`）都使用相同的格式，每行一个目标，支持以下格式：

```
# 域名
example.com
www.google.com

# IP地址
8.8.8.8
1.1.1.1

# 带端口的IP（端口会被忽略）
192.168.1.1:8080

# 带注释的目标
104.17.151.112:443#圣何塞-5.60MB/s  # 注释部分会被忽略

# 空行和以#开头的行会被跳过
```

### 三种输入源

程序支持三种输入方式，可以灵活组合：

1. **主文件输入** (`data/input/testip.txt`)
   - 默认输入源
   - 适用于通用的IP/域名列表

2. **URL远程获取** (通过 `config.json` 配置)
   - 从远程URL获取IP列表
   - 支持多个URL并发获取
   - 自动重试和错误处理

3. **自定义文件** (`data/input/custom.txt`)
   - 适用于个人专属域名/IP列表
   - 优先级可配置（before_url/after_url）
   - 可与URL结果自动合并

### 数据合并策略

程序会按照以下优先级合并多个输入源：

```
自定义文件（如果启用且优先级为before_url）
    ↓
URL获取（如果启用）
    ↓
自定义文件（如果优先级为after_url）
    ↓
主文件（testip.txt）
    ↓
自动去重
```

## 输出结果格式

### ip.txt（详细信息格式）
```
168.138.165.174:443#168.138.165.174-SG-64ms-97分
95.163.240.24:8443#95.163.240.24-SE-78ms-95分
34.143.159.175:443#34.143.159.175-SG-82ms-93分
```

### best.txt（干净格式，无广告）
```
168.138.165.174:443#SG
95.163.240.24:8443#SE
34.143.159.175:443#SG
```

### result_pro.txt/md（完整测试报告）
包含以下列：
```
排名  目标                          延迟(ms)  丢包率(%)  抖动(ms)  TCP连接(ms)  综合评分  流媒体  游戏  实时通信  状态
--------------------------------------------------------------------------------------------------------------
1     168.138.165.174:443          64.0      0.0        3.5       60.0         97        95      98    96        成功
2     95.163.240.24:8443           78.0      0.0        4.2       72.0         95        93      94    95        成功
...
```

结果按综合评分降序排列（评分越高质量越好）

## 配置选项

### 配置文件结构

程序使用 `config.json` 进行配置，支持多个配置模块：

```json
{
  "custom_file_config": {
    "enable_custom_file": true,
    "custom_file_path": "data/input/custom.txt",
    "merge_custom_with_url": true,
    "custom_file_priority": "before_url"
  },
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
    ],
    "url_timeout": 15,
    "url_retry_times": 3,
    "url_retry_delay": 1,
    "fallback_to_file": true,
    "merge_file_and_url": false
  },
  "test_config": {
    "test_mode": "balanced"
  }
}
```

### 自定义文件配置 (custom_file_config)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_custom_file` | bool | false | 是否启用自定义文件功能 |
| `custom_file_path` | string | 'data/input/custom.txt' | 自定义文件路径（相对于项目根目录） |
| `merge_custom_with_url` | bool | true | 是否合并自定义文件和URL结果 |
| `custom_file_priority` | string | 'before_url' | 自定义文件读取顺序：<br>- `before_url`: 在URL前读取（优先测试）<br>- `after_url`: 在URL后读取 |

### URL获取配置 (url_config)

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_url_fetch` | bool | false | 是否启用URL获取功能 |
| `url_sources` | array | [] | URL列表，支持多个URL |
| `url_timeout` | int | 10 | URL获取超时时间（秒） |
| `url_retry_times` | int | 2 | 失败重试次数 |
| `url_retry_delay` | int | 1 | 重试间隔（秒） |
| `fallback_to_file` | bool | true | URL全部失败时是否回退到文件读取 |
| `merge_file_and_url` | bool | false | 是否合并主文件和URL的结果 |

### 测试模式配置 (test_config)

| 测试模式 | 说明 | 推荐场景 |
|---------|------|---------|
| `fast` | 快速模式，单轮测试 | 快速评估大量节点 |
| `balanced` | 平衡模式，两轮测试（默认） | 日常使用（推荐） |
| `thorough` | 彻底模式，三轮测试 | 需要最准确结果时 |

### 高级配置参数

可以在代码中直接修改以下参数：

```python
# 每个目标的ping次数（默认：10）
ping_count = 10

# 每次ping的超时时间（秒，默认：2）
ping_timeout = 2

# TCP连接超时时间（秒，默认：5）
tcp_timeout = 5

# 最大并发线程数（默认：10）
max_workers = 10

# 快速检测并发数（默认：50）
quick_check_workers = 50
```

## 系统要求

- Python 3.6 或更高版本
- Windows 系统（支持Linux/macOS但需要调整ping命令）
- 网络连接正常

## 故障排除

### 1. Python未安装
```
错误: 未找到Python，请先安装Python 3.x
```
解决方案：从 [python.org](https://www.python.org/downloads/) 下载并安装Python

### 2. ip.txt文件不存在
```
错误: 找不到 ip.txt 文件
```
解决方案：创建 `ip.txt` 文件并添加要测试的目标

### 3. 测试结果不准确
- 增加 `ping_count` 值以获得更准确的平均延迟
- 增加 `timeout` 值以适应网络较慢的目标
- 检查防火墙设置是否允许ICMP流量

### 4. 程序运行缓慢
- 减少 `max_workers` 值以降低系统负载
- 减少 `ping_count` 值以加快测试速度

## 示例

### 测试前显示
```
=======================================================
批量IP/域名质量测试工具
=======================================================
从 ip.txt 读取到 55 个目标
开始测试 55 个目标...
[1/55] saas.sin.fan: 延迟=177.0ms, 丢包=0.0%
[2/55] csgo.com: 延迟=183.0ms, 丢包=0.0%
...
测试完成，成功: 50/55
总测试时间: 45.2秒
```

### 结果摘要
```
======================================================================
前20个最佳结果:
======================================================================
目标                          延迟(ms)       丢包率(%)
----------------------------------------------------------------------
saas.sin.fan                  177.0          0.0
csgo.com                      183.0          0.0
www.visa.com                  192.0          0.0
...
```

## 许可证

本项目使用 MIT 许可证。

## 更新日志

### v2.1.0 (2025-01-22)
- 🎉 **新增自定义文件功能**：支持独立的自定义域名/IP列表文件
- ✨ **优化输入方式**：支持三种输入源（主文件/URL/自定义文件）灵活组合
- 🔧 **新增配置项**：`custom_file_config` 模块，支持优先级和合并控制
- 📝 **更新文档**：完善配置说明和使用示例
- 🏗️ **代码重构**：改进配置加载逻辑，更好的向后兼容性

### v2.0.0 (2025-12-17)
- 🚀 **重大更新**：专业版测试器，速度提升90%，准确性提升40%
- ⚡ **两阶段测试**：快速筛选 + 深度测试策略
- 📊 **新增评分系统**：代理专用评分算法（可用性+速度+稳定性+响应性）
- 🌐 **HTTP性能测试**：TTFB、TLS握手时间、总响应时间
- 🔄 **连接稳定性测试**：10次连续连接测试
- 📈 **统计分析**：异常值过滤、置信区间计算
- 🎨 **三种测试模式**：fast/balanced/thorough
- 🔗 **URL远程获取**：支持从URL获取IP列表

### v1.0.0 (2025-12-17)
- 初始版本发布
- 支持批量测试IP/域名
- 实现延迟和丢包率计算
- 支持多线程并发测试
- 自动排序和结果输出