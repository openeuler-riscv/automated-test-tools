## mugen-adapted-pkgs

统计 mugen 对于软件包功能的覆盖情况，当前脚本以 24.03SP1 为基准，统总共当前版本有多少软件包，mugen 目前有那些已适配了，有哪些没有适配。

### 获取系统版本中所有软件包

目前策略从 https://gitee.com/openeuler/release-management 仓库中获取。如 https://gitee.com/openeuler/release-management/raw/master/openEuler-24.03-LTS-SP1/baseos/pckg-mgmt.yaml 文件中获取 baseos 软件包列表。

### 获取 mugen 已适配的软件包

分别从 mugen/suite2cases 下提取 json 文件名，从 mugen/testcases/feature-test/epol 下提取包名，从 os-basic.json 提取包名。

### 使用方法

在当前目录下获取 mugen 仓库：

```
git clone https://gitee.com/openeuler/mugen.git
```

运行脚本：

```
python3 mugen-adapted-pkgs.py
```

生成结果 `pkg_status.xlsx`，其中包含所有软件包和 mugen 已适配情况。

### 结果分析

结果分为三列，'Source', 'Package', 'Mugen Adapted'，第一列 'Source' 将软件包按仓库分类出 baseos，epol，everything ，第二列 'Package' 列出软件包名，第三列 'Mugen Adapted' 标记该软件包是否在 mugen 已适配。