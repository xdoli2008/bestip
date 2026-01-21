# IP测试工具 - 技术开发文档

## 项目概述

这是一个高级IP/域名质量测试工具，基于专业网络质量评估算法实现。工具从`ip.txt`读取目标列表，批量测试延迟、丢包率、抖动和TCP性能，并按综合评分排序输出结果。

### 核心功能
- ✅ 批量测试IP/域名质量（支持带端口和注释的目标）
- ✅ 专业测试指标：延迟、丢包率、抖动、TCP连接时间
- ✅ 综合评分系统（流媒体、游戏、实时通信评分）
- ✅ 并发测试（默认10线程，可配置）
- ✅ 智能目标清理（自动去除端口和注释）
- ✅ 多格式输出（Markdown + 文本）
- ✅ 实时进度显示和错误处理

## 系统架构

### 文件结构
```
bestip/
├── ip.txt                    # 输入文件：测试目标列表
├── ip_tester_pro.py          # 主程序：高级测试器
├── run_pro.bat               # 启动脚本
├── result_pro.md             # 输出文件：Markdown格式结果
├── result_pro.txt            # 输出文件：文本格式结果
└── README.md                 # 使用说明
```

### 核心类：`AdvancedIPTester`

```python
class AdvancedIPTester:
    def __init__(self, config: Dict = None)
    def test_targets(self, targets: List[str]) -> List[Dict]
    def test_target(self, target: str) -> Dict
    def save_results_md(self, output_file: str = 'result_pro.md')
    def save_results(self, output_file: str = 'result_pro.txt')
    def sort_results(self, sort_by: str = 'overall') -> List[Dict]
    def display_summary(self, top_n: int = 20)
```

## 系统要求

### Python版本
- **Python 3.6+**（需要`statistics`、`concurrent.futures`等标准库模块）
- 推荐Python 3.8或更高版本以获得最佳性能

### 操作系统
- **Windows**：完全支持（自动检测中英文系统）
- **Linux/macOS**：支持但需要调整ping命令参数
- 需要管理员/root权限才能执行ping命令（某些系统）

### 依赖项
- 纯Python标准库，无外部依赖
- 需要的标准库模块：
  - `subprocess`：执行ping命令
  - `re`：解析ping输出
  - `statistics`：计算抖动（标准差）
  - `socket`：TCP连接测试
  - `threading`：并发控制
  - `concurrent.futures`：线程池
  - `datetime`：时间戳生成

### 网络要求
- 能够执行ICMP ping（某些网络可能禁止ICMP）
- 出站TCP连接权限（用于测试TCP连接）
- 稳定的互联网连接

## 配置参数

### 默认配置
```python
config = {
    'ping_count': 10,      # 每个目标的ping次数（影响抖动计算精度）
    'ping_timeout': 2,     # ping超时时间（秒）
    'tcp_timeout': 5,      # TCP连接超时时间（秒）
    'max_workers': 10      # 并发线程数
}
```

### 参数说明
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| ping_count | int | 10 | 影响抖动计算精度，值越大越准确但越慢 |
| ping_timeout | int | 2 | Windows: -w参数（毫秒），Linux: -W参数（秒） |
| tcp_timeout | int | 5 | socket连接超时时间 |
| max_workers | int | 10 | 线程池大小，影响并发性能 |

## 测试算法

### 1. 延迟计算
- **采集**：从ping命令输出中提取所有延迟样本
- **统计**：计算平均值、最小值、最大值
- **公式**：`avg_delay = mean(delays)`

### 2. 丢包率计算
- **采集**：从ping统计信息中提取丢失包数
- **公式**：`loss_rate = (lost_packets / total_packets) * 100%`

### 3. 抖动计算
- **定义**：延迟的标准差，反映网络稳定性
- **公式**：`jitter = stdev(delays)` （需要至少2个样本）

### 4. TCP连接测试
- **方法**：使用socket建立TCP连接
- **测量**：记录连接建立时间
- **端口**：默认443，可从目标字符串中提取（如`:50001`）

### 5. 综合评分算法（基于Cloudflare AIM模型）

#### 流媒体评分（权重30%）
```python
# 延迟扣分
if delay > 300: score -= 50
elif delay > 200: score -= 30
elif delay > 100: score -= 10

# 丢包扣分
if loss > 5: score -= 40
elif loss > 3: score -= 20
elif loss > 1: score -= 10

# 抖动扣分
if jitter > 100: score -= 20
elif jitter > 50: score -= 10
```

#### 游戏评分（权重30%）
```python
# 丢包非常敏感
if loss > 2: score -= 40
elif loss > 1: score -= 20
elif loss > 0.5: score -= 10

# 延迟敏感
if delay > 150: score -= 30
elif delay > 100: score -= 20
elif delay > 50: score -= 10

# 抖动敏感
if jitter > 50: score -= 20
elif jitter > 20: score -= 10
```

