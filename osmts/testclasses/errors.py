from pystemd.dbusexc import *
import inspect


class DefaultError(Exception):
    def __init__(self, message):
        super().__init__(message)


class GitCloneError(Exception):
    """
        在subprocess运行git clone时报错
    """
    def __init__(self, error_code,url,stderr):
        self.error_code = error_code
        self.url = url
        self.stderr = stderr
        super().__init__("failed to git clone " + self.url)


class CompileError(Exception):
    def __init__(self, error_code,compiler,stderr):
        """
            在使用某个编译器编译失败时报错
        """
        self.error_code = error_code
        self.compiler = compiler
        self.stderr = stderr
        super().__init__(stderr)


class RunError(Exception):
    """
        在run_test()方法里运行测试命令时报错
    """
    def __init__(self, error_code,stderr):
        self.error_code = error_code
        self.stderr = stderr
        super().__init__()


class SummaryError(Exception):
    """
        在把结果解析并保存为Excel时报错
    """
    def __init__(self, fileName):
        self.fileName = fileName
        super().__init__()


class DnfError(Exception):
    """
        使用dnf包管理器时发生错误
    """
    def __init__(self, error_code,stderr):
        self.error_code = error_code
        self.stderr = stderr