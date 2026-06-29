import re

def parse_openssl_speed(file_path):
    """解析 openssl speed 输出，返回字典 {(alg, size): throughput_k}"""
    result = {}
    size_order = [16, 64, 256, 1024, 8192, 16384]
    alg_set = {'md5', 'sha256', 'sha512'}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 7:
                    continue
                alg = parts[0].lower()
                if alg not in alg_set:
                    continue
                nums = []
                for p in parts[1:]:
                    if p.endswith('k'):
                        try:
                            nums.append(float(p[:-1]))
                        except ValueError:
                            break
                    else:
                        break
                if len(nums) == len(size_order):
                    for s, v in zip(size_order, nums):
                        result[(alg, s)] = v
                else:
                    print(f"[警告] 算法 {alg} 的数值数量不符，期望 {len(size_order)}，实际 {len(nums)}")
                    print(f"  行内容: {line}")
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        return {}
    except Exception as e:
        print(f"读取文件 {file_path} 时发生异常：{e}")
        return {}
    return result

# 解析两个文件
data_no_zbb = parse_openssl_speed("output.txt")
data_zbb = parse_openssl_speed("output_zbb.txt")

if not data_no_zbb or not data_zbb:
    print("解析失败，请检查文件内容是否包含算法速度行（如 'md5   3121.55k ...'）")
    print(f"data_no_zbb 条目数: {len(data_no_zbb)}")
    print(f"data_zbb 条目数: {len(data_zbb)}")
    exit(1)

# 生成 Markdown 表格
alg_order = ["md5", "sha256", "sha512"]
size_order = [16, 64, 256, 1024, 8192, 16384]
size_name = {16: "16 bytes", 64: "64 bytes", 256: "256 bytes",
             1024: "1024 bytes", 8192: "8192 bytes", 16384: "16384 bytes"}

# 修改表头：无Zbb在前，有Zbb在后
md_lines = [
    "| 指标大项 | 指标小项 | Backport后无Zbb | Backport后有Zbb | 性能提升占比 |",
    "| ---- | ---- | ---- | ---- | ---- |"
]

for alg in alg_order:
    for size in size_order:
        key = (alg, size)
        if key not in data_zbb or key not in data_no_zbb:
            print(f"警告：缺少 {alg} {size} bytes 的数据")
            continue
        val_zbb = data_zbb[key]
        val_nozbb = data_no_zbb[key]
        pct = (val_zbb - val_nozbb) / val_nozbb * 100
        # 先输出无Zbb，再输出有Zbb
        row = f"| {alg} | {size_name[size]} | {val_nozbb:.2f}k | {val_zbb:.2f}k | {pct:.1f}% |"
        md_lines.append(row)

full_md = "\n".join(md_lines)
print(full_md)

with open("openssl_compare.md", "w", encoding="utf-8") as f:
    f.write(full_md)
print("\n表格已保存至 openssl_compare.md")