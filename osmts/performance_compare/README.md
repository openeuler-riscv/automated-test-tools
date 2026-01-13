## performance-compare

OERV 多版本性能测试结果对比自动化脚本

### 获取性能测试结果

从发版测试结果中获取性能测试结果，[oerv-qa](https://github.com/openeuler-riscv/oerv-qa) 中的 testreport 下有各个版本的发版测试结果，其中 performance-test 为性能测试结果。
将需要对比的版本性能测试结果拷贝到当前目录下（其中会包含 sg2042 和 lpi4a 的测试结果），并将目录修改为版本号，例如：
```
╰─$ tree
.
├── 24.03SP2
│   ├── lpi4a
│   │   ├── fio
│   │   │   └── fio.xlsx
│   │   ├── iozone
│   │   │   └── iozone.xls
│   │   ├── lmbench
│   │   │   ├── lmbench.xlsx
│   │   ├── netperf
│   │   │   └── netperf.xlsx
│   │   ├── stream
│   │   │   └── stream.xlsx
│   │   └── unixbench
│   │       └── unixbench.xlsx
│   └── sg2042
│       ├── fio
│       │   ├── fio.xlsx
│       ├── iozone
│       │   └── iozone.xls
│       ├── lmbench
│       │   ├── lmbench.xlsx
│       ├── netperf
│       │   └── netperf.xlsx
│       ├── stream
│       │   └── stream.xlsx
│       └── unixbench
│           └── unixbench.xlsx
└── 25.03
│   ├── lpi4a
│   │   ├── fio
│   │   │   └── fio.xlsx
│   │   ├── iozone
│   │   │   └── iozone.xls
│   │   ├── lmbench
│   │   │   ├── lmbench.xlsx
│   │   ├── netperf
│   │   │   └── netperf.xlsx
│   │   ├── stream
│   │   │   └── stream.xlsx
│   │   └── unixbench
│   │       └── unixbench.xlsx
│   └── sg2042
│       ├── fio
│       │   ├── fio.xlsx
│       ├── iozone
│       │   └── iozone.xls
│       ├── lmbench
│       │   ├── lmbench.xlsx
│       ├── netperf
│       │   └── netperf.xlsx
│       ├── stream
│       │   └── stream.xlsx
│       └── unixbench
│           └── unixbench.xlsx
```

### config 文件简要说明

```
"versions": ["24.03SP2", "25.03"],
"devices": ["lpi4a", "sg2042"],
```
定义了需要比较的版本号以及两种设备类型

```
"test_tools": 
```
测试工具列表，每个测试工具下有文件名和需要对比的列信息

```
"unixbench": {
    "filename": "unixbench.xlsx",
```
定义了测试工具的 excel 文件名，脚本会读取该文件，并根据配置进行对比

```
"version_mark": {
    "ver1_text": "24.03SP2",
    "ver2_text": "25.03",
    "result_cells": ["C1", "E1"]
}
```
定义了两个版本号在 excel 中的标记，以及需要对比的列信息（注意： ver1_text 和 ver2_text 需要与 versions 列表中的顺序一致）

```
"test_type_project": [
    {
        "source_ranges": ["A1:B28"],
        "target_ranges": ["A2:B29"],
        "transpose": [False]
    },
    {
        "source_range": "B1:E1",
        "target_ranges": ["B2:B5", "B6:B9", "B10:B13", "B14:B17"],
        "transpose": [True, True, True, True]
    }
],
```

需要复制的 excel 区域，包括测试类型，测试项目等。可以一对一或一对多复制，并可以设置是否转置（一行转为一列）。

```
"result_data": {
    "ver1": {
        "source_ranges": ["B2:E2", "B3:E3", "B4:E4", "B5:E5"],
        "target_ranges": ["C2:C5", "C6:C9", "C10:C13", "C14:C17"],
        "transpose": [True, True, True, True]
    },
    "ver2": {
        "source_ranges": ["B2:E2", "B3:E3", "B4:E4", "B5:E5"],
        "target_ranges": ["D2:D5", "D6:D9", "D10:D13", "D14:D17"],
        "transpose": [True, True, True, True]
    }
},
```
定义了需要对比的 excel 数据信息，包括两个版本号的数据源和目标区域，并设置是否转置（一行转为一列）。

```
"diff_result": {
    "difference_title_cell": "E1",
    "difference_title_text": "Difference",
    "target_range": "E2:E17",
    "formula": "=( {ver2} - {ver1} ) / {ver1}"
}
```

定义了对比结果的标题单元格，目标区域和公式。其中的 formula 中的 {ver1} 和 {ver2} 会被替换为 result_data 中的两个版本号的对应的数据源，如上述例子中第一个替换为 (D2 - C2) / C2。

### 使用方法

安装依赖：

```
pip install pandas openpyxl xlrd
```

运行脚本：

```
python compare_perf.py
```

分别生成结果 `comparison_sg2042.xlsx` 与 `comparison_lpi4a.xlsx`，分别为两个版本 sg2042 和 lpi4a 的性能测试结果。
