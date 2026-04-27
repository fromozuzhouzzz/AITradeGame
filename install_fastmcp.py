#!/usr/bin/env python3
"""
安装 fastmcp 包
"""

import subprocess
import sys

print("正在安装 fastmcp...")
result = subprocess.run([sys.executable, "-m", "pip", "install", "fastmcp"], 
                       capture_output=True, text=True)

print("STDOUT:")
print(result.stdout)

print("\nSTDERR:")
print(result.stderr)

print(f"\n返回码: {result.returncode}")

if result.returncode == 0:
    print("\n✅ fastmcp 安装成功!")
    
    # 验证安装
    try:
        import fastmcp
        print(f"✅ fastmcp 版本: {fastmcp.__version__}")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
else:
    print("\n❌ fastmcp 安装失败!")

