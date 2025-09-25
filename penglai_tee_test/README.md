# penglai_tee_test

根据 [Penglai_TEE测试指导](https://github.com/openeuler-riscv/oerv-qa/blob/main/docs/Penglai_Tee/Penglai_TEE%E6%B5%8B%E8%AF%95%E6%8C%87%E5%AF%BC.md) 编写的Penglai TEE 自动化测试脚本，用于测试 penglai demo 的编译和运行（不含 evm）

### 使用方法

使用 start_vm_penglai.sh 启动虚拟机，如 [24.03 SP2](https://dl-cdn.openeuler.openatom.cn/openEuler-24.03-LTS-SP2/virtual_machine_img/riscv64/start_vm_penglai.sh)

进入虚拟机后，执行目录下的 penglai_tee_test.sh 脚本

```
git clone https://github.com/openeuler-riscv/automated-test-tools.git
cd automated-test-tools/penglai_tee_test
bash penglai_tee_test.sh
```

### 查看测试结果

1. 可以根据脚本输出判断测试是否通过，如下

```
aes/aes 测试开始
host:1: enclave attest
host:1: enclave run
aes/aes 测试通过
...
seal_data/seal_data 测试开始
host:1: enclave attest
host:1: enclave run
seal_data/seal_data 测试通过
所有测试通过
```

2. 也可以通过当前目录下的  penglai_tee_test_result.txt 文件查看各个 demo 的测试结果

```
pass: aes/aes
pass: count/count
pass: crypt/crypt
pass: gm_test_enclaves/test_random
pass: gm_test_enclaves/test_sm2
pass: gm_test_enclaves/test_sm4_cbc
pass: gm_test_enclaves/test_sm4_ocb
pass: mem/mem
pass: prime/prime
pass: seal_data/seal_data
```