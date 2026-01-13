from pathlib import Path
import subprocess

from .errors import GitCloneError,DefaultError


"""
ltp posix测试在ltp源码的基础上单独编译运行
"""

class Ltp_posix(object):
    def __init__(self, **kwargs):
        self.rpms = {'automake', 'pkgconf', 'autoconf', 'bison', 'flex', 'm4', 'kernel-headers', 'glibc-headers',
                     'findutils', 'libtirpc', 'libtirpc-devel', 'pkg-config'}
        self.directory: Path = kwargs.get('saved_directory') / 'ltp_posix'
        self.test_result = ''
        self.test_passed = 0
        self.test_failed = 0
        self.test_skipped = 0
    
    
    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True,parents=True)
        if not Path('/opt/ltp').exists():
            try:
                subprocess.run(
                    "git clone https://gitee.com/zhtianyu/ltp.git",
                    cwd="/root/osmts_tmp/",
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise GitCloneError(e.returncode,'https://gitee.com/zhtianyu/ltp.git',e.stderr.decode())

        try:
            make = subprocess.run(
                f" ./configure && make all -j $(nproc)",
                cwd="/root/osmts_tmp/ltp/testcases/open_posix_testsuite",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"ltp_posix测试出错.configure和make all出错.报错信息:{e.decode('utf-8')}")


    def run_test(self):
        runltp = subprocess.run(
            "cd /root/osmts_tmp/ltp/testcases/open_posix_testsuite/bin && ./run-all-posix-option-group-tests.sh",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if runltp.returncode != 0:
            print(f"ltp_posix测试出错.run-all-posix-option-group-tests.sh脚本报错:报错信息:{runltp.stderr.decode('utf-8')}")


        self.test_result = runltp.stdout.decode('utf-8')
        with open(self.directory / 'ltp_posix.log', 'w') as file:
            file.write(self.test_result)
        for line in self.test_result.splitlines():
            if 'Test passed' in line or 'Test PASSED' in line:
                self.test_passed += 1
            elif 'Test FAILED' in line:
                self.test_failed += 1
            elif 'Test skipped' in line:
                self.test_skipped += 1
            print(f"通过数量:{self.test_passed}",f"失败数量:{self.test_failed}",f"跳过数量:{self.test_skipped}",sep='\n')


    def run(self):
        print("开始进行ltp_posix测试")
        self.pre_test()
        self.run_test()
        print("ltp_posix测试结束")