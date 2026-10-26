from pathlib import Path
import os,subprocess,shutil,json
from openpyxl import Workbook
from .errors import GitCloneError, DefaultError, RunError
from .utils import decode_output




"""
ltp cve测试在ltp测试的基础上运行,是ltp其中一个测试
"""

class Ltp_cve:
    def __init__(self, **kwargs):
        self.rpms = {'automake', 'pkgconf', 'autoconf', 'bison', 'flex', 'm4', 'kernel-headers', 'glibc-headers',
                     'findutils', 'libtirpc', 'libtirpc-devel', 'pkg-config'}
        self.path = Path('/root/osmts_tmp/ltp')
        self.directory: Path = kwargs.get('saved_directory') / 'ltp_cve'


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True, parents=True)
        if not Path('/opt/ltp/finish.sign').exists():
            if self.path.exists():
                shutil.rmtree(self.path)

            # GIT_TERMINAL_PROMPT=0 禁止git交互式询问账号密码,否则会卡死在输入提示
            clone_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            try:
                git_clone = subprocess.run(
                    # --recurse-submodules 检出 tools/kirk 子模块,make install 会安装 kirk
                    ["git", "clone", "--recurse-submodules", "https://github.com/linux-test-project/ltp.git"],
                    cwd="/root/osmts_tmp",
                    env=clone_env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                print("ltp_cve测试出错.git clone超时(网络不稳定)")
                raise GitCloneError(1, 'https://github.com/linux-test-project/ltp.git', b'git clone timeout')
            if git_clone.returncode != 0:
                print(f"ltp_cve测试出错.git clone拉取ltp源码失败:{decode_output(git_clone.stderr)}")
                raise GitCloneError(git_clone.returncode, 'https://github.com/linux-test-project/ltp.git', git_clone.stderr)

            make = subprocess.run(
                "cd /root/osmts_tmp/ltp/ && make autotools && ./configure && make -j $(nproc) && make install",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if make.returncode != 0:
                # 不能用 sys.exit:SystemExit 不被 main.py 捕获,会终止整个osmts运行
                raise DefaultError(
                    f"ltp_cve测试出错.configure和make出错,返回值:{make.returncode}."
                    f"报错信息:{decode_output(make.stderr)}"
                )
            Path('/opt/ltp/finish.sign').touch()


    def run_test(self):
        report = Path('/opt/ltp/kirk-report-cve.json')
        if report.exists():
            report.unlink()  # kirk 要求 --json-report 目标文件不存在

        kirk = subprocess.run(
            f"/opt/ltp/kirk --run-suite cve --json-report {report}",
            cwd="/opt/ltp",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if kirk.returncode != 0:
            print(f"ltp_cve测试出错.kirk进程报错:报错信息:{decode_output(kirk.stderr)}")
            print('这是正常现象,osmts继续运行')

        # kirk 非0退出时可能根本没生成报告,先判存在性,
        # 否则 open() 抛 FileNotFoundError 掩盖真实原因
        if not report.exists():
            raise RunError(
                kirk.returncode,
                f"kirk未生成测试报告:{report},无法解析结果.报错信息:{decode_output(kirk.stderr)}",
            )

        self._parse_and_generate_excel(report)
        shutil.copy(report, self.directory)

    # 解析 kirk JSON 报告，提取测试统计和各用例结果，写入 Excel
    def _parse_and_generate_excel(self, report_path: Path):
        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        results = []
        for item in data['results']:
            status = item['status'].upper()
            if status in ('PASS', 'FAIL', 'CONF', 'BROK'):
                results.append((item['test_fqn'], status, int(item['test']['retval'][0])))

        stats = data['stats']
        env = data['environment']

        wb = Workbook()
        ws = wb.active
        ws.title = 'LTP_CVE'
        ws.append(['Testcase', 'Result', 'Exit Value'])
        for testcase, result, exit_val in results:
            ws.append([testcase, result, exit_val])

        ws.append([])
        ws.append(['统计信息'])
        ws.append(['总测试数', stats['passed'] + stats['failed'] + stats['broken'] + stats['skipped']])
        ws.append(['跳过数', stats['skipped']])
        ws.append(['失败数', stats['failed'] + stats['broken']])
        ws.append(['通过数', stats['passed']])
        ws.append([])
        ws.append(['环境信息'])
        ws.append(['内核版本', env['kernel']])
        ws.append(['架构', env['arch']])

        wb.save(self.directory / 'ltp_cve.xlsx')



    def run(self):
        print("开始进行ltp_cve测试")
        self.pre_test()
        self.run_test()
        print("ltp_cve测试结束")