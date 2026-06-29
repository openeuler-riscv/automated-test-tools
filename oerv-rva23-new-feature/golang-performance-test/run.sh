#!/bin/bash
set -x
set -euo pipefail

REMOTE_USER="root"
REMOTE_HOST="localhost"
REMOTE_PORT="12055"
SSHPASS="openEuler12#\$"

REMOTE_SCRIPT="./golang.sh"
REMOTE_TEST_DIR="/root/golang_test"

LOCAL_RESULTS_DIR="./golang_results"
LOCAL_MATH_RESULTS_FILE="$LOCAL_RESULTS_DIR/math_comparison.txt"
LOCAL_BITS_RESULTS_FILE="$LOCAL_RESULTS_DIR/bits_comparison.txt"

command -v sshpass &>/dev/null || sudo apt install -y sshpass
command -v go &>/dev/null || sudo apt install -y golang-go
go version

go env -w GOSUMDB=sum.golang.google.cn
go env -w GOPROXY=mirrors.aliyun.com/goproxy/
go install golang.org/x/perf/cmd/benchstat@latest

sudo rm -rf "${LOCAL_RESULTS_DIR}" && sudo mkdir -p "${LOCAL_RESULTS_DIR}"
sudo chmod 755 "${LOCAL_RESULTS_DIR}"
sudo chown $USER:$USER "${LOCAL_RESULTS_DIR}"

echo ">>> 正在上传远程脚本 ..."
sshpass -p "$SSHPASS" ssh -p "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST" "rm -rf /root/golang.sh"
sshpass -p "$SSHPASS" scp -P "$REMOTE_PORT" "$REMOTE_SCRIPT" "$REMOTE_USER@$REMOTE_HOST:/root"

echo ">>> 正在远程执行测试脚本 ..."
sshpass -p "$SSHPASS" ssh -p "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST" \
    "bash /root/golang.sh '$REMOTE_TEST_DIR/math-rva20' '$REMOTE_TEST_DIR/math-rva23' '$REMOTE_TEST_DIR/bits-rva20' '$REMOTE_TEST_DIR/bits-rva23'"

echo ">>> 正在复制结果文件到本地 $LOCAL_RESULTS_DIR ..."
sshpass -p "$SSHPASS" scp -P "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEST_DIR/math-rva20/output.txt" "$LOCAL_RESULTS_DIR/math-rva20.txt"
sshpass -p "$SSHPASS" scp -P "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEST_DIR/math-rva23/output.txt" "$LOCAL_RESULTS_DIR/math-rva23.txt"
sshpass -p "$SSHPASS" scp -P "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEST_DIR/bits-rva20/output.txt" "$LOCAL_RESULTS_DIR/bits-rva20.txt"
sshpass -p "$SSHPASS" scp -P "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEST_DIR/bits-rva23/output.txt" "$LOCAL_RESULTS_DIR/bits-rva23.txt"

echo ">>> 生成 math 对比报告 ..."
~/go/bin/benchstat "$LOCAL_RESULTS_DIR/math-rva20.txt" "$LOCAL_RESULTS_DIR/math-rva23.txt" | tee "$LOCAL_MATH_RESULTS_FILE"

echo ">>> 生成 bits 对比报告 ..."
~/go/bin/benchstat "$LOCAL_RESULTS_DIR/bits-rva20.txt" "$LOCAL_RESULTS_DIR/bits-rva23.txt" | tee "$LOCAL_BITS_RESULTS_FILE"

echo ">>> 所有结果已保存在 $LOCAL_RESULTS_DIR"