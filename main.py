#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主入口文件 - 向后兼容

这个文件提供了一个简单的入口点，用户可以直接运行：
    python main.py

而不需要使用模块语法：
    python -m src.core.ip_tester_pro
"""

from src.core.ip_tester_pro import main

if __name__ == '__main__':
    main()