#### 实时通信评分（权重40%）
```python
# 丢包非常敏感
if loss > 1: score -= 30
elif loss > 0.5: score -= 20
elif loss > 0.1: score -= 10

# 抖动非常敏感
if jitter > 30: score -= 30
elif jitter > 20: score -= 20
elif jitter > 10: score -= 10

# 延迟有一定容忍度
if delay > 200: score -= 20
elif delay > 150: score -= 15
elif delay > 100: score -= 10
```

#### 总体评分
```python
overall_score = int((streaming_score * 0.3 + gaming_score * 0.3 + rtc_score * 0.4))
```

## 并发架构

### 线程池设计
```python
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    future_to_target = {
        executor.submit(self._test_target_with_progress, target, idx, len(targets)): (target, idx)
        for idx, target in enumerate(targets)
    }
```

### 输出同步
使用`threading.Lock()`确保并发测试时输出不混乱：
```python
self.print_lock = threading.Lock()

def _test_target_with_progress(self, target: str, idx: int, total: int) -> Dict:
    with self.print_lock:
        print(f"[{idx+1}/{total}] ", end='', flush=True)
        result = self.test_target(target)
        # ... 其他输出
```

## 目标清理算法

### 处理规则
1. **去除注释**：`目标#注释` → `目标`
2. **去除端口**：`IP:端口` → `IP`（仅当端口为数字时）
3. **IPv6保护**：包含多个`:`时不处理（可能是IPv6地址）

### 实现代码
```python
def _clean_target(self, target: str) -> str:
    clean_target = target.strip()
    
    # 处理注释部分
    if '#' in clean_target:
        clean_target = clean_target.split('#')[0].strip()
    
    # 处理端口部分（小心处理IPv6）
    if ':' in clean_target and clean_target.count(':') <= 1:
        parts = clean_target.split(':')
        if len(parts) == 2 and parts[1].isdigit():
            clean_target = parts[0].strip()
    
    return clean_target
```

## 输入文件格式

### 支持格式
```txt
# 基本格式
example.com
8.8.8.8

# 带端口
111.171.108.67:50001
example.com:8080

# 带注释
104.17.151.112:443#圣何塞-5.60MB/s
20.247.137.183:443#新加坡

# IPv6地址（注意：端口处理可能有限）
2001:db8::1
[2001:db8::1]:8080

# 注释行（会被忽略）
# 这是注释行
```

### 解析逻辑
```python
def read_targets_from_file(filename: str = 'ip.txt') -> List[str]:
    targets = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                targets.append(line)
    return targets
```

## 输出格式

### Markdown格式（result_pro.md）
- **表格展示**：清晰的Markdown表格
- **可视化评分**：表情符号表示质量等级
  - 🟢 优秀 (80-100分)
  - 🟡 良好 (60-79分)
  - 🟠 一般 (40-59分)
  - 🔴 较差 (0-39分)
- **详细说明**：包含评分说明、指标解释
- **失败统计**：单独列出失败目标

### 文本格式（result_pro.txt）
- **兼容性**：纯文本，兼容所有编辑器
- **结构化**：固定宽度列对齐
- **完整数据**：包含所有测试结果

### 控制台输出
```
[1/55] 测试Ping: 111.171.108.67...
测试TCP连接: 111.171.108.67:50001...
  延迟: 64.2ms, 丢包: 0.0%, 抖动: 6.9ms
  评分: 总体97, 流媒体100, 游戏90, 通话100
```

## API参考

### 主要方法

#### `AdvancedIPTester.test_targets(targets: List[str]) -> List[Dict]`
批量测试多个目标，返回结果列表。

**参数**：
- `targets`: 目标字符串列表

**返回**：
```python
[{
    'original': '111.171.108.67:50001#韩国',
    'target': '111.171.108.67',
    'ping': {
        'delays': [64.0, 65.0, 63.0, ...],
        'avg_delay': 64.2,
        'min_delay': 63.0,
        'max_delay': 65.0,
        'loss_rate': 0.0,
        'jitter': 6.9,
        'success': True
    },
    'tcp': {
        'success': True,
        'connect_time': 78.9,
        'error': None
    },
    'scores': {
        'overall': 97,
        'streaming': 100,
        'gaming': 90,
        'rtc': 100
    },
    'success': True,
    'error': None
}]
```

#### `AdvancedIPTester.sort_results(sort_by: str = 'overall') -> List[Dict]`
对结果进行排序。

**排序选项**：
- `'overall'`: 综合评分（默认）
- `'streaming'`: 流媒体评分
- `'gaming'`: 游戏评分
- `'rtc'`: 实时通信评分
- `'delay'`: 延迟
- `'loss'`: 丢包率

#### `AdvancedIPTester.save_results_md(output_file: str = 'result_pro.md')`
保存结果为Markdown格式。

#### `AdvancedIPTester.save_results(output_file: str = 'result_pro.txt')`
保存结果为文本格式。

### 工具函数

#### `read_targets_from_file(filename: str = 'ip.txt') -> List[str]`
从文件读取目标列表，支持utf-8和gbk编码。

## 性能优化

### 并发策略
- **默认10线程**：平衡性能和资源消耗
- **动态调整**：可根据目标数量调整线程数
- **超时控制**：防止单个目标阻塞整个测试

### 内存管理
- **增量处理**：结果实时收集，不堆积在内存
- **流式输出**：边测试边显示进度

### 网络优化
- **连接复用**：TCP连接测试后立即关闭
- **超时设置**：防止长时间等待无响应目标

## 扩展点

### 1. 新增测试指标
```python
def test_bandwidth(self, target: str) -> Dict:
    """测试带宽（需要安装iperf等工具）"""
    pass

def test_route(self, target: str) -> Dict:
    """测试路由路径（traceroute）"""
    pass
```

### 2. 自定义评分算法
```python
def set_scoring_weights(self, weights: Dict[str, float]):
    """设置评分权重"""
    # weights = {'streaming': 0.3, 'gaming': 0.3, 'rtc': 0.4}
    pass

def add_custom_score(self, name: str, calculator: Callable):
    """添加自定义评分项"""
    pass
```

### 3. 输出格式扩展
```python
def save_results_json(self, output_file: str):
    """保存为JSON格式"""
    pass

def save_results_csv(self, output_file: str):
    """保存为CSV格式"""
    pass

def generate_report_html(self, output_file: str):
    """生成HTML报告"""
    pass
```

### 4. 数据持久化
```python
def save_to_database(self, connection):
    """保存到数据库"""
    pass

def load_previous_results(self) -> List[Dict]:
    """加载历史结果进行比较"""
    pass
```

## 待优化项

### 高优先级
1. **IPv6支持**：目前IPv6地址的端口处理不完善
2. **带宽测试**：集成iperf进行真实带宽测量
3. **历史对比**：支持与历史测试结果对比

### 中优先级
1. **配置文件**：支持外部配置文件（JSON/YAML）
2. **结果缓存**：缓存成功目标，避免重复测试
3. **批量导出**：支持导出为多种格式（JSON、CSV、Excel）

### 低优先级
1. **Web界面**：提供Web管理界面
2. **定时任务**：支持定时自动测试
3. **告警通知**：质量下降时发送通知

## 故障排除

### 常见问题

#### 1. 测试速度慢
**原因**：网络延迟高或目标无响应
**解决**：
- 调整`ping_timeout`减少等待时间
- 减少`ping_count`加速测试
- 检查网络连接

#### 2. 并发测试输出混乱
**原因**：多个线程同时输出
**解决**：已使用`threading.Lock()`同步输出

#### 3. 带端口目标测试失败
**原因**：端口未正确清理
**解决**：检查`_clean_target()`方法逻辑

#### 4. 评分算法不合理
**原因**：阈值设置不适合当前网络环境
**解决**：调整`calculate_quality_score()`中的扣分阈值

### 调试建议
1. 使用小规模测试集验证功能
2. 调整配置参数观察影响
3. 查看详细日志定位问题

## 版本历史

### v2.0.0 (2025-12-17) - 当前版本
- 高级测试指标：抖动、TCP连接时间
- 综合评分系统（基于Cloudflare AIM模型）
- 并发测试（默认10线程）
- Markdown格式输出
- 智能目标清理

### v1.0.0 (2025-12-17) - 基础版本
- 基础延迟和丢包率测试
- 多线程并发
- 文本格式输出

## 开发建议

### 代码规范
1. **类型提示**：所有函数使用类型提示
2. **文档字符串**：重要函数添加详细文档
3. **错误处理**：妥善处理异常情况
4. **代码复用**：提取公共逻辑为独立函数

### 测试策略
1. **单元测试**：测试核心算法（评分、清理等）
2. **集成测试**：测试完整流程
3. **性能测试**：测试并发性能和大数据量处理

### 维护建议
1. **定期更新**：更新依赖库和安全补丁
2. **文档同步**：代码变更时更新文档
3. **用户反馈**：收集用户需求持续改进

---

**最后更新**：2025-12-17  
**维护者**：AI助手  
**状态**：生产就绪，持续维护中