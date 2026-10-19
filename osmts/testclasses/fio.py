from pathlib import Path
import subprocess,re,shutil,hashlib
from openpyxl.workbook import Workbook
from pySmartDL import SmartDL
from tqdm import tqdm
import re
import sys
from collections import OrderedDict

from .errors import DefaultError
from .utils import decode_output


def sha256_of_file(file_path:Path, chunk_size:int = 1024 * 1024) -> str:
    """独立计算文件sha256,不依赖SmartDL的内部状态。"""
    digest = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(chunk_size), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Fio:
    # ISO文件名与sha256:原先在 __init__ 与 run_test 里各硬编码一次,容易改漏
    ISO_FILENAME = 'openEuler-24.03-LLVM-riscv64-dvd.iso'
    ISO_SHA256 = '74e9ac072b6b72744f21fec030fbe67ea331047ae44b26277f9d5ef41ab6776d'
    # 下载目录(类属性,便于测试重定向;实机为 /root/osmts_tmp/fio)
    path = Path('/root/osmts_tmp/fio')

    def __init__(self, **kwargs):
        self.rpms = {'fio'}
        self.path = Path(type(self).path)
        self.directory: Path = kwargs.get('saved_directory') / 'fio'
        self.test_result:str = ''

        # SmartDL 不会创建目标目录:board上首次运行时目录不存在,下载会直接失败
        self.path.mkdir(parents=True, exist_ok=True)

        self.download_iso_file:SmartDL = SmartDL(
            urls = [
                "https://fast-mirror.isrc.ac.cn/openeuler/openEuler-preview/openEuler-24.03-LLVM-Preview/ISO/riscv64/openEuler-24.03-LLVM-riscv64-dvd.iso", # 下载速度最快
                "https://repo.openeuler.openatom.cn/openEuler-preview/openEuler-24.03-LLVM-Preview/ISO/riscv64/openEuler-24.03-LLVM-riscv64-dvd.iso",       # 下载速度慢
                "https://repo.openeuler.org/openEuler-preview/openEuler-24.03-LLVM-Preview/ISO/riscv64/openEuler-24.03-LLVM-riscv64-dvd.iso",               # 有时候无法访问
                "https://mirrors.ustc.edu.cn/openeuler/openEuler-preview/openEuler-24.03-LLVM-Preview/ISO/riscv64/openEuler-24.03-LLVM-riscv64-dvd.iso",    # USTC repo
            ],
            dest = str(self.path / self.ISO_FILENAME),
            threads = 16,
            progress_bar = False,
            timeout = 10,
            request_args = {
                "headers" : {
                'Connection': 'keep-alive',
                # User-Agent会自动生成
                'Referer': 'https://gitee.com/zhtianyu/osmts'
                }
            }
        )
        # 如果iso文件已经存在则不重复下载(用哈希值校验文件)
        self.download_iso_file.add_hash_verification(algorithm='sha256',hash=self.ISO_SHA256)
        # 记下启动前的报错数量,便于下载后区分"本次新增的报错"
        self._errors_before_start = list(self.download_iso_file.get_errors())
        self.download_iso_file.start(blocking=False)
    def parse_fio_log(self, log_path):
        """解析fio日志文件，返回格式化数据字典"""
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 区分每个测试块，形如: read-4k:, randrw-256k:
        blocks = re.split(r'(?m)^\s*([^\s]+-[0-9]+k):', content)
        # split返回形如 ['', blockname1, block1_text, blockname2, block2_text, ...]
        entry_map = {}

        for i in range(1, len(blocks), 2):
            test_case = blocks[i]
            block_text = blocks[i + 1]
            if test_case not in entry_map:
                entry_map[test_case] = {}

            # 匹配 read 或 write 段
            rw_sections = re.findall(r"((read|write):.*?)(?=read:|write:|$)", block_text, flags=re.DOTALL)
            for section_text, rw_type in rw_sections:
                lat_match = re.search(r"^ *lat \((usec|msec)\):.*?avg=([\d\.]+)", section_text, flags=re.MULTILINE)
                bw_match = re.search(r"^ *bw\s*\(\s*(KiB|MiB)/s\s*\):.*?avg=([\d\.]+)", section_text, flags=re.MULTILINE)
                iops_match = re.search(r"^ *iops\s*:\s*.*?avg=([\d\.]+)", section_text, flags=re.MULTILINE)

                if lat_match and bw_match and iops_match:
                    bw_val = float(bw_match.group(2))
                    if bw_match.group(1) == "MiB":
                        bw_val *= 1024  # 转成 KiB/s

                    entry_map[test_case][rw_type] = {
                        "lat_unit": lat_match.group(1),
                        "lat_avg": float(lat_match.group(2)),
                        "bw_avg_KiBps": bw_val,
                        "iops_avg": float(iops_match.group(1))
                    }

        # 组织数据为 { rw_mode: { metric: { bs: value } } }
        data_structured = {}
        for test_case, ops in entry_map.items():
            parts = test_case.split('-')
            if len(parts) != 2:
                continue
            rw_mode = parts[0]
            bs = int(parts[1].replace('k', ''))

            for op_type, metrics in ops.items():
                key = f"{rw_mode}" if op_type == 'read' else f"{rw_mode}-write"
                if key not in data_structured:
                    data_structured[key] = {"IOPS": {}, "bw(KiB/s)": {}, "lat(usec)": {}, "lat(msec)": {}}

                data_structured[key]["IOPS"][bs] = metrics["iops_avg"]
                data_structured[key]["bw(KiB/s)"][bs] = metrics["bw_avg_KiBps"]
                lat_field = f"lat({metrics['lat_unit']})"
                data_structured[key].setdefault(lat_field, {})
                data_structured[key][lat_field][bs] = metrics["lat_avg"]

        return data_structured


    def save_to_excel(self, data_structured, output_dir):
        """将解析结果保存到Excel文件，格式化输出为你需要的样式"""
        output_path = Path(output_dir)
        wb = Workbook()
        ws = wb.active
        ws.title = "fio_summary"

        for rw_mode, metrics in data_structured.items():
            for metric, bs_values in metrics.items():
                # 写标题行，比如: read  IOPS
                ws.append([rw_mode, metric])
                for bs in sorted(bs_values.keys()):
                    ws.append(["", bs, bs_values[bs]])
                ws.append([])  # 空行分隔区块

        excel_file = output_path / "fio.xlsx"
        wb.save(excel_file)
        return excel_file

    # 确认ISO已下载且通过哈希校验,否则后续48轮fio跑的是无效文件
    def _validate_iso_download(self):
        errors = list(self.download_iso_file.get_errors())
        new_errors = errors[len(self._errors_before_start):]
        if new_errors:
            details = '; '.join(f"{type(e).__name__}: {e}" for e in new_errors)
            return False, f"下载报错:{details}"

        # SmartDL 的 isSuccessful() 覆盖哈希校验失败/镜像全挂/本地IO错误
        if not self.download_iso_file.isSuccessful():
            return False, "镜像均不可用或sha256校验失败(参见上方SmartDL日志)"

        iso_path = Path(self.download_iso_file.get_dest())
        if not iso_path.exists():
            return False, f"下载后未找到ISO文件:{iso_path}"

        # 二次自校验:不依赖SmartDL内部状态,独立确认文件哈希
        actual_hash = sha256_of_file(iso_path)
        if actual_hash.lower() != self.ISO_SHA256.lower():
            return False, (f"ISO哈希不匹配:期望{self.ISO_SHA256},实际{actual_hash}."
                           f"文件可能已损坏或被镜像替换")

        size_gb = iso_path.stat().st_size / 1024 / 1024 / 1024
        print(f"ISO校验通过({iso_path},{size_gb:.2f}GB),开始fio测试")
        return True, ''


    def run_test(self):
        # 结果目录必须提前创建:否则中途失败时fio.log无处落盘,现场丢失
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)

        if self.download_iso_file is not None:
            self.download_iso_file.wait()
            ok, reason = self._validate_iso_download()
            if not ok:
                raise DefaultError(f"fio测试出错.测试用ISO不可用,已跳过fio测试.原因:{reason}")

        filename = str(self.path / self.ISO_FILENAME)
        numjobs = 10
        iodepth = 10
        pbar = tqdm(total=48,desc="fio运行进度")
        for rw in ("read","write","rw","randread","randwrite","randrw"):
            for bs in (4,16,32,64,128,256,512,1024):
                try:
                    if rw == "randrw" or rw == "rw":
                        fio = subprocess.run(
                            f"fio -filename={filename} -direct=1 -iodepth {iodepth} -thread -rw={rw} -rwmixread=70 -ioengine=libaio -bs={bs}k -size=1G -numjobs={numjobs} -runtime=30 -group_reporting -name={rw}-{bs}k",
                            shell=True,check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                    else:
                        fio = subprocess.run(
                            f"fio -filename={filename} -direct=1 -iodepth {iodepth} -thread -rw={rw} -ioengine=libaio -bs={bs}k -size=1G -numjobs={numjobs} -runtime=30 -group_reporting -name={rw}-{bs}k",
                            shell=True,check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                except subprocess.CalledProcessError as e:
                    raise DefaultError(f"fio测试出错:fio进程运行报错,此时rw为{rw}.报错信息:{decode_output(e.stderr)}")

                # 保存fio命令的输出结果
                result = decode_output(fio.stdout)
                self.test_result += result + '\n'
                pbar.update(1)
        pbar.close()
        with open(self.directory / 'fio.log', 'w', encoding='utf-8') as file:
            file.write(self.test_result)
        parsed_data = self.parse_fio_log(self.directory / 'fio.log')
        self.save_to_excel(parsed_data, output_dir=self.directory)


    def run(self):
        print("开始进行fio测试")
        self.run_test()
        print("fio测试结束")