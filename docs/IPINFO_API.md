# IP 信息查询 API 集成说明

## 📋 概述

bestip 项目已集成 [ipinfo.dkly.net](https://ipinfo.dkly.net) API，可以获取更丰富的 IP 信息，包括：

- 🌍 **地理位置**：国家、地区、城市、经纬度
- 🏢 **网络信息**：ASN、运营商/组织、连接类型
- 🔒 **安全检测**：VPN、代理、Tor、威胁检测
- 🕐 **时区信息**：时区 ID、UTC 偏移

## 🚀 快速开始

### 1. 获取 API Key

1. 访问 [ipinfo.dkly.net](https://ipinfo.dkly.net)
2. 注册账号并获取 API Key
3. 选择合适的计划（推荐 Pro Plus：200,000 请求/月）

### 2. 配置 API Key

编辑项目根目录的 `config.yaml` 文件：

```yaml
# IP 信息查询配置
enable_ipinfo: true
ipinfo_api_key: "your_api_key_here"  # 替换为你的 API Key
```

### 3. 运行测试

```bash
python main.py
```

## ⚙️ 配置选项

在 `config.yaml` 中可以配置以下选项：

```yaml
# 是否启用 IP 信息查询
enable_ipinfo: true

# API 密钥
ipinfo_api_key: "your_api_key_here"

# API 速率限制（请求/分钟）
# 所有计划统一为 60 请求/分钟
ipinfo_rate_limit: 60

# API 请求超时（秒）
ipinfo_timeout: 10

# API 请求最大重试次数
ipinfo_max_retries: 3

# API 请求重试延迟（秒）
ipinfo_retry_delay: 1

# 是否启用缓存
# 推荐启用，可以节省 API 配额
ipinfo_enable_cache: true

# 缓存有效期（秒）
# 默认 3600 秒（1小时）
ipinfo_cache_ttl: 3600
```

## 📊 功能特性

### 1. 智能回退机制

- **优先使用** ipinfo.dkly.net API 获取详细信息
- **自动回退** 到 Cloudflare trace 接口（如果 API 不可用）
- **无缝切换** 不影响测试流程

### 2. 速率限制保护

- 自动遵守 60 请求/分钟的速率限制
- 智能等待机制，避免触发限流
- 请求队列管理，确保稳定运行

### 3. 缓存优化

- 默认启用 1 小时缓存
- 减少重复 API 调用
- 节省 API 配额

### 4. 错误处理

- 完善的异常处理机制
- 自动重试失败的请求
- 详细的错误日志输出

## 📈 输出增强

### Markdown 报告新增内容

测试完成后，`data/output/result_pro.md` 会包含新的 **IP 详细信息表**：

```markdown
## 🌐 IP 详细信息

| 排名 | 目标 | 地理位置 | ASN | 运营商/组织 | 代理类型 |
|:---:|:---|:---|:---|:---|:---:|
| 1 | `1.1.1.1:443` | 美国-加利福尼亚-旧金山 | `AS13335` | Cloudflare, Inc. | ✅ 直连 |
| 2 | `8.8.8.8:443` | 美国 | `AS15169` | Google LLC | ✅ 直连 |
```

### 地理位置信息

原有的地理位置字段会显示更详细的信息：

- **之前**：`SG/US`（机场代码/国家代码）
- **现在**：`新加坡-新加坡-新加坡`（国家-地区-城市）

### 代理类型标识

自动识别并标注节点类型：

- 🔒 **VPN**：VPN 节点
- 🌐 **Proxy**：代理节点
- 🧅 **Tor**：Tor 出口节点
- ✅ **直连**：非代理节点

## 💡 使用建议

### 1. 配额管理

**Pro Plus 计划（200,000 请求/月）：**

- 每天约 6,600 次请求
- 每小时约 275 次请求
- 建议启用缓存以节省配额

**测试规模建议：**

- 小规模测试（<50 个节点）：随意测试
- 中等规模（50-200 个节点）：注意缓存利用
- 大规模测试（>200 个节点）：建议分批测试

### 2. 缓存策略

**推荐配置：**

```yaml
ipinfo_enable_cache: true
ipinfo_cache_ttl: 3600  # 1小时
```

**适用场景：**

- ✅ 重复测试相同的 IP 列表
- ✅ 短时间内多次运行测试
- ❌ 需要实时最新的 IP 信息

### 3. 性能优化

**速率限制影响：**

- 60 请求/分钟 = 每秒 1 次请求
- 测试 100 个节点约需 1.7 分钟（仅 API 查询时间）
- 启用缓存可显著减少等待时间

**优化建议：**

1. 启用快速检测模式，先筛选可用节点
2. 只对通过筛选的节点进行详细测试
3. 充分利用缓存机制

## 🔧 故障排查

### API Key 无效

**症状：**
```
[ERROR] API 认证失败: API Key 无效
```

**解决方案：**
1. 检查 `config.yaml` 中的 `ipinfo_api_key` 是否正确
2. 确认 API Key 没有过期
3. 访问 [ipinfo.dkly.net](https://ipinfo.dkly.net) 验证账号状态

### 速率限制

**症状：**
```
[WARNING] API 请求过于频繁，已达到速率限制
```

**解决方案：**
1. 程序会自动等待并重试
2. 启用缓存减少 API 调用
3. 减少并发测试数量

### API 不可用

**症状：**
```
[WARNING] IP 信息 API 查询失败: xxx，使用备用方法
```

**影响：**
- 自动回退到 Cloudflare trace 接口
- 只能获取基本的地理位置信息
- 不影响测试流程继续进行

**解决方案：**
1. 检查网络连接
2. 确认 API 服务状态
3. 查看详细错误日志

## 📚 API 文档

完整的 API 文档请访问：[https://ipinfo.dkly.net/documentation](https://ipinfo.dkly.net/documentation)

## 🎯 最佳实践

1. **始终启用缓存**：节省配额，提高性能
2. **合理设置超时**：避免长时间等待
3. **监控配额使用**：定期检查剩余配额
4. **分批测试大量节点**：避免一次性消耗过多配额
5. **保护 API Key**：不要将 API Key 提交到公共仓库

## 🔐 安全建议

### 保护 API Key

**方法 1：使用环境变量**

```bash
# Windows
set IPINFO_API_KEY=your_api_key_here

# Linux/Mac
export IPINFO_API_KEY=your_api_key_here
```

然后在代码中读取：

```python
import os
api_key = os.environ.get('IPINFO_API_KEY', '')
```

**方法 2：使用 .gitignore**

确保 `config.yaml` 不被提交到版本控制：

```gitignore
# .gitignore
config.yaml
```

创建 `config.yaml.example` 作为模板：

```yaml
# config.yaml.example
ipinfo_api_key: "your_api_key_here"  # 替换为你的 API Key
```

## 📞 支持

如有问题或建议，请：

1. 查看项目文档：`docs/` 目录
2. 提交 Issue：项目 GitHub 仓库
3. 参考 API 文档：[ipinfo.dkly.net/documentation](https://ipinfo.dkly.net/documentation)

---

**更新时间**：2026-02-02
**版本**：v1.0
