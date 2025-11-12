#!/bin/bash

# Function to handle script exit
function check_result {
    if [ $1 -ne 0 ]; then
        echo "退出脚本"
        exit 1
    fi
}

# build penglai-enclave-driver rpms
function install_driver_rpms {
    driver_version="1.0-1"
    pushd penglai-enclave-driver
    if [[ ! -f ./penglai-enclave-driver-"${driver_version}".riscv64.rpm ]]; then
        echo "正在编译 penglai-enclave-driver"
        dnf -y builddep penglai-enclave-driver.spec
        rpmbuild --define "_topdir %(pwd)" --define "_builddir %{_topdir}" --define "_rpmdir %{_topdir}" --define "_sourcedir %{_topdir}" --define "_srcrpmdir %{_topdir}" --define "_rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm" -ba *.spec
    fi
    yum install -y ./penglai-enclave-driver-"${driver_version}".riscv64.rpm
    check_result $?
    echo "安装 penglai-enclave-driver 完成"
    popd
}

# build penglai-enclave-sdk rpms
function install_sdk_rpms {
    sdk_version="1.0-1"
    pushd penglai-enclave-sdk
    if [[ ! -f ./penglai-enclave-sdk-"${sdk_version}".riscv64.rpm ]]; then
        echo "正在编译 penglai-enclave-sdk"
        dnf -y builddep penglai-enclave-sdk.spec
        rpmbuild --define "_topdir %(pwd)" --define "_builddir %{_topdir}" --define "_rpmdir %{_topdir}" --define "_sourcedir %{_topdir}" --define "_srcrpmdir %{_topdir}" --define "_rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm" -ba *.spec
    fi
    yum install -y ./penglai-enclave-sdk-"${sdk_version}".riscv64.rpm ./penglai-enclave-sdk-devel-"${sdk_version}".riscv64.rpm
    check_result $?
    echo "安装 penglai-enclave-sdk 完成"
    popd
}

# Install necessary packages
function install_dependencies {
    yum -y install rpm-build rpmdevtools git
    git submodule update --init
    install_driver_rpms
    install_sdk_rpms
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
        /opt/penglai/bin/penglai-host Penglai-demo/$demo | grep "host:1: enclave"
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
