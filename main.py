#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主入口文件

直接运行即可：
    python main.py

## 配置说明

程序会自动读取项目根目录下的 `config.yaml` / `config.yml` 配置文件（YAML）。

### 首次使用

1. 复制 `config.example.yaml` 为 `config.yaml`
2. 编辑 `config.yaml`，按需配置 URL 输入/自定义文件/测试项
3. 运行 python main.py

### 配置文件示例 (config.yaml)

```yaml
# URL 获取
enable_url_fetch: true
url_sources:
  - https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt
url_timeout: 15
url_retry_times: 3
fallback_to_file: true

# 测试模式
test_mode: balanced
```

### 配置优先级

自定义配置 > 配置文件（YAML） > 测试模式 > 默认配置

### 不使用配置文件

如果不存在 `config.yaml` / `config.yml`，程序会使用默认配置（从 `data/input/testip.txt` 读取）。

### 依赖说明

读取 YAML 配置需要 `PyYAML`：`pip install pyyaml`
"""

from src.core.ip_tester_pro import main

if __name__ == '__main__':
    main()
