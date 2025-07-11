# osmts means "One-stop management of test scripts".

osmts 是一个一站式管理和运行测试脚本并完成总结数据的工具。为基于 rpm 包管理器的 linux 发行版设计，一般用于 openEuler 新镜像的测试。

testclasses 目录用于存放测试类,用于描述测试脚本执行过程以及数据分析与总结。



## 如何使用？

* 获取osmts

```
git clone https://github.com/openeuler-riscv/automated-test-tools.git
cd automated-test-tools/osmts
```

* 运行前安装环境

```
bash dep_install.sh
```

* 运行脚本

```commandline
tmux new-session -s "osmts"
# main.py应当直接以root身份运行
chmod +x main.py
./main.py
```

在运行脚本时可以使用--config或者-c选项指定配置文件的位置（默认是osmts_config.toml）.

比如：

```Python
./main.py --config your_config.toml

# 或者
./main.py -c your_config.toml

# 也可以不配置,用默认的文件名
./main.py
```



* toml文件配置

```
run_tests = ['netperf','unixbench','nmap','stream']
saved_directory = "/root/osmts_result"
compiler = "gcc"
netperf_server_ip = "127.0.0.1"
netperf_server_password = "openEuler12#$"
sha256sumISO=""
csmith_count = 1000
yarpgen_count = 100
gcc_version="auto"
believe_tmp = 0
```

1. run_tests是一个列表，里面是需要测试的项目;
2. run_tests里的值可以是开发进度里的任意个项目,如果出现'performance-test'则自动添加"fio", "stream", "iozone", "unixbench", "libmicro", "nmap", "lmbench", "netperf";
3. 如果run_tests=["ALL"],则添加所有测试项目进去;
3. saved_directory填写测试结果存放的目录，main.py运行结束后会在这个目录产生excel文件，默认为'/root/osmts_result';
4. compiler是待测试的编译环境，应当填写gcc或者clang ,默认是gcc;
5. netperf_server_ip是netserver运行的机器的ip地址，如果不测试netperf则无需填写，netserver机器可以是自己，这时候就填写127.0.0.1;指定机器上提前运行netserver -p 10000;如果指定了netperf_server_password则会尝试打开对方机器上的netserver;
6. sha256sumISO是ISO镜像哈希校验的ISO下载地址
6. csmith_count是csmith测试生成和编译随机c文件的数量,取值范围[100,5000],默认为1000;
7. yarpgen_count是yarpgen测试生成随机c++文件的数量,取值范围[10,1000],默认为100;
8. gcc_version是api_sanity_checker测试需要用到的当前系统安装的gcc的版本,可以查看/usr/lib/gcc/riscv64-openEuler-linux/目录下的子目录,是一个数字比如12,如果不想指定可以填入auto让osmts自动查询;
9. believe_tmp=1表示尽可能使用本地已下载好的资源而不是从远程获取,调试用.



有的测试项目会运行很长一段时间，把main.py一直挂着就好，推荐在screen/tmux这样的终端复用器里运行，防止意外终止运行。

---

## 开发进度

| 编号 | 项目                 | 支持程度 |
|----|--------------------|------|
| 1  | unixbench          | 完成   |
| 2  | nmap               | 完成   |
| 3  | lmbench            | 完成   |
| 4  | stream             | 完成   |
| 5  | ltp_stress         | 完成   |
| 6  | iozone             | 完成   |
| 7  | libmicro           | 完成   |
| 8  | wrk                | 完成   |
| 9  | fio                | 完成   |
| 10 | netperf            | 完成   |
| 11 | trinity            | 完成   |
| 12 | ltp                | 完成   |
| 13 | ltp_cve            | 完成   |
| 14 | ltp_posix          | 完成   |
| 15 | gpgcheck           | 完成   |
| 16 | dejagnu            | 完成   |
| 17 | yarpgen            | 完成   |
| 18 | llvmcase           | 完成   |
| 19 | anghabench         | 完成   |
| 20 | csmith             | 完成   |
| 21 | jotai              | 完成   |
| 22 | jtreg              | 完成   |
| 23 | openscap           | 完成   |
| 24 | secureguardian     | 完成   |
| 25 | mmtests            | 完成   |
| 26 | api-sanity-checker | 完成   |
| 27 | ycsb               | 完成   |
| 28 | redis_benchmark    | 完成   |
| 29 | sysbench           | 完成   |
| 30 | benchmarksql       | 完成   |
| 31 | tpch               | 完成   |
| 32 | sha256sum          | 完成   |


## 注意事项
1. 进行ltp测试期间机器可能会ssh连不上,在sg2042上这很正常,机器并没有崩溃,耐心等待几天不要重启机器,否则丢失运行结果.如果对机器状态有疑惑可以连上串口查看是否kernel panic.
2. ltp_cve实际上已经被包含在了ltp里,在ltp存在的情况下可以不测试ltp_cve.
3. ltp_stress测试执行时接收SIGINT会清理子进程.
4. 若待测机器的/分区剩余容量过小,osmts会报错,避免因fio下载文件导致文件系统崩溃.
5. gpgcheck测试中会下载大量的rpm包,为加快速度,需要修改/etc/dnf/dnf.conf,添加一行max_parallel_downloads=20,并行下载rpm包,但这个数字不要太大否则会报Error: Bad value of LRO_MAXPARALLELDOWNLOADS
错误;
6. 部分测试用到了asyncio协程,从目前的结果来看不建议使用uvloop调度器;
7. 如果进行mysql或postresql数据库的测试,把数据库的登陆密码设置为无密码或者123456,osmts运行后数据库密码会设置为123456;
8. osmts使用时必须带有dbus,Python版本应为3.9以上,机器在测试期间不要作其他用途.

---
## 未来计划
1. 开发更多测试脚本进行汇总;
2. 对已有的测试结果进行审查看是否有数据遗漏;
3. osmts项目在sg2042 Milk-V Pioneer和Sipeed Lichee pi 4A开发板上检测通过,在其他设备上待测试.


---
## 展示图片
netperf测试类的输出结果如图所示:
![netperf总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/netperf_excel.png)

fio测试类的输出结果如图所示:
![fio总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/fio_excel.png)

lmbench测试类的输出结果如图所示:
![netperf总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/lmbench_excel.png)

unixbench测试类的输出结果如图所示:
![unixbench总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/unixbench_excel.png)

ltp_stress测试类的输出结果如图所示:
![ltp_stress总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/ltp_stress_excel.png)
_可以对excel文件中Result列进行筛选获取到其中FAIL的项目_

![ltp_stress_iodata总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/ltp_stress_iodata.png)

AnghaBench测试类的输出结果如图所示:
![AnghaBench总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/anghabench_excel.png)

jotai测试类的输出结果如图所示:
![jotai总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/jotai_excel.png)

yarpgen测试类的输出结果如图所示:
![yarpgen总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/yarpgen_excel.png)

secureguardian测试类的输出结果如图所示:
![secureguardian总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/secureguardian_excel.png)

wrk测试类的输出结果如图所示:
![wrk总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/wrk_excel.png)

mmtests测试类的输出结果如图所示:
![mmtests总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/mmtests_excel.png)

ycsb测试类的输出结果如图所示:
![ycsb总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/ycsb_excel.png)

redis_benchmark测试类的输出结果如图所示:
![redis_benchmark总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/redis_benchmark_excel.png)

sysbench测试类的输出结果如图所示:
![sysbench总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/sysbench_excel.png)

tpch测试类的输出结果如图所示:



![tpch总结为excel的截图](https://gitee.com/April_Zhao/images/raw/master/osmts/tpch_excel.png)

---

osmts项目可以托管更多的测试项目,接入后可以一键批量运行测试,如果有需要可以[给本项目提交issue](https://github.com/openeuler-riscv/automated-test-tools/issues),或者参考testclasses目录里的测试类自建 <测试名.py>文件