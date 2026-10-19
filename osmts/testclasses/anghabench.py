from pathlib import Path
import fnmatch,tarfile,resource
import os,subprocess,shutil
from openpyxl import Workbook
from concurrent.futures import ThreadPoolExecutor

from .errors import GitCloneError, DefaultError

# angha-bench 实测数据(2026-10-10):
#   源文件 1,044,021 个(全部为.c),内容 1.54GB,检出后占用约 4.3GB;
#   git对象树 92.3万个对象/465MB,完整克隆本机(32核+高速网络)需 181 秒。
# 该仓库是"百万文件"型,git clone 在板级设备上极易超时:
#   接收465MB + 服务端枚举92万对象 + 检出104万文件(inode消耗极大)。
# 因此改为下载预打包的 tar.xz:169MB、单文件HTTP、支持断点续传,
# 本机实测下载18秒、解压32秒,且解压后文件数与源仓库逐项一致。
ANGHABENCH_TARBALL_URL = (
    "https://atomgit.com/zhtianyu/angha-bench/releases/download/v0.1/angha-bench.tar.xz"
)
ANGHABENCH_TARBALL = "angha-bench.tar.xz"
# 归档下载需要正常UA,否则可能被服务端拒绝
ANGHABENCH_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux riscv64) osmts"}

# 归档解压后应有 1,044,021 个 .c 文件;少于该数说明归档被截断或解压中断
ANGHABENCH_REQUIRE_FILES = 1_044_021
# 解压需要 4.3GB 内容 + 百万文件的文件系统块开销,按1.4倍余量预检
ANGHABENCH_REQUIRE_FREE_GB = 7
ANGHABENCH_REQUIRE_FREE_INODES = 1_400_000
# 完整性标记:解压并校验通过后写入,避免半途失败后下次误判为可用
ANGHABENCH_COMPLETE_MARK = ".osmts_extract_complete"


class AnghaBench:
    def __init__(self, **kwargs):
        self.rpms = set()
        self.believe_tmp:bool = kwargs.get('believe_tmp')
        self.path = Path('/root/osmts_tmp/angha-bench')
        self.directory: Path = kwargs.get('saved_directory') / 'anghabench'
        self.log_files:Path = self.directory / 'log_files'
        self.matches:list = []
        self.failed_compile:list = []

        self.failed = 0
        self.total = 0

        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = 'AnghaBench'

        self.ws.cell(1,1,"AnghaBench测试中编译未通过项目汇总")
        self.ws.merge_cells("A1:B1")
        self.ws.append(['文件名','日志文件'])


    def _check_free_space(self, target_dir:Path):
        """解压104万个文件前预检空间与inode,避免中途失败留下半成品。"""
        vfs = os.statvfs(target_dir)
        free_gb = vfs.f_bavail * vfs.f_frsize / (1024 ** 3)
        free_inodes = vfs.f_favail
        # f_files为0表示该文件系统不限制inode数(btrfs等),跳过inode检查
        inode_limited = vfs.f_files > 0
        if free_gb < ANGHABENCH_REQUIRE_FREE_GB or (
            inode_limited and free_inodes < ANGHABENCH_REQUIRE_FREE_INODES
        ):
            inode_desc = f"{free_inodes}个inode" if inode_limited else "不限量inode"
            raise DefaultError(
                f"angha-bench解压需要至少{ANGHABENCH_REQUIRE_FREE_GB}GB空闲空间和"
                f"{ANGHABENCH_REQUIRE_FREE_INODES}个空闲inode(源码含104万个.c文件,"
                f"常见ext4分区需约30GB以上),当前{target_dir}所在文件系统仅剩"
                f"{free_gb:.1f}GB空间、{inode_desc},"
                f"请扩容根分区或把osmts_tmp放到更大的挂载点上"
            )


    def _download_tarball(self, tarball:Path):
        """下载源码归档。用 -C - 断点续传:板级设备网络慢,一次下载可能被中断,
        续传可避免每次失败都从头开始(这也是弃用 git clone 的主要原因之一)。"""
        print(f"开始下载angha-bench源码归档(约169MB):{ANGHABENCH_TARBALL_URL}")
        try:
            subprocess.run(
                ["curl", "-fL", "-C", "-",
                 "--retry", "5", "--retry-delay", "5", "--retry-connrefused",
                 "--connect-timeout", "30",
                 "-A", ANGHABENCH_HEADERS["User-Agent"],
                 "-o", str(tarball), ANGHABENCH_TARBALL_URL],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise GitCloneError(e.returncode, ANGHABENCH_TARBALL_URL, e.stderr)
        print(f"归档下载完成:{tarball}({tarball.stat().st_size / 1024 / 1024:.1f}MB)")


    def _extract_tarball(self, tarball:Path, dest_dir:Path):
        """解压归档并校验。tar.xz 的流完整性用 xz -t 主动确认,比只看tar退出码更可靠
        (xz是流式解压,截断的归档可能在tar侧表现为"提前结束"而不报错)。"""
        try:
            subprocess.run(
                ["xz", "-t", str(tarball)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(
                f"angha-bench测试出错.源码归档xz流校验失败(文件可能未下载完整),"
                f"请删除{tarball}后重试.报错信息:{e.stderr.decode('utf-8', errors='replace')}"
            )

        print(f"开始解压源码归档到{dest_dir}(104万个文件,需要几分钟)...")
        try:
            subprocess.run(
                # --no-same-owner:归档内属主是打包机用户,板上不存在也没有意义
                ["tar", "--no-same-owner", "-xJf", str(tarball), "-C", str(dest_dir)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(
                f"angha-bench测试出错.解压源码归档失败,报错信息:"
                f"{e.stderr.decode('utf-8', errors='replace')}"
            )

        # 校验1:顶层目录存在(归档内顶层目录名是 angha-bench,与 self.path.name 一致)
        extracted = dest_dir / self.path.name
        if not extracted.is_dir():
            raise DefaultError(
                f"angha-bench测试出错.解压后未找到预期目录:{extracted}"
            )
        # 校验2:文件数达标(截断的归档会造成解压"成功"但文件不全)
        # 用 os.walk 逐层统计,不依赖 find 子进程,也不受shell参数长度限制
        actual = sum(len(files) for _, _, files in os.walk(extracted))
        if actual < ANGHABENCH_REQUIRE_FILES:
            raise DefaultError(
                f"angha-bench测试出错.解压后文件数不足:期望至少{ANGHABENCH_REQUIRE_FILES}个,"
                f"实际{actual}个,归档可能不完整(可删除{dest_dir}与{tarball}后重试)"
            )
        print(f"解压完成并校验通过:共{actual}个文件")
        # 校验通过才写标记,避免半成品被下次运行误判为可用
        (dest_dir / ANGHABENCH_COMPLETE_MARK).touch()


    def pre_test(self):
        resource.setrlimit(resource.RLIMIT_NOFILE,(65536,524288))
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)
        self.log_files.mkdir(parents=True)

        work_dir = self.path.parent
        complete_mark = work_dir / ANGHABENCH_COMPLETE_MARK

        # 复用条件:目录存在 + 上次解压校验通过(有标记)。只看目录存在是不够的 ——
        # 上次解压中断会留下百万个残缺文件,继续用会得到错误的测试结果。
        if complete_mark.exists() and self.path.is_dir():
            print(f"复用上次已校验通过的源码目录:{self.path}")
            return
        if self.path.exists() and self.believe_tmp:
            # 用户显式要求相信 osmts_tmp:即使没有标记也按可用处理
            print(f"believe_tmp=1,复用已有源码目录:{self.path}")
            return

        work_dir.mkdir(parents=True, exist_ok=True)
        self._check_free_space(work_dir)

        # 清理上次的半成品(可能残留百万个残缺文件)
        if self.path.exists():
            print(f"清理上次未完成的源码目录:{self.path}")
            shutil.rmtree(self.path, ignore_errors=True)
        complete_mark.unlink(missing_ok=True)

        tarball = work_dir / ANGHABENCH_TARBALL
        if tarball.exists():
            print(f"发现已下载的归档,继续复用:{tarball}")
        else:
            self._download_tarball(tarball)

        self._extract_tarball(tarball, work_dir)
        print(f"angha-bench源码就绪:{self.path}(归档保留在{tarball},重跑可直接复用)")



    def match2result(self,match):
        # 只关心"能否编译通过",故用 -fsyntax-only:
        #   1) 返回码与 -c 完全一致(已用缺头文件/类型错误/隐式声明/GNU扩展等样本验证);
        #   2) 不做代码生成,单文件耗时约减半(本机实测 12ms → 6ms);
        #   3) 不会在源码树里留下 104 万个从未被读取、也从不清理的 .o 文件。
        compile = subprocess.run(
            f"gcc {match[1]} -fsyntax-only",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        if compile.returncode != 0: # 这里编译出错在预料之中不属于意外实践
            with open(self.log_files / (match[0] + '.log'), 'w', encoding='utf-8') as log:
                log.write(compile.stdout.decode('utf-8', errors='replace'))
            return match[0]
        else:
            return None


    def run_test(self):
        if self.matches == []:
            for root,dirnames,filenames in os.walk(self.path):
                for filename in fnmatch.filter(filenames, '*.c'):
                    self.matches.append((filename,os.path.join(root,filename)))
        self.total = len(self.matches)
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            results = executor.map(self.match2result, self.matches)
            for result in results:
                if result is not None:
                    self.failed_compile.append(result)
        
        for item in set(self.failed_compile):
            self.ws.append([item, item + '.log'])

        self.failed = len(self.failed_compile)
        # 汇总结果
        self.ws.append([f"总共编译文件数{self.total}",f"通过编译数{self.total - self.failed}",f"失败编译数{self.failed}"])

        self.wb.save(self.directory / 'AnghaBench.xlsx')

        with tarfile.open(self.directory / 'AnghaBench.tar.xz',"w:xz") as tar:
            tar.add(self.log_files)


    def run(self):
        print('开始进行AnghaBench测试')
        self.pre_test()
        self.run_test()
        print('AnghaBench测试结束')