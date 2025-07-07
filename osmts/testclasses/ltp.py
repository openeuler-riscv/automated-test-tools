import os
from pathlib import Path
import subprocess,shutil
from openpyxl import Workbook

from .errors import GitCloneError,DefaultError

"""
文档:https://blog.sina.com.cn/s/blog_7695e9f40100yjme.html
"""



class Ltp:
    def __init__(self, **kwargs):
        self.rpms = {'automake','pkgconf','autoconf','bison','flex','m4','kernel-headers','glibc-headers','findutils','libtirpc','libtirpc-devel','pkg-config'}
        self.path = Path('/root/osmts_tmp/ltp')
        self.directory: Path = kwargs.get('saved_directory') / 'ltp'
        self.results_dir = Path('/opt/ltp/results')
        self.output_dir = Path('/opt/ltp/output')


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True, parents=True)
        if self.path.exists():
            shutil.rmtree(self.path)
        try:
            subprocess.run(
                "git clone https://gitcode.com/gh_mirrors/ltp/ltp.git",
                cwd = "/root/osmts_tmp",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise GitCloneError(e.returncode,'https://gitcode.com/gh_mirrors/ltp/ltp.git',e.stderr)

        try:
            subprocess.run(
                "make autotools && ./configure && make -j $(nproc) && make install",
                cwd = "/root/osmts_tmp/ltp/",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"ltp测试出错.configure和make出错:报错信息:{e.stderr.decode('utf-8')}")

        # 添加标记
        Path('/opt/ltp/finish.sign').touch()

        # 确保运行前/opt/ltp/results和/opt/ltp/output为空目录
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir)
            self.results_dir.mkdir()
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
            self.output_dir.mkdir()


    def run_test(self):
        runltp = subprocess.run(
            "./runltp",
            cwd="/opt/ltp",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if runltp.returncode != 0:
            print(f"ltp测试出错.runltp进程报错:报错信息:{runltp.stderr.decode('utf-8')}")
            print('这是正常现象,osmts继续运行')


        # 测试结果存储在/opt/ltp/results,测试日志保存在/opt/ltp/output
        wb = Workbook()
        ws = wb.active
        ws.title = 'ltp report'
        ws.append(['Testcase', 'Result', 'Exit Value'])
        # 对/opt/ltp/results目录里的日志进行分析
        for file in os.listdir(self.results_dir):
            if '.log' in file:
                with open(self.results_dir / file, 'r') as ltp_log:
                    testcases = sorted(set(line.strip() for line in ltp_log.readlines() if
                                           any(result in line for result in ('PASS', 'FAIL', 'CONF'))))
                    for testcase in testcases:
                        ws.append([item for item in testcase.split(' ') if item != ''])
                    wb.save(self.directory / 'ltp.xlsx')
            shutil.copy(self.results_dir / file,self.directory)
            Path(self.results_dir / file).unlink()

        # 复制/opt/ltp/output目录里的总结信息
        for file in os.listdir(self.output_dir):
            if 'LTP' in file:
                shutil.copy(self.output_dir / file,self.directory)
                Path(self.output_dir / file).unlink()


    def run(self):
        print("开始进行ltp测试")
        self.pre_test()
        self.run_test()
        print("ltp测试结束")