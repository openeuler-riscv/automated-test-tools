#!/bin/bash

# ========== 基本配置 ==========
PRIMARY_IP=${1:-"192.168.122.30"}
SECONDARY_IP=${2:-"192.168.122.28"}
USER="root"
PASSWD="openEuler12#$"
PORT=22
LOG_DIR="test_result_$(date +%Y%m%d_%H%M%S)"
REPO_FILE="openEuler-24.03-LTS-SP1_update_20250205.repo"
REMOTE_REPO_DIR="/etc/yum.repos.d"

mkdir -p "$LOG_DIR"

log() {
    echo -e "\033[1;34m[INFO] $1\033[0m" | tee -a "$LOG_DIR/main.log"
}

error() {
    echo -e "\033[1;31m[ERROR] $1\033[0m" | tee -a "$LOG_DIR/main.log"
}

extract_failures() {
    local logfile=$1
    local failfile=$2
    grep -iE "FAIL|error|not pass" "$logfile" > "$failfile" || true
    grep -E "A total of [0-9]+ use cases were excuted.*" "$logfile" > "${failfile%.log}_summary.log" || echo "No summary line found" > "${failfile%.log}_summary.log"
}

# summarize_all() {
#     log "生成汇总结果 summary_all.log"
#     echo "Test Summary - $(date)" > "$LOG_DIR/summary_all.log"
#     for summary in "$LOG_DIR"/*_summary.log; do
#         echo "--- ${summary##*/} ---" >> "$LOG_DIR/summary_all.log"
#         cat "$summary" >> "$LOG_DIR/summary_all.log"
#         echo "" >> "$LOG_DIR/summary_all.log"
#     done
# }

# ========== 推送 repo 文件 ==========
push_repo() {
    local ips=("$@")  # 接收所有 IP
    for ip in "${ips[@]}"; do
        log "[REPO] 正在配置 $ip 的 repo 源..."

        sshpass -p "$PASSWD" ssh -p "$PORT" "$USER@$ip" "
            if [ -f $REMOTE_REPO_DIR/openEuler.repo ]; then 
                cp $REMOTE_REPO_DIR/openEuler.repo $REMOTE_REPO_DIR/openEuler.repo.bak_\$(date +%s); 
            else
                rm -rf $REMOTE_REPO_DIR/*.repo; 
            fi
        "

        sshpass -p "$PASSWD" scp -P "$PORT" "$REPO_FILE" "$USER@$ip:$REMOTE_REPO_DIR/"
        log "[REPO] $ip repo 配置完成。"
    done
}


# ========== 安装并配置 mugen ==========
install_mugen() {
    local ip=$1
    shift
    local remote_ips=("$@")
    log "配置测试机：$ip"
    sshpass -p $PASSWD ssh -o StrictHostKeyChecking=no -p $PORT $USER@"$ip" "
  rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-openEuler &&
  rm -rf mugen &&
  dnf install -y git &&
  git clone https://gitee.com/openeuler/mugen.git &&
  cd mugen &&
  bash dep_install.sh &&
  bash mugen.sh -c --ip $ip --password $PASSWD --user $USER --port $PORT &&
  bash mugen.sh -c --ip $ip_remote --password $PASSWD --user $USER --port $PORT"
    for remote_ip in "${remote_ips[@]}"
    do
        log "配置远程测试机：$remote_ip"
        sshpass -p "$PASSWD" ssh -o StrictHostKeyChecking=no -p "$PORT" "$USER@$ip" "
            cd mugen &&
            bash mugen.sh -c --ip $remote_ip --password $PASSWD --user $USER --port $PORT
        "
    done
}

# ========== 执行用例 ==========
run_case() {
    local ip=$1
    local case_dir=$2
    local case_arg=$3
    local tag=$4
    local mode=${5:-"full"}

    log "[$tag] 在 $ip 上运行测试：$case_arg"
    if [ "$mode" = "full" ]; then
        sshpass -p $PASSWD ssh -tt -o LogLevel=ERROR -p $PORT $USER@"$ip" "cd mugen && stdbuf -oL -eL bash mugen.sh -f $case_dir -x" | tee "$LOG_DIR/${tag}_$ip.log"
    else
        sshpass -p $PASSWD ssh -tt -o LogLevel=ERROR -p $PORT $USER@"$ip" "cd mugen && stdbuf -oL -eL bash mugen.sh -f $case_dir -r $case_arg -x" | tee "$LOG_DIR/${tag}_$ip.log"
    fi

    extract_failures "$LOG_DIR/${tag}_$ip.log" "$LOG_DIR/fail_${tag}_$ip.log"
    sshpass -p $PASSWD scp -P $PORT -r $USER@"$ip":~/mugen/logs "$LOG_DIR/logs_${tag}_$ip"
    sshpass -p $PASSWD scp -P $PORT -r $USER@"$ip":~/mugen/results "$LOG_DIR/results_${tag}_$ip"
}

# ========== 清理日志文件 ==========
clear_logs() {
    log "清理 mugen 日志文件..."
    sshpass -p $PASSWD ssh -p $PORT $USER@"$PRIMARY_IP" "rm -rf ~/mugen/logs ~/mugen/results"
}

kernel_test() {
    local ip=$1
    log "[KERNEL] 在 $ip 安装并测试内核"
    sshpass -p $PASSWD ssh -p $PORT $USER@"$ip" "dnf install -y kernel && reboot"
    sleep 180
    run_case "$ip" "ltp" "ltp" "ltp" "full"
    clear_logs
}

smoke_test() {
    local ip=$1
    log "[SMOKE] 在 $ip 执行冒烟测试"
    sshpass -p $PASSWD ssh -p $PORT $USER@"$ip" "cd mugen && cp suite2cases/mugen_baseline_json/smoke-test/AT.json suite2cases/"
    run_case "$ip" "AT" "AT" "smoke" "full"
    clear_logs
}

cli_test() {
    local ip=$1
    log "执行命令参数测试..."
    sshpass -p $PASSWD ssh -p $PORT $USER@"$ip" <<'EOF'
cd mugen
dnf list --available --repo="openEuler-24.03-LTS-SP1_update_20250205_riscv64" | grep "arch\|riscv64" | awk '{print $1}' | awk -F. 'OFS="."{$NF="";print}' | awk '{print substr($0, 1, length($0)-1)}' > update_list
grep -Ev 'debuginfo|debugsource' ../update_list > update_list_filtered
dnf install -y $(cat update_list_filtered) --nobest --skip-broken
rm -rf cmd_pkg
while read pkg; do
    if rpm -ql "$pkg" | grep -E "^/usr/bin/|^/usr/sbin/" | grep -v ".sh" &>/dev/null; then
        echo "$pkg" >> cmd_pkg
    fi
done < update_list_filtered
rm -rf cmd_src
while read -r pkg; do
    if rpm -q "$pkg" &>/dev/null; then
        src_pkg=$(rpm -q --qf '%{SOURCERPM}\n' "$pkg" | sed 's/\.src\.rpm$//')
        clean_src_pkg=$(echo "$src_pkg" | sed -E 's/-[0-9]+(\.[0-9]+)*-[^-]+$//')
        if [[ -n "$clean_src_pkg" ]]; then
            echo "$clean_src_pkg" >> cmd_src
        else
            echo "Source package for $pkg not found!" >&2
        fi
    else
        echo "Package $pkg not installed!" >&2
    fi
done < cmd_pkg
sort -u -o cmd_src cmd_src
ls testcases/cli-test >./cli_list
cat cmd_src cli_list | sort | uniq -d > auto_cmd_src
cat >auto_run_mugen.sh <<SH
#!/bin/bash
while read pkg; do
    bash mugen.sh -f \$pkg -x
done < auto_cmd_src
SH
bash auto_run_mugen.sh
EOF
    sshpass -p $PASSWD scp -P $PORT -r $USER@"$ip":~/mugen/logs "$LOG_DIR/logs_${tag}_$ip"
    sshpass -p $PASSWD scp -P $PORT -r $USER@"$ip":~/mugen/results "$LOG_DIR/results_${tag}_$ip"
    clear_logs
}

docker_test() {
    local ip=$1
    log "执行 Docker 测试..."
    sshpass -p $PASSWD ssh -p $PORT $USER@"$ip" <<EOF
dnf remove -y podman*
dnf install -y docker wget
systemctl start docker
wget https://mirror.iscas.ac.cn/openeuler/openEuler-24.03-LTS-SP1/docker_img/riscv64/openEuler-docker.riscv64.tar.xz --no-check-certificate
docker load -i openEuler-docker.riscv64.tar.xz
img_name=\$(docker images --format "{{.Repository}}:{{.Tag}}" | head -n 1)
docker_name=openEuler_test
docker run -itd --name \${docker_name} --privileged -u root \${img_name} /bin/bash
docker exec \${docker_name} mv /etc/yum.repos.d/openEuler.repo /root
docker cp /etc/yum.repos.d/*.repo \${docker_name}:/etc/yum.repos.d
docker exec \${docker_name} dnf install -y sudo passwd systemd openssh git iproute bind-utils traceroute mtr wget setools-console selinux-policy selinux-policy-targeted openvswitch
docker exec \${docker_name} sed -i 's/SELINUX=enforcing/SELINUX=disabled/g' /etc/selinux/config
docker exec \${docker_name} bash -c "echo -e 'openEuler12#\nopenEuler12#' | passwd"
container_id=\$(docker ps -a | grep \${docker_name} | awk '{print \$1}')
container_path=\$(ls /var/lib/docker/containers | grep \${container_id})
docker stop \${docker_name}
systemctl stop docker
sed -i 's#/bin/bash#/sbin/init#g' /var/lib/docker/containers/\${container_path}/config.v2.json
systemctl start docker
docker start \${docker_name}
docker exec \${docker_name} bash -c "git clone https://gitee.com/openeuler/mugen.git /home/mugen"
docker exec \${docker_name} systemctl start sshd
docker exec \${docker_name} bash -c "cd /home/mugen && bash dep_install.sh && bash mugen.sh -c --ip 172.17.0.2 --password openEuler12# --user root"
docker exec \${docker_name} bash -c "cp /home/mugen/suite2cases/mugen_baseline_json/smoke-test/AT.json /home/mugen/suite2cases"
docker exec \${docker_name} bash -c "cd /home/mugen && bash mugen.sh -f AT -x" | tee /home/docker_mugen_run.log
EOF

    # 提取 docker 测试结果
    log "提取 Docker 测试结果..."

    sshpass -p $PASSWD ssh -p $PORT $USER@"$ip" <<EOF
docker_id=\$(docker ps -aqf name=openEuler_test)
docker cp \${docker_id}:/home/mugen/logs \$HOME/docker_logs
docker cp \${docker_id}:/home/mugen/results \$HOME/docker_results
EOF

    sshpass -p $PASSWD scp -P $PORT -r $USER@"$ip":docker_logs "$LOG_DIR/logs_docker_$ip"
    sshpass -p $PASSWD scp -P $PORT -r $USER@"$ip":docker_results "$LOG_DIR/results_docker_$ip"
    extract_failures "$LOG_DIR/docker_run_$ip.log" "$LOG_DIR/fail_docker_run_$ip.log"
}


# ========== 脚本主流程 ==========


# 检查 repo 文件
if [ ! -f "$REPO_FILE" ]; then
    error "未找到 repo 文件：$REPO_FILE"
    exit 1
fi

# 推送 repo 到两台机
push_repo "$PRIMARY_IP" "$SECONDARY_IP"

# 安装 mugen (remote ip 可以为多个)
install_mugen "$PRIMARY_IP" "$SECONDARY_IP"

# 软件包管理（双机）
log "执行软件包管理测试（双机）..."
run_case "$PRIMARY_IP" "pkgmanager-test" "oe_test_pkg_manager01" "pkgmgr01" "single"
sleep 60
push_repo "$PRIMARY_IP"
push_repo "$SECONDARY_IP"
run_case "$PRIMARY_IP" "pkgmanager-test" "oe_test_pkg_manager02" "pkgmgr02" "single"
sleep 60
push_repo "$PRIMARY_IP"
push_repo "$SECONDARY_IP"

# 执行测试
smoke_test "$PRIMARY_IP"
cli_test "$PRIMARY_IP"
kernel_test "$PRIMARY_IP" 
docker_test "$PRIMARY_IP"

# 启用 SELinux（仅主机）
log "检查并启用 SELinux..."
sshpass -p $PASSWD ssh -p $PORT $USER@"$PRIMARY_IP" <<'EOS'
status=$(sestatus | grep "SELinux status" | awk '{print $3}')
if [ "$status" != "enabled" ]; then
  echo "[SELinux] 正在启用..."
  sed -i 's/selinux=0//' /etc/default/grub
  grub2-mkconfig -o /boot/efi/EFI/openeuler/grub.cfg
  dnf install -y selinux-policy-targeted
  sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
  touch /.autorelabel
  reboot
fi
EOS
sleep 360

# 单包服务
log "执行服务测试..."
run_case "$PRIMARY_IP" "service-test" "service-test" "service" "full"

# 汇总统计
# summarize_all
log "所有测试完成，结果保存在：$LOG_DIR"
exit 0
