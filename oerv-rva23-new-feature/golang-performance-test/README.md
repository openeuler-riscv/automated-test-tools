### 1. 脚本功能

执行 Golang Backport RVA23 Profile 特性性能测试

### 2. 使用方法

由于用于性能对比的程序要求 Golang 版本大于 1.25，openEuler 的 Golang 版本是 1.21.4 ，无法满足要求，所以需要在其他环境中安装。

该脚本的执行环境是 ubuntu，通过 ssh 远程在 openEuler 物理机中调用 golang.sh 脚本执行测试。执行方法在 ubuntu 中执行以下命令

````
$ bash run.sh
````

测试结果会被存储在当前目录下 ./golang_results 中，测试结果分别为：bits-rva20.txt，bits-rva23.txt，math-rva20.txt  math-rva23.txt

性能对比结果是：bits_comparison.txt，math_comparison.txt  