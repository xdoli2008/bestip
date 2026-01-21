# 配置文件使用指南

## 快速开始

### 1. 创建配置文件

```bash
# 复制示例配置文件
cp config.example.json config.json
```

### 2. 编辑配置文件

使用任何文本编辑器打开 `config.json`，修改URL列表：

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://your-url-1.com/ip-list.txt",
      "https://your-url-2.com/backup-list.txt"
    ]
  }
}
```

### 3. 运行程序

```bash
python main.py
```

---

## 配置文件结构

配置文件采用JSON格式，分为4个主要部分：

### 1. URL输入配置 (url_config)

控制从URL获取IP列表的行为。

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://example.com/ip-list.txt"
    ],
    "url_timeout": 15,
    "url_retry_times": 3,
    "url_retry_delay": 1,
    "fallback_to_file": true,
    "merge_file_and_url": false
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_url_fetch` | boolean | false | 是否启用URL获取功能 |
| `url_sources` | array | [] | URL列表，支持多个URL |
| `url_timeout` | number | 10 | URL获取超时时间（秒） |
| `url_retry_times` | number | 2 | 失败后重试次数 |
| `url_retry_delay` | number | 1 | 重试间隔（秒） |
| `fallback_to_file` | boolean | true | URL失败时是否回退到文件 |
| `merge_file_and_url` | boolean | false | 是否合并文件和URL的结果 |

### 2. 测试配置 (test_config)

基础测试参数配置。

```json
{
  "test_config": {
    "test_mode": "balanced",
    "ping_count": 10,
    "ping_timeout": 2,
    "tcp_timeout": 5,
    "max_workers": 10
  }
}
```

**参数说明：**

| 参数 | 类型 | 可选值 | 说明 |
|------|------|--------|------|
| `test_mode` | string | fast/balanced/thorough | 测试模式 |
| `ping_count` | number | - | Ping测试次数 |
| `ping_timeout` | number | - | Ping超时时间（秒） |
| `tcp_timeout` | number | - | TCP连接超时（秒） |
| `max_workers` | number | - | 深度测试并发数 |

**测试模式说明：**

- **fast**: 快速模式，单轮测试，适合快速筛选
- **balanced**: 平衡模式，两轮测试，推荐使用
- **thorough**: 彻底模式，三轮测试，最准确但最慢

### 3. 快速检测配置 (quick_check_config)

第一阶段快速筛选的配置。

```json
{
  "quick_check_config": {
    "enable_quick_check": true,
    "quick_check_workers": 50,
    "quick_ping_count": 1,
    "quick_ping_timeout": 1,
    "quick_tcp_timeout": 2
  }
}
```

### 4. 高级配置 (advanced_config)

高级测试功能配置。

```json
{
  "advanced_config": {
    "enable_multi_round": true,
    "test_rounds": 2,
    "enable_http_test": true,
    "enable_stability_test": true,
    "stability_attempts": 10
  }
}
```

---

## 使用场景

### 场景1：仅使用URL输入（推荐）

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
    ],
    "fallback_to_file": false
  },
  "test_config": {
    "test_mode": "balanced"
  }
}
```

### 场景2：URL + 文件备份

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://example.com/ip-list.txt"
    ],
    "fallback_to_file": true
  }
}
```

当URL获取失败时，自动回退到 `data/input/testip.txt` 文件。

### 场景3：多URL合并

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://source1.com/list.txt",
      "https://source2.com/list.txt",
      "https://source3.com/backup.txt"
    ],
    "url_timeout": 15,
    "url_retry_times": 3
  }
}
```

程序会从所有URL获取IP列表并自动合并去重。

### 场景4：URL + 文件合并

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://example.com/ip-list.txt"
    ],
    "merge_file_and_url": true
  }
}
```

同时使用URL和本地文件的IP列表。

### 场景5：快速测试模式

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": ["https://example.com/list.txt"]
  },
  "test_config": {
    "test_mode": "fast"
  }
}
```

使用快速模式，适合大量节点的初步筛选。

---

## 配置优先级

配置加载的优先级从高到低：

1. **代码中的自定义配置** (custom_config参数)
2. **config.json 配置文件**
3. **测试模式预设** (test_mode)
4. **默认配置** (DEFAULT_CONFIG)

---

## 常见问题

### Q1: 配置文件不存在会怎样？

A: 程序会显示提示信息并使用默认配置（从 `data/input/testip.txt` 读取）。

### Q2: JSON格式错误会怎样？

A: 程序会显示错误信息并使用默认配置。

### Q3: 如何禁用URL功能？

A: 设置 `"enable_url_fetch": false` 或删除 config.json 文件。

### Q4: 可以只配置部分参数吗？

A: 可以！未配置的参数会使用默认值。

### Q5: 如何添加注释？

A: JSON标准不支持注释，但可以使用 `"_comment"` 字段：

```json
{
  "_comment": "这是我的配置说明",
  "url_config": {
    "_comment": "URL配置部分",
    "enable_url_fetch": true
  }
}
```

---

## 配置文件示例

### 最小配置

```json
{
  "url_config": {
    "enable_url_fetch": true,
    "url_sources": [
      "https://example.com/ip-list.txt"
    ]
  }
}
```

### 完整配置

参考 `config.example.json` 文件。

---

## 故障排查

### 问题：URL获取失败

**检查项：**
1. URL是否可访问
2. 网络连接是否正常
3. 超时时间是否足够
4. 是否启用了回退机制

**解决方案：**
- 增加 `url_timeout` 和 `url_retry_times`
- 启用 `fallback_to_file`
- 添加备用URL

### 问题：配置不生效

**检查项：**
1. config.json 是否在项目根目录
2. JSON格式是否正确
3. 参数名称是否拼写正确

**解决方案：**
- 使用JSON验证工具检查格式
- 参考 config.example.json
- 查看程序输出的错误信息

---

## 更多帮助

- 查看 `config.example.json` 获取完整配置示例
- 查看 `main.py` 文件头部的配置说明
- 查看 `docs/` 目录下的技术文档
