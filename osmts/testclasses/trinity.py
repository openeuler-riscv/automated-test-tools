from pathlib import Path
import sys,subprocess,lzma

from .errors import DefaultError,GitCloneError


class Trinity:
    def __init__(self,**kwargs ):
        self.rpms = set()
        self.directory:Path = kwargs.get('saved_directory') / 'trinity'
        self.compiler:str = kwargs.get('compiler')
        self.test_result:str = ''


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True,parents=True)
        user_exist = subprocess.run(
            "id trinity_test",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        # trinity_test用户若不存在则创建一个
        if user_exist.returncode != 0:
            try:
                subprocess.run(
                    f"useradd trinity_test",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                raise DefaultError(f"trinity测试出错:无法创建临时测试用户trinity_test.报错信息:{e.stderr.decode('utf-8')}")

        else:
            del_add = subprocess.run(
                f"userdel trinity_test -r && useradd -m trinity_test",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            if del_add.returncode != 0:
                print(f"trinity测试出错:无法创建临时测试用户trinity_test.报错信息:{del_add.stderr.decode('utf-8')}")
                sys.exit(1)

        try:
            subprocess.run(
                f"git clone https://gitee.com/April_Zhao/trinity_{self.compiler}.git",
                cwd="/home/trinity_test/",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise GitCloneError(e.returncode,f'https://gitee.com/April_Zhao/trinity_{self.compiler}.git',e.stderr.decode('utf-8'))

        try:
            subprocess.run(
                f"./configure && make && make install",
                cwd=f"/home/trinity_test/trinity_{self.compiler}",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"trinity测试出错:configure和make失败.报错信息:{e.stderr.decode('utf-8')}")

        try:
            set_permit = subprocess.run(
                f"chmod -R 777 /home/trinity_test/trinity_{self.compiler}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"trinity测试出错:trinity_{self.compiler}目录的权限设置失败.报错信息:{e.stderr.decode('utf-8')}")


    def run_test(self):
        try:
            trinity = subprocess.run(
                f"""su trinity_test -c 'cd /home/trinity_test/trinity_{self.compiler} && ./trinity -N 10000'""",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"trinity测试出错:configure和make失败.报错信息:{e.stderr.decode('utf-8')}")
        else:
            self.test_result = trinity.stdout.decode('utf-8')
            with lzma.open(self.directory / 'trinity.log.xz','wt',format=lzma.FORMAT_XZ) as file:
                file.write(self.test_result)


    def post_test(self):
        userdel = subprocess.run(
            "userdel trinity_test -r", # -r选项会删除用户的家目录
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
        )
        if userdel.returncode != 0:
            print(f"删除trinity的测试用户test失败,请手动删除该用户[userdel test -r].报错信息:{userdel.stderr.decode('utf-8')}")


    def run(self):
        print("开始进行trinity测试")
        self.pre_test()
        self.run_test()
        self.post_test()
        print("trinity测试结束")