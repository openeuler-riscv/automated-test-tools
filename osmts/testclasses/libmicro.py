from pathlib import Path
import subprocess,shutil

from .errors import GitCloneError,CompileError,RunError


class Libmicro:
    def __init__(self, **kwargs):
        self.rpms = set()
        self.believe_tmp: bool = kwargs.get('believe_tmp')
        self.path = Path('/root/osmts_tmp/libmicro')
        self.directory: Path = kwargs.get('saved_directory') / 'libmicro'
        self.compiler: str = kwargs.get('compiler')
        self.test_result = ''


    def pre_test(self):
        if self.path.exists() and self.believe_tmp:
            pass
        else:
            shutil.rmtree(self.path, ignore_errors=True)
            # 获取源码
            try:
                subprocess.run(
                    args="git clone https://gitee.com/April_Zhao/libmicro.git",
                    cwd="/root/osmts_tmp",
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                raise GitCloneError(e.returncode,'https://gitee.com/April_Zhao/libmicro.git',e.stderr.decode())


        # 开始编译
        try:
            if self.compiler == "gcc":
                subprocess.run(
                    args="make",
                    cwd=self.path,
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
            elif self.compiler == "clang":
                subprocess.run(
                    args='make CC=clang CFLAGS="-Wno-error=implicit-function-declaration"',
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
        except subprocess.CalledProcessError as e:
            raise CompileError(e.returncode,self.compiler,e.stderr.decode())


    def run_test(self):
        try:
            bench = subprocess.run(
                args="./bench",
                cwd=self.path,
                shell=True,check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise RunError(e.returncode,e.stderr.decode())
        else:
            self.test_result = bench.stdout.decode('utf-8')
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True,parents=True)
        with open(self.directory / 'libmicro.log','w') as file:
            file.write(self.test_result)


    def result2summary(self):
        pass


    def run(self):
        print("开始进行libmicro测试")
        self.pre_test()
        self.run_test()
        self.result2summary()
        print("libmicro测试结束")