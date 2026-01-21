# 项目目录结构重构方案

## 当前结构问题

1. 所有文件混在根目录，不易维护
2. 源代码、配置、数据、文档混杂
3. 缺乏模块化组织
4. 测试文件和输出文件混在一起

## 新目录结构设计

```
bestip/
├── src/                          # 源代码目录
│   ├── __init__.py
│   ├── core/                     # 核心模块
│   │   ├── __init__.py
│   │   ├── ip_tester.py          # 基础版测试器
│   │   └── ip_tester_pro.py      # 专业版测试器
│   ├── analyzers/                # 分析器模块
│   │   ├── __init__.py
│   │   ├── statistical_analyzer.py    # 统计分析
│   │   └── proxy_score_calculator.py  # 代理评分
│   ├── utils/                    # 工具模块
│   │   ├── __init__.py
│   │   ├── network.py            # 网络工具（ping、TCP等）
│   │   ├── geo.py                # 地理位置查询
│   │   └── formatter.py          # 格式化输出
│   └── config/                   # 配置模块
│       ├── __init__.py
│       └── config.py             # 配置管理
│
├── tests/                        # 测试目录
│   ├── __init__.py
│   ├── test_improvements.py      # 改进功能测试
│   ├── test_core.py              # 核心功能测试
│   └── test_analyzers.py         # 分析器测试
│
├── data/                         # 数据目录
│   ├── input/                    # 输入文件
│   │   ├── testip.txt            # 测试IP列表
│   │   └── ip.txt                # IP列表（基础版）
│   └── output/                   # 输出文件
│       ├── result.txt            # 基础版结果
│       ├── result_pro.txt        # 专业版结果（文本）
│       ├── result_pro.md         # 专业版结果（Markdown）
│       ├── ip.txt                # 优质节点（详细）
│       └── best.txt              # 优质节点（干净格式）
│
├── docs/                         # 文档目录
│   ├── README.md                 # 项目说明
│   ├── CLAUDE.md                 # Claude Code指南
│   ├── TECHNICAL.md              # 技术文档
│   └── CHANGELOG.md              # 更新日志
│
├── scripts/                      # 脚本目录
│   ├── run.bat                   # 运行基础版（Windows）
│   ├── run_pro.bat               # 运行专业版（Windows）
│   ├── run.sh                    # 运行基础版（Linux）
│   └── run_pro.sh                # 运行专业版（Linux）
│
├── .gitignore                    # Git忽略文件
├── requirements.txt              # 依赖列表（如果有）
└── setup.py                      # 安装脚本（可选）
```

## 重构步骤

### 第1步：创建目录结构
```bash
mkdir -p src/core src/analyzers src/utils src/config
mkdir -p tests
mkdir -p data/input data/output
mkdir -p docs
mkdir -p scripts
```

### 第2步：移动源代码文件
```bash
# 核心模块
mv ip_tester.py src/core/
mv ip_tester_pro.py src/core/

# 分析器模块
mv statistical_analyzer.py src/analyzers/
mv proxy_score_calculator.py src/analyzers/

# 配置模块
mv config.py src/config/
```

### 第3步：移动测试文件
```bash
mv test_improvements.py tests/
```

### 第4步：移动数据文件
```bash
# 输入文件
mv testip.txt data/input/
cp ip.txt data/input/  # 保留一份作为输入模板

# 输出文件
mv result.txt data/output/
mv result_pro.txt data/output/
mv result_pro.md data/output/
mv ip.txt data/output/
mv test_best.txt data/output/
```

### 第5步：移动文档文件
```bash
mv README.md docs/
mv CLAUDE.md docs/
mv TECHNICAL.md docs/
```

### 第6步：移动脚本文件
```bash
mv run.bat scripts/
mv run_pro.bat scripts/
```

### 第7步：创建__init__.py文件
```bash
touch src/__init__.py
touch src/core/__init__.py
touch src/analyzers/__init__.py
touch src/utils/__init__.py
touch src/config/__init__.py
touch tests/__init__.py
```

### 第8步：更新导入路径

需要修改的文件：
1. `src/core/ip_tester_pro.py` - 更新导入路径
2. `tests/test_improvements.py` - 更新导入路径
3. `scripts/run_pro.bat` - 更新执行路径

## 导入路径变更

### 旧导入方式
```python
from config import load_config
from statistical_analyzer import StatisticalAnalyzer
from proxy_score_calculator import ProxyScoreCalculator
```

### 新导入方式
```python
from src.config.config import load_config
from src.analyzers.statistical_analyzer import StatisticalAnalyzer
from src.analyzers.proxy_score_calculator import ProxyScoreCalculator
```

## 优势

1. **清晰的模块划分**：源代码、测试、数据、文档分离
2. **易于维护**：每个模块职责明确
3. **便于扩展**：新功能可以轻松添加到对应模块
4. **专业规范**：符合Python项目最佳实践
5. **版本控制友好**：.gitignore可以更精确地忽略输出文件

## .gitignore 更新建议

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# 输出文件
data/output/*
!data/output/.gitkeep

# 测试输出
tests/output/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

## 执行脚本更新

### scripts/run_pro.bat
```batch
@echo off
cd ..
python -m src.core.ip_tester_pro
pause
```

### scripts/run_pro.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/.."
python -m src.core.ip_tester_pro
```

## 注意事项

1. 重构后需要更新所有导入路径
2. 需要在根目录运行程序（或使用-m参数）
3. 测试文件需要更新导入路径
4. 批处理脚本需要更新相对路径
5. 文档中的路径引用需要更新

## 兼容性方案

为了保持向后兼容，可以在根目录创建入口文件：

### main.py（根目录）
```python
#!/usr/bin/env python3
"""
主入口文件 - 向后兼容
"""
from src.core.ip_tester_pro import main

if __name__ == '__main__':
    main()
```

这样用户仍然可以使用 `python main.py` 运行程序。
