import os
import requests
import yaml
import json
import subprocess
from openpyxl import Workbook

# 1. 获取 mugen_list（即 mugen 中已适配的软件包列表）
def generate_mugen_list(output_file='mugen_list'):
    mugen_set = set()

    # 1. 从 mugen/suite2cases 下提取 json 文件名（去掉 .json）
    suite_dir = 'mugen/suite2cases'
    if os.path.isdir(suite_dir):
        for fname in os.listdir(suite_dir):
            if fname.endswith('.json'):
                mugen_set.add(fname[:-5])  # 去掉 .json

    # 2. 从 mugen/testcases/feature-test/epol 下提取目录名
    epol_dir = 'mugen/testcases/feature-test/epol'
    if os.path.isdir(epol_dir):
        for entry in os.listdir(epol_dir):
            full_path = os.path.join(epol_dir, entry)
            if os.path.isdir(full_path):
                mugen_set.add(entry)

    # 3. 从 os-basic.json 提取 name 字段第三段
    os_basic_json = os.path.join(suite_dir, 'os-basic.json')
    if os.path.isfile(os_basic_json):
        try:
            with open(os_basic_json, 'r') as f:
                data = json.load(f)
                for case in data.get('cases', []):
                    name = case.get('name', '')
                    parts = name.split('_')
                    if len(parts) >= 3:
                        mugen_set.add(parts[2])
        except Exception as e:
            print(f"[ERROR] 解析 os-basic.json 失败: {e}")

    # 写入文件
    with open(output_file, 'w') as f:
        for pkg in sorted(mugen_set):
            f.write(pkg + '\n')
    print(f"[INFO] 已生成 mugen_list，共 {len(mugen_set)} 个软件包")

    return mugen_set

# 2. 从 YAML URL 获取软件包名
def get_package_names_from_yaml(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = yaml.safe_load(response.text)
        return [pkg['name'] for pkg in data.get('packages', [])]
    except Exception as e:
        print(f"[ERROR] 读取 {url} 失败: {e}")
        return []

# 3. 检查软件包是否可安装
# def is_package_installable(pkg_name):
#     result = subprocess.run(
#         ['dnf', 'info', pkg_name],
#         stdout=subprocess.DEVNULL,
#         stderr=subprocess.DEVNULL
#     )
#     return result.returncode == 0

# 4. 主处理函数：整合并生成 Excel
def generate_excel_output(baseos_pkgs, epol_pkgs, everything_pkgs, mugen_set, output='pkg_status.xlsx'):
    wb = Workbook()
    ws = wb.active
    ws.append(['Source', 'Package', 'Mugen Adapted'])

    all_rows = []

    for origin, pkgs in [('baseos', baseos_pkgs), ('epol', epol_pkgs), ('everything', everything_pkgs)]:
        for pkg in sorted(pkgs):
            # if not is_package_installable(pkg):
            #     continue
            is_mugen = 'Y' if pkg in mugen_set else 'N'
            all_rows.append([origin, pkg, is_mugen])

    for row in all_rows:
        ws.append(row)

    wb.save(output)
    print(f"[INFO] 已生成 Excel 文件：{output}")

# ----------------- 主流程 -----------------
if __name__ == '__main__':
    # 生成 mugen_list
    mugen_set = generate_mugen_list()

    # YAML 链接
    baseos_yaml = 'https://gitee.com/openeuler/release-management/raw/master/openEuler-24.03-LTS-SP1/baseos/pckg-mgmt.yaml'
    epol_yaml = 'https://gitee.com/openeuler/release-management/raw/master/openEuler-24.03-LTS-SP1/epol/pckg-mgmt.yaml'
    everything_yaml = 'https://gitee.com/openeuler/release-management/raw/master/openEuler-24.03-LTS-SP1/everything-exclude-baseos/pckg-mgmt.yaml'

    # 提取 pkg_list
    baseos_pkgs = get_package_names_from_yaml(baseos_yaml)
    epol_pkgs = get_package_names_from_yaml(epol_yaml)
    everything_pkgs = get_package_names_from_yaml(everything_yaml)

    # 生成 Excel
    generate_excel_output(baseos_pkgs, epol_pkgs, everything_pkgs, mugen_set)
