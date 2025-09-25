#!/bin/bash

# Function to handle script exit
function check_result {
    if [ $1 -ne 0 ]; then
        echo "退出脚本"
        exit 1
    fi
}

# Install necessary packages
function install_dependencies {
    yum install -y penglai-enclave-driver penglai-enclave-sdk penglai-enclave-sdk-devel git make
    check_result $?
    echo "安装依赖完成"

}

# Load the penglai module
function check_module_insert {
    modprobe penglai
    check_result $?
    lsmod | grep penglai
    check_result $?
    echo "模块加载成功"
}

# Clone the repository and build
function build_demo {
    git clone https://github.com/Penglai-Enclave/Penglai-demo
    make -C Penglai-demo
    check_result $?
    echo "编译demo完成"
}

# Test various demo commands
function test_demo {
    demos=(
        "aes/aes"
        "count/count"
        "crypt/crypt"
        "gm_test_enclaves/test_random"
        "gm_test_enclaves/test_sm2"
        "gm_test_enclaves/test_sm4_cbc"
        "gm_test_enclaves/test_sm4_ocb"
        "mem/mem"
        "prime/prime"
        "seal_data/seal_data"
        # "deadloop/deadloop"
    )

    test -f penglai_tee_test_result.txt && rm -f penglai_tee_test_result.txt
    for demo in "${demos[@]}"; do
        echo "$demo 测试开始"
        /opt/penglai/bin/penglai-host Penglai-demo/$demo |grep "host:1: enclave"
        check_result $?
        echo "$demo 测试通过"
        echo "pass: $demo" >>penglai_tee_test_result.txt
    done
}

install_dependencies
check_module_insert
build_demo
test_demo
echo "所有测试通过"
