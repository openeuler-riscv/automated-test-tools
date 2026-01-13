
#!/bin/bash
# 环境配置自动化脚本 (2025-07-02)

LOG_FILE="pre_install.log"
echo "=== 开始环境配置 $(date) ===" | tee -a $LOG_FILE

# 检查root权限
if [ "$(id -u)" -ne 0 ]; then
    echo "请使用root权限运行此脚本" | tee -a $LOG_FILE
    exit 1
fi

# 安装基础依赖
echo "正在安装系统依赖..." | tee -a $LOG_FILE
dnf install -y gcc g++ cmake python python3-devel python3-pip python3-Cython python3-xlrd python3-openpyxl \
    python3-psycopg2 python3-paramiko python3-numpy python3-pandas systemd-devel libxml2 libxslt \
    libxslt-devel libxml2-devel tmux automake autoconf ntp 2>&1 | tee -a $LOG_FILE

if [ ${PIPESTATUS} -ne 0 ]; then
    echo "系统依赖安装失败，请检查网络或软件源配置" | tee -a $LOG_FILE
    exit 1
fi

# 手动同步时间
echo "手动同步时间..." | tee -a $LOG_FILE
ntpdate cn.pool.ntp.org 2>&1 | tee -a $LOG_FILE

# 升级pip和setuptools
echo "升级Python工具链..." | tee -a $LOG_FILE
pip3 install --upgrade pip setuptools -i https://mirrors.aliyun.com/pypi/simple 2>&1 | tee -a $LOG_FILE

# 安装requirements.txt依赖
if [ -f "requirements.txt" ]; then
    echo "安装Python依赖包..." | tee -a $LOG_FILE
    pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple 2>&1 | tee -a $LOG_FILE
else
    echo "未找到requirements.txt文件" | tee -a $LOG_FILE
fi

echo "=== 环境配置完成 $(date) ===" | tee -a $LOG_FILE
