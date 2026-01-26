### 脚本作用：

根据指定的划分软件包等级的 excel 文件，给 mugen 测试结果为非 pass 的测试用例划分优先级

### 使用方法：

#### 1. 下载 mugen 

​     下载 mugen 到本地：git clone https://atomgit.com/openeuler/mugen.git ，因为脚本需要对测试用例内容进行匹配

#### 2. 配置文件 config.toml

配置 4 个需要用到的目录：

package_level_file：划分软件包等级的 excel 文件目录

mugen_testcases_file：测试结果为非 pass 的 mugen 测试用例 excel 文件

mugen_dir：下载到本地的 mugen 目录

output_file：生成最终 mugen 测试用例划分完优先级的 excel 文件的目录，如果不配置改参数，该文件默认存储在当前脚本所在目录中，文件名是 mugen_testcase_grades.xlsx

````
package_level_file = 'D:\\git\\github\\openeuler-riscv\\automated-test-tools\\assign-mugen-level\\oE2403SP3-packagelevel-20251202.xlsx'
mugen_testcases_file = 'D:\\git\\github\\openeuler-riscv\\automated-test-tools\\assign-mugen-level\\24.03sp3_rva20_mugen.xlsx'
mugen_dir = 'D:\\git\\atomgit\\mugen'
output_file = 'D:\\git\\github\\openeuler-riscv\\automated-test-tools\\assign-mugen-level\\mugen_testcase_grades.xlsx'
````

以上例子是在 windows 系统中的目录

#### 3. 执行脚本

执行 `python run.py`运行脚本，脚本执行完成后会在指定目录生成 mugen 测试用例划分完优先级的 excel 文件





