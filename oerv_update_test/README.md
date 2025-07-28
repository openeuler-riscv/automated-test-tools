## oerv-update-test

OERV update 版本测试自动化脚本

### 环境准备

#### 机器准备

准备 2-4 台 oerv 虚拟机（虚拟机数量取决于[单包命令参数覆盖](https://github.com/atzhtianyu/oerv-qa/blob/main/docs/update_test/oerv-update%E7%89%88%E6%9C%AC%E6%B5%8B%E8%AF%95%E6%8C%87%E5%AF%BC%E8%AF%B4%E6%98%8E%E6%96%87%E6%A1%A3.md#%E5%8D%95%E5%8C%85%E5%91%BD%E4%BB%A4%E5%8F%82%E6%95%B0%E8%A6%86%E7%9B%96epol-%E8%BD%AF%E4%BB%B6%E5%8C%85%E4%B8%8D%E8%BF%9B%E8%A1%8C%E6%B5%8B%E8%AF%95)部分需要对软件包 cli 测试的 mugen 测试用例，最少为 2 台），可参考 [mugen 使用说明](https://github.com/atzhtianyu/oerv-qa/blob/main/docs/mugen/Mugen%E6%B5%8B%E8%AF%95Lesson%20Learn.md) 进行必要的配置，如添加网卡，挂载磁盘等。

#### update repo 准备

在测试脚本同级目录下新建 .repo 文件，内容参考 [update repo 配置](./openEuler-24.03-LTS-SP1_update_20250205.repo)，注意替换其中的镜像源地址。

#### 安装依赖

在本机安装 sshpass，用于自动化脚本执行过程中 ssh 免密登录以及命令执行。

安装方式参考 [sshpass 安装](https://www.cyberciti.biz/faq/noninteractive-shell-script-ssh-password-provider/)

### 使用方法

```sh
PRIMARY_IP=${1:-"192.168.122.30"}
SECONDARY_IP=${2:-"192.168.122.28"}
USER="root"
PASSWD="openEuler12#$"
PORT=22
LOG_DIR="test_result_$(date +%Y%m%d_%H%M%S)"
REPO_FILE="openEuler-24.03-LTS-SP1_update_20250205.repo"
REMOTE_REPO_DIR="/etc/yum.repos.d"
```

- PRIMARY_IP：主测试虚拟机 IP
- SECONDARY_IP(REMOTE_IP)：从测试虚拟机 IP
- USER：登录用户名
- PASSWD：登录密码
- PORT：登录端口
- LOG_DIR：测试日志目录
- REPO_FILE：update repo 配置文件
- REMOTE_REPO_DIR：远程 repo 目录

需要修改的部分

cli_test 中的

```sh
dnf list --available --repo="openEuler-24.03-LTS-SP1_update_20250205_riscv64" | grep "arch\|riscv64" | awk '{print $1}' | awk -F. 'OFS="."{$NF="";print}' | awk '{print substr($0, 1, length($0)-1)}' > update_list
```
--repo 参数改为实际 update 的 repo id

docker_test 中的

```sh
wget https://mirror.iscas.ac.cn/openeuler/openEuler-24.03-LTS-SP1/docker_img/riscv64/openEuler-docker.riscv64.tar.xz --no-check-certificate
docker load -i openEuler-docker.riscv64.tar.xz
```

docker 镜像下载地址改为实际镜像源，docker load 镜像文件名改为实际下载的 docker 镜像文件。

修改完毕后，执行测试：

```sh
bash oerv_update_test.sh
```

