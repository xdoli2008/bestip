# 配置文件使用指南（YAML）

本项目使用 YAML 配置文件：`config.yaml` 或 `config.yml`。

## 快速开始

1. 安装依赖（用于读取 YAML）：
   ```bash
   pip install pyyaml
   ```

2. 创建配置文件：
   ```bash
   cp config.example.yaml config.yaml
   ```

3. 运行：
   ```bash
   python main.py
   ```

## 配置优先级

从高到低：
1. 代码中的 `custom_config`
2. `config.yaml` / `config.yml`
3. `test_mode` 预设（fast/balanced/thorough）
4. 默认值（见 `src/config/config.py`）

## 输入源配置（目标列表）

目标来源支持三种，可组合；最终会自动去重：

1. 主文件：`data/input/testip.txt`（默认）
2. URL 获取：`enable_url_fetch: true`
3. 自定义文件：`enable_custom_file: true`

关键参数：
- URL 获取：`enable_url_fetch`、`url_sources`、`url_timeout`、`url_retry_times`、`fallback_to_file`、`merge_file_and_url`
- 自定义文件：`enable_custom_file`、`custom_file_path`、`custom_file_priority`、`merge_custom_with_url`

示例：启用 URL 获取并允许回退到文件
```yaml
enable_url_fetch: true
url_sources:
  - https://example.com/list.txt
fallback_to_file: true
```

示例：启用自定义文件（优先于 URL）
```yaml
enable_custom_file: true
custom_file_path: data/input/custom.txt
custom_file_priority: before_url
merge_custom_with_url: true
```

## 测试模式与并发

推荐先用模式，再按需微调：
```yaml
test_mode: balanced  # fast / balanced / thorough
```

并发相关：
```yaml
enable_quick_check: true
quick_check_workers: 50   # 第一阶段快速检测并发
max_workers: 10           # 第二阶段深度测试并发
```

## 网站连通性测试（仅展示）

用于“展示该 IP 是否能访问指定站点”，不参与综合评分与排序：
```yaml
enable_streaming_test: true
streaming_sites:
  - https://chatgpt.com
  - https://www.youtube.com
streaming_timeout: 15
streaming_concurrent: true
```

## HTTP 性能测试（可仅展示）

HTTP 测试用于测量 TTFB/响应头时间。Cloudflare 优选 IP 场景常见做法：
1) 保持 `enable_http_test: true` 让报告展示 HTTP 指标  
2) 设置 `score_include_http: false` 让它不参与综合评分与排序

```yaml
enable_http_test: true
score_include_http: false
http_test_url: https://cp.cloudflare.com/generate_204
http_timeout: 10
```

实现说明（Cloudflare 优选 IP）：程序会“连接到目标 IP”，但用 `http_test_url` 的域名作为 SNI/Host 发起请求，
从而评估“通过该边缘 IP 访问该域名”的可用性与 TTFB。

## 常见问题

### Q1: 没有 `config.yaml` 会怎样？
使用默认配置（从 `data/input/testip.txt` 读取）。

### Q2: 配置不生效，怎么排查？
1. 确认 `config.yaml` 在项目根目录
2. 确认已安装 `pyyaml`
3. 对照 `config.example.yaml` 检查参数名拼写

## 新增功能配置（v2.1+）

### 下载速度测试
测试真实下载速度，更准确反映带宽质量：
```yaml
enable_download_test: true
download_test_duration: 10  # 测试时长（秒）
download_timeout: 15         # 超时时间（秒）
```

**注意：** 会显著增加测试时间（每个节点约10秒）

### 地理位置检测
自动检测IP的地理位置（机场代码、国家等）：
```yaml
enable_location_test: true
location_timeout: 5  # 超时时间（秒）
```

### 改进的排序算法
按丢包率分组后再排序，避免高丢包低延迟IP排前面：
```yaml
sort_by: quality  # quality / overall / delay / loss
quality_sort_candidates: 10
```

**排序策略：**
- `quality`（推荐）：按丢包率分组（0% > <5% > <10% > >=10%），组内按延迟和速度排序
- `overall`：按综合评分降序
- `delay`：按延迟升序
- `loss`：按丢包率升序

### 改进的快速检测改进
提高快速检测阶段的准确性：
```yaml
quick_ping_count: 3  # 从1次增加到3次
```

### IP 信息查询配置 (v3.0+)
集成 [ipinfo.dkly.net](https://ipinfo.dkly.net) API 以获取更详细的节点信息：
```yaml
enable_ipinfo: true             # 是否启用
ipinfo_api_key: "YOUR_KEY"      # 你的 API Key
ipinfo_enable_cache: true       # 启用缓存以节省配额
ipinfo_cache_ttl: 3600          # 缓存时长（秒）
```
详情请参阅 [docs/IPINFO_API.md](docs/IPINFO_API.md)。
