from pathlib import Path
import sys,subprocess,shutil,os




"""
ltp cve测试在ltp测试的基础上运行,是ltp其中一个测试
"""

class Ltp_cve:
    def __init__(self, **kwargs):
        self.rpms = {'automake', 'pkgconf', 'autoconf', 'bison', 'flex', 'm4', 'kernel-headers', 'glibc-headers',
                     'findutils', 'libtirpc', 'libtirpc-devel', 'pkg-config'}
        self.path = Path('/root/osmts_tmp/ltp')
        self.directory: Path = kwargs.get('saved_directory') / 'ltp_cve'
        self.results_dir = Path('/opt/ltp/results')
        self.output_dir = Path('/opt/ltp/output')


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True, parents=True)
        if not Path('/opt/ltp/finish.sign').exists():
            if self.path.exists():
                shutil.rmtree(self.path)

            git_clone = subprocess.run(
                "cd /root/osmts_tmp/ && git clone https://gitcode.com/gh_mirrors/ltp/ltp.git",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if git_clone.returncode != 0:
                print(f"ltp_cve测试出错.git clone拉取ltp源码失败:{git_clone.stderr.decode('utf-8')}")
                sys.exit(1)

            make = subprocess.run(
                "cd /root/osmts_tmp/ltp/ && make autotools && ./configure && make -j $(nproc) && make install",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if make.returncode != 0:
                print(f"ltp_cve测试出错.configure和make出错:报错信息:{make.stderr.decode('utf-8')}")
                sys.exit(1)
            Path('/opt/ltp/finish.sign').touch()
        else:
            if self.results_dir.exists():
                shutil.rmtree(self.results_dir)
                self.results_dir.mkdir()
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
                self.output_dir.mkdir()


    def run_test(self):
        runltp = subprocess.run(
            "cd /opt/ltp && ./runltp -f cve",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if runltp.returncode != 0:
            print(f"ltp_cve测试出错.runltp进程报错:报错信息:{runltp.stderr.decode('utf-8')}")
            print('这是正常现象,osmts继续运行')

        # 测试结果存储在/opt/ltp/results,测试日志保存在/opt/ltp/output
        for file in os.listdir(self.results_dir):
            if 'LTP' in file:
                shutil.copy(self.results_dir / file,self.directory)
                Path(self.results_dir / file).unlink()
        for file in os.listdir(self.output_dir):
            if 'LTP' in file:
                shutil.copy(self.output_dir / file,self.directory)
                Path(self.output_dir / file).unlink()



    def run(self):
        print("开始进行ltp_cve测试")
        self.pre_test()
        self.run_test()
        print("ltp_cve测试结束")