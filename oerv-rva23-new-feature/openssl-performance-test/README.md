### 1. 脚本功能

执行 openssl Backport 上游优化特性测试

### 2. 使用方法

执行 openssl.sh 执行 openssl speed 性能测试

该脚本会调用 compare_result.py 脚本来比较 Backport 后有无 Zbb 的测试结果，最后生成 markdown 格式表格

### 3. 注意事项

因为是性能测试，且在 openEuler RISC-V 24.03 SP3 LTS 版本及后续版本才有该特性，所以该脚本需要在安装有 openEuler RISC-V 24.03 SP3 LTS 版本及后续版本镜像的物理机中执行。