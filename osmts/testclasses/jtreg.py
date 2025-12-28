import shutil
import subprocess
import sys
import tarfile
import requests
from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from .errors import DnfError


"""
使用 Jtreg 对 OpenJDK 执行测试回归测试
分别要测试OpenJDK 8,11,17
"""

headers = {
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0',
    'Referer': 'https://gitee.com/April_Zhao/osmts'
}


def install_rpm(package_name):
    try:
        subprocess.run(
            f"dnf install -y {package_name}",
            shell=True,check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise DnfError(e.returncode,e.stderr.decode())


def remove_rpm(package_name):
    dnf = subprocess.run(
        f"dnf remove -y {package_name}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if dnf.returncode != 0:
        print(f"jtreg测试安装{package_name}失败,报错信息:{dnf.stderr.decode('utf-8')}")
        sys.exit(1)


def clean_java_environment():
    remove_rpm("java-1.8.0-openjdk*")
    remove_rpm("java-11-openjdk*")
    remove_rpm("java-17-openjdk*")


class Jtreg:
    def __init__(self, **kwargs):
        self.rpms = { 'subversion','screen','samba','samba-client','gdb','automake','lrzsz','expect','libX11*','libxt*','libXtst*','libXt*','libXrender*','cache*','cups*','freetype*','mercurial','numactl','vim','tar','dejavu-fonts','unix2dos','dos2unix','bc','lsof','net-tool'}
        self.path = Path('/root/osmts_tmp/jtreg')
        self.directory: Path = kwargs.get('saved_directory') / 'jtreg'


    def get_tar(self,package_name):
        response = requests.get(
            url=f"https://gitee.com/April_Zhao/osmts/releases/download/v1.0/{package_name}.tar.xz",
            headers=headers
        )
        response.raise_for_status()
        with tarfile.open(fileobj=BytesIO(response.content), mode="r:xz") as tar:
            tar.extractall(path=self.path)


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(parents=True)
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(parents=True)

        # 获取tar包
        with ThreadPoolExecutor(max_workers=5) as pool:
            pool.map(self.get_tar, ('jtreg','OpenJDK8-test','OpenJDK11-test','OpenJDK17-test'))
            pool.submit(clean_java_environment)


    def run_test(self):
        # OpenJDK8 测试
        print('  开始进行OpenJDK 8测试')
        install_rpm('java-1.8.0-openjdk*')
        jtreg = subprocess.run(
            "export JT_HOME=/root/osmts_tmp/jtreg/jtreg-4.2 && cd /root/osmts_tmp/jtreg/OpenJDK8-test && "
            "/root/osmts_tmp/jtreg/jtreg-4.2/bin/jtreg -va -ignore:quiet -jit -conc:auto -timeout:16 -tl:3590 "
            "hotspot/test:hotspot_tier1 langtools/test:langtools_tier1 jdk/test:jdk_tier1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        with open(self.directory / 'OpenJDK8.log', 'w') as log:
            log.write(jtreg.stdout.decode('utf-8'))
        remove_rpm('java-1.8.0-openjdk*')
        print('  OpenJDK 8测试结束')


        # OpenJDK11 测试
        print('  开始进行OpenJDK 11测试')
        install_rpm('java-11-openjdk*')
        jtreg = subprocess.run(
            "export JT_HOME=/root/osmts_tmp/jtreg/jtreg-7.3.1 && cd /root/osmts_tmp/jtreg/OpenJDK11-test && "
            "/root/osmts_tmp/jtreg/jtreg-7.3.1/bin/jtreg -va -ignore:quiet -jit -conc:auto -timeout:16 -tl:3590 "
            "langtools:tier1 hotspot/jtreg:tier1 jdk:tier1 jaxp:tier1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        with open(self.directory / 'OpenJDK11.log', 'w') as log:
            log.write(jtreg.stdout.decode('utf-8'))
        remove_rpm('java-11-openjdk*')
        print('  OpenJDK 11测试结束')


        # OpenJDK17 测试
        print('  开始进行OpenJDK 17测试')
        install_rpm('java-17-openjdk*')
        jtreg = subprocess.run(
            "export JT_HOME=/root/osmts_tmp/jtreg/jtreg-7.3.1 && cd /root/osmts_tmp/jtreg/OpenJDK17-test && "
            "/root/osmts_tmp/jtreg/jtreg-7.3.1/bin/jtreg -va -ignore:quiet -jit -conc:auto -timeout:16 -tl:3590 "
            "jtreg:tier1 langtools:tier1 jdk:tier1 jaxp:tier1 lib-test:tier1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        with open(self.directory / 'OpenJDK17.log', 'w') as log:
            log.write(jtreg.stdout.decode('utf-8'))
        remove_rpm('java-17-openjdk*')
        print('  OpenJDK 17测试结束')


    def run(self):
        print('开始进行jtreg测试')
        self.pre_test()
        self.run_test()
        print('jtreg测试结束')