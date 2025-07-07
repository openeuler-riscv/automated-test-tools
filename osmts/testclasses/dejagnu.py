from pathlib import Path
import subprocess,shutil

from .errors import GitCloneError,RunError


class DejaGnu:
    def __init__(self, **kwargs):
        self.rpms = {'gcc-g++', 'gcc-gfortran', 'dejagnu'}
        self.path = Path('/root/osmts_tmp/dejagnu')
        self.directory: Path = kwargs.get('saved_directory') / 'dejagnu'
        self.testsuite = Path("/root/osmts_tmp/dejagnu/gcc/gcc/testsuite/")


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(parents=True,exist_ok=True)
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(parents=True)
        # 拉取源码
        try:
            subprocess.run(
                f"git clone https://gitee.com/openeuler/gcc.git",
                cwd=self.path,
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise GitCloneError(e.returncode,'https://gitee.com/openeuler/gcc.git',e.stderr.decode())


    def run_test(self):
        for tool, logname in [('gcc', 'gcc'), ('g++', 'g++'), ('gfortran', 'gfortran')]:
            result = subprocess.run(
                f"runtest --tool {tool}",
                cwd=self.testsuite,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stderr_output = result.stderr.decode('utf-8')
            stdout_output = result.stdout.decode('utf-8')

            # 如果退出码非 0 且不是可以忽略的警告
            if result.returncode != 0 and "Couldn't find the global config file." not in stderr_output:
                raise RunError(result.returncode, f"dejagnu测试出错.runtest --tool {tool} 命令运行失败,报错信息:\n{stderr_output}")

            # 打印剩余警告信息（可选）
            remaining_warnings = '\n'.join([
                line for line in stderr_output.splitlines()
                if "Couldn't find the global config file." not in line
            ])
            if remaining_warnings.strip():
                print(f"[{tool}] stderr 警告信息:\n{remaining_warnings}")

            # 拷贝日志文件
            log_file = self.testsuite / f"{logname}.log"
            sum_file = self.testsuite / f"{logname}.sum"
            if log_file.exists() and sum_file.exists():
                shutil.copy(log_file, self.directory)
                shutil.copy(sum_file, self.directory)
            else:
                print(f"[警告] 未生成 {logname}.log 或 {logname}.sum 文件，可能测试未运行")



    def run(self):
        print('开始进行dejagnu测试')
        self.pre_test()
        self.run_test()
        print('dejagnu测试结束')