import shutil
import subprocess
import os
from pathlib import Path

from .errors import GitCloneError


class APISanityChecker:
    def __init__(self, **kwargs):
        self.rpms ={'ctags','gcc-c++'}
        self.believe_tmp: bool = kwargs.get('believe_tmp')
        self.abi_compliance_checker = Path('/root/osmts_tmp/abi-compliance-checker')
        self.api_sanity_checker = Path('/root/osmts_tmp/api-sanity-checker')
        self.directory: Path = kwargs.get('saved_directory') / 'api_sanity_checker'
        self.gcc_version = kwargs.get('gcc_version','auto')


    def pre_test(self):
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)
        if self.abi_compliance_checker.exists() and self.believe_tmp:
            pass
        else:
            shutil.rmtree(self.abi_compliance_checker,ignore_errors=True)
            try:
                subprocess.run(
                    "git clone https://gitcode.com/gh_mirrors/ab/abi-compliance-checker.git",
                    cwd="/root/osmts_tmp",
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise GitCloneError(e.returncode,'https://gitcode.com/gh_mirrors/ab/abi-compliance-checker.git',e.stderr.decode())


        if self.api_sanity_checker.exists() and self.believe_tmp:
            pass
        else:
            shutil.rmtree(self.api_sanity_checker,ignore_errors=True)
            try:
                subprocess.run(
                    "cd /root/osmts_tmp && git clone https://github.com/lvc/api-sanity-checker.git",
                    cwd="/root/osmts_tmp",
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise GitCloneError(e.returncode,'https://github.com/lvc/api-sanity-checker.git',e.stderr.decode())

        # 开始安装
        subprocess.run(
            f"cd /root/osmts_tmp/abi-compliance-checker && make install prefix=/usr",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            f"cd /root/osmts_tmp/api-sanity-checker && make install prefix=/usr",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        test = subprocess.run(
            "api-sanity-checker -test",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if test.returncode != 0:
            print(f"api-snity-checcker测试出错.api-sanity-checker -test验证命令失败,报错信息:{test.stderr.decode('utf-8')}")
            print('osmts继续运行')

        # 生成GCC_VERSION.xml
        lib = Path('/usr/lib/gcc/riscv64-openEuler-linux')
        if self.gcc_version == 'auto':
            try:
                self.version = os.listdir(lib)[0]
            except FileNotFoundError:
                print("/usr/lib/gcc/riscv64-openEuler-linux/目录下未找到gcc版本")
        else:
            if not (lib / self.gcc_version).exists():
                print(f"用户输入的gcc_version={self.gcc_version}无效,试图自动查找")
                try:
                    self.version = os.listdir(lib)[0]
                except FileNotFoundError:
                    print("/usr/lib/gcc/riscv64-openEuler-linux/目录下未找到gcc版本")

        with open(f"{self.directory}/GCC_VERSION.xml",'w') as file:
            file.writelines(['<version>\n',f'\t{self.version}\n','</version>\n'])
            file.writelines(['<headers>\n',f'\t{lib}/{self.version}/include\n','</headers>\n'])
            file.writelines(['<libs>\n',f'\t{lib}/{self.version}\n','</libs>'])


    def run_test(self):
        osmts_dir = os.getcwd()
        os.chdir(self.directory)
        checker = subprocess.run(
            f"api-sanity-checker -lib NAME -d GCC_VERSION.xml -gen -build -run",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if checker.returncode != 0:
            print(f"api-snity-checcker测试出错.测试命令运行失败,报错信息:{checker.stderr.decode('utf-8')}")
            return
        # test_results/NAME/12/test_results.html
        shutil.copy2(f"test_results/NAME/{self.version}/test_results.html",self.directory)
        os.chdir(osmts_dir)


    def run(self):
        print('开始进行API Sanity Checker测试')
        self.pre_test()
        self.run_test()
        print('API Sanity Checker测试结束')