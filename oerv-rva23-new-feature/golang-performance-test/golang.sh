#!/bin/bash
set -x
set -euo pipefail

# 安装 Go（若已安装可跳过，但保留）
if ! command -v go &>/dev/null; then
    dnf install -y golang
fi

# 接收四个目录参数
OUTPUT_MATH_RVA20="$1"   # 例如 /root/golang_test/math-rva20
OUTPUT_MATH_RVA23="$2"
OUTPUT_BITS_RVA20="$3"
OUTPUT_BITS_RVA23="$4"

# 创建四个目录
DIR_LIST=(
    "$OUTPUT_MATH_RVA20"
    "$OUTPUT_MATH_RVA23"
    "$OUTPUT_BITS_RVA20"
    "$OUTPUT_BITS_RVA23"
)
for target_dir in "${DIR_LIST[@]}"; do
    if [ -d "$target_dir" ]; then
        echo "目录 $target_dir 已存在，执行清理删除"
        rm -rf "$target_dir"
    fi
    mkdir -p "$target_dir"
done

# 定义输出文件名（均放在各自目录下）
MATH_RVA20_FILE="${OUTPUT_MATH_RVA20}/output.txt"
MATH_RVA23_FILE="${OUTPUT_MATH_RVA23}/output.txt"
BITS_RVA20_FILE="${OUTPUT_BITS_RVA20}/output.txt"
BITS_RVA23_FILE="${OUTPUT_BITS_RVA23}/output.txt"

# math 测试
GORISCV64=rva20u64 go test -bench=. math -count=8 -timeout=1200s 2>&1 | tee "$MATH_RVA20_FILE"
GORISCV64=rva23u64 go test -bench=. math -count=8 -timeout=1200s 2>&1 | tee "$MATH_RVA23_FILE"

# math/bits 测试
GORISCV64=rva20u64 go test -bench=. math/bits -count=8 -timeout=1200s 2>&1 | tee "$BITS_RVA20_FILE"
GORISCV64=rva23u64 go test -bench=. math/bits -count=8 -timeout=1200s 2>&1 | tee "$BITS_RVA23_FILE"
