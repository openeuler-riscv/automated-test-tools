import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from openpyxl import Workbook

from .errors import GitCloneError, DefaultError, RunError
from .utils import decode_output

"""
文档:https://blog.sina.com.cn/s/blog_7695e9f40100yjme.html
"""



class Ltp:
    def __init__(self, **kwargs):
        self.rpms = {'automake','pkgconf','autoconf','bison','flex','m4','kernel-headers','glibc-headers','findutils','libtirpc','libtirpc-devel','pkg-config'}
        self.path = Path('/root/osmts_tmp/ltp')
        self.directory: Path = kwargs.get('saved_directory') / 'ltp'

    def get_latest_ltp_version(self):
        # 1) 优先用 github 的 git ls-remote 获取最新 release 标签(不走 GitHub API,避免速率限制)
        try:
            ls_remote = subprocess.run(
                ["git", "ls-remote", "--refs", "--tags", "https://github.com/linux-test-project/ltp.git"],
                check=True, capture_output=True, text=True, timeout=10,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                stdin=subprocess.DEVNULL,
            )
            # LTP release 标签格式为 YYYYMMDD(如 20260529),取最大值即最新版本
            release_tags = []
            for line in ls_remote.stdout.splitlines():
                tag = line.split("refs/tags/")[-1]
                if tag.isdigit() and len(tag) == 8:
                    release_tags.append(tag)
            if release_tags:
                version = max(release_tags)
                print(f"检测到最新LTP版本: {version}")
                return version
        except subprocess.CalledProcessError as e:
            # text=True 时 stderr 已是字符串,直接打印
            print(f"git ls-remote获取最新LTP版本失败: {e.stderr}")
        except subprocess.TimeoutExpired as e:
            print(f"git ls-remote获取最新LTP版本失败: {e}")

        # 2) 从 github releases/latest 的跳转地址解析标签(仅github可达时有效)
        try:
            latest_url = subprocess.run(
                ["curl", "-sIL", "-o", "/dev/null", "-w", "%{url_effective}",
                 "https://github.com/linux-test-project/ltp/releases/latest"],
                check=True, capture_output=True, text=True, timeout=10,
            )
            version = latest_url.stdout.strip().rstrip("/").rsplit("/", 1)[-1]
            if version.isdigit() and len(version) == 8:
                print(f"检测到最新LTP版本: {version}")
                return version
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"从releases页面获取最新LTP版本失败: {e}")

        print("使用 master 分支")
        return "master"

    def _download_ltp_tarball(self, version):
        # 官方release的ltp-full tarball包含kirk等子模块,用于git协议被拦截的网络
        if version == "master":
            raise GitCloneError(1, 'https://github.com/linux-test-project/ltp',
                                '无法确定LTP release版本,不能下载tarball'.encode())
        tarball = f"ltp-full-{version}.tar.xz"
        url = f"https://github.com/linux-test-project/ltp/releases/download/{version}/{tarball}"
        print(f"开始下载ltp源码tarball: {url}")
        try:
            subprocess.run(
                ["curl", "-fL", "--connect-timeout", "10", "--max-time", "300",
                 "-o", f"/root/osmts_tmp/{tarball}", url],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=320,
            )
            print(f"tarball下载完成({os.path.getsize(f'/root/osmts_tmp/{tarball}') // 1024 // 1024}MB),解压中...")
            subprocess.run(
                ["tar", "xJf", f"/root/osmts_tmp/{tarball}", "-C", "/root/osmts_tmp"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=600,
            )
        except subprocess.CalledProcessError as e:
            raise GitCloneError(e.returncode, url, e.stderr or '下载ltp tarball失败'.encode())
        # 清理clone超时残留的半成品目录,避免rename失败
        if self.path.exists():
            shutil.rmtree(self.path)
        os.rename(f"/root/osmts_tmp/ltp-full-{version}", "/root/osmts_tmp/ltp")
        os.remove(f"/root/osmts_tmp/{tarball}")
        print(f"源码解压完成:/root/osmts_tmp/ltp(已包含kirk子模块)")

    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(exist_ok=True, parents=True)
        if self.path.exists():
            shutil.rmtree(self.path)

        version = self.get_latest_ltp_version()

        try:
            # GIT_TERMINAL_PROMPT=0 禁止git交互式询问账号密码,否则会卡死在输入提示
            clone_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            # timeout: 网络不稳定时clone可能挂起无响应,超时后走tarball兜底
            subprocess.run(
                # --recurse-submodules 检出 tools/kirk 子模块,make install 会安装 kirk
                ["git", "clone", "--depth", "1", "--recurse-submodules", "--branch", version,
                 "https://github.com/linux-test-project/ltp.git"],
                cwd = "/root/osmts_tmp",
                check=True,
                env=clone_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            # 部分网络拦截github的git协议但允许下载release文件,git clone失败时改用官方release tarball
            print(f"git clone拉取ltp源码失败({decode_output(e.stderr)}),尝试下载release tarball")
            self._download_ltp_tarball(version)
        except subprocess.TimeoutExpired:
            print("git clone超时(网络不稳定),尝试下载release tarball")
            self._download_ltp_tarball(version)

        print("开始编译安装LTP(make autotools && ./configure && make,板子上可能需要较长时间)...")
        t0 = time.time()
        try:
            subprocess.run(
                "make autotools && ./configure && make -j $(nproc) && make install",
                cwd = "/root/osmts_tmp/ltp/",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"ltp测试出错.configure和make出错:报错信息:{decode_output(e.stderr)}")
        print(f"LTP编译安装完成,耗时{int(time.time() - t0)}秒")

        # 添加标记
        Path('/opt/ltp/finish.sign').touch()


    def run_test(self):
        report = Path('/opt/ltp/kirk-report.json')
        if report.exists():
            report.unlink()  # kirk 要求 --json-report 目标文件不存在

        # kirk 需要显式列出全部测试套件(runtest 目录下的文件名)
        suites_list = sorted(os.listdir('/opt/ltp/runtest'))
        suites = " ".join(suites_list)
        # 串行执行:并行会放大内核竞态触发概率,panic时日志里也混着多个用例难以定位
        kirk_jobs = 1
        print(f"开始运行LTP测试({len(suites_list)}个套件,串行执行,可能需要数小时)...")
        t0 = time.time()
        # 输出同时写入日志文件,设备崩溃/断电后仍可查看(stdbuf -oL保证行级刷新,不丢尾部数据)
        kirk_log = self.directory / 'kirk.log'
        kirk = subprocess.run(
            f"stdbuf -oL /opt/ltp/kirk --run-suite {suites} --workers {kirk_jobs} "
            f"--no-colors --json-report {report} > {kirk_log} 2>&1",
            cwd="/opt/ltp",
            shell=True,
            stdout=subprocess.DEVNULL,
        )
        print(f"测试日志已保存到:{kirk_log}")
        if kirk.returncode != 0:
            log_tail = ' '.join(kirk_log.read_text(errors='replace').splitlines()[-5:])
            print(f"ltp测试出错.kirk进程报错(详见{kirk_log}):{log_tail}")
            print('这是正常现象,osmts继续运行')

        # 测试结果存储在 kirk 生成的 JSON 报告中
        # 上面 kirk 非0退出时已明确"继续运行",此时报告可能根本没生成;
        # 必须先判存在性,否则 open() 抛 FileNotFoundError 掩盖真实原因
        if not report.exists():
            raise RunError(
                kirk.returncode,
                f"kirk未生成测试报告:{report},无法解析结果.完整输出见:{kirk_log}",
            )
        wb = Workbook()
        ws = wb.active
        ws.title = 'ltp report'
        ws.append(['Testcase', 'Result', 'Exit Value'])
        with open(report) as f:
            data = json.load(f)
        stats = data['stats']
        print(f"LTP测试结束,耗时{int(time.time() - t0)}秒:"
              f"通过{stats['passed']},失败{stats['failed']},"
              f"broken{stats['broken']},跳过{stats['skipped']}")
        for item in data['results']:
            status = item['status'].upper()
            if status in ('PASS', 'FAIL', 'CONF', 'BROK'):
                ws.append([item['test_fqn'], status, item['test']['retval'][0]])
        wb.save(self.directory / 'ltp.xlsx')

        # 复制 kirk 报告作为摘要(替代原 LTP_RUN_* 文件)
        shutil.copy(report, self.directory)


    def run(self):
        print("开始进行ltp测试")
        self.pre_test()
        self.run_test()
        print("ltp测试结束")