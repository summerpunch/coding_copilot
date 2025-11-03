#!/bin/bash
# 运行打包后的 CLI 程序
# 确保在项目根目录运行，这样可以访问项目文件

cd "$(dirname "$0")"
./dist/coding_copilot
