import re
import shutil
import subprocess
import zipfile
import os
import tarfile
import shlex
import time
import requests
from pathlib import Path
from collections import Counter
from openpyxl import Workbook
from openpyxl.styles import Alignment

from .errors import DnfError, DefaultError
from .utils import decode_output


"""
使用 Jtreg 对 OpenJDK 执行测试回归测试
根据系统安装的 OpenJDK 版本自动下载对应源码包和 jtreg 工具
"""

headers = {
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0',
    'Referer': 'https://gitee.com/April_Zhao/osmts'
}

JDK_RPM_PATTERNS = {
    8: 'java-1.8.0-openjdk*',
    11: 'java-11-openjdk*',
    17: 'java-17-openjdk*',
    21: 'java-21-openjdk*',
}

JDK_GITHUB_REPOS = {
    8: 'openjdk/jdk8u-dev',
    11: 'openjdk/jdk11u-dev',
    17: 'openjdk/jdk17u-dev',
    21: 'openjdk/jdk21u-dev',
}

# jtreg 版本与 JDK 的对应关系,取自各 JDK 官方构建配置 make/conf/jib-profiles.js
# (其中 jtreg 依赖项写明了该 JDK 使用的 jtreg 版本):
#   jdk11u-dev -> bundles/jtreg-7.3.1+1.zip
#   jdk17u-dev -> bundles/jtreg-7.5.2+1.zip
#   jdk21u-dev -> bundles/jtreg-8.2.1+1.zip
# JDK8 的构建系统没有 jib-profiles.js,沿用验证可用的 jtreg 4.2-b16。
# 注意:jdk17 用 7.3.1 会失败(实测),必须用 7.5.2。
JTREG_VERSION = {
    8: '4.2-b16',
    11: '7.3.1+1',
    17: '7.5.2+1',
    21: '8.2.1+1',
}

# shipilev 站点的文件名规则不统一:
#   JDK8  -> jtreg4.2-b16.zip   (无连字符)
#   JDK11+-> jtreg-7.3.1+1.zip  (有连字符)
# 故直接保存文件名,不做字符串拼接(拼接会生成 jtreg7.3.1+1.zip 这种不存在的地址)。
JTREG_ZIP_FILENAME = {
    8: 'jtreg4.2-b16.zip',
    11: 'jtreg-7.3.1+1.zip',
    17: 'jtreg-7.5.2+1.zip',
    21: 'jtreg-8.2.1+1.zip',
}

JTREG_SHIPILEV_URL = {
    major: f'https://builds.shipilev.net/jtreg/{filename}'
    for major, filename in JTREG_ZIP_FILENAME.items()
}

# 这些zip解压后的顶层目录都叫 jtreg(不带版本号),因此不同JDK的jtreg必须解压到
# 各自独立的子目录,否则后一个版本会覆盖前一个。此处记录用于校验/提示。
JTREG_EXTRACTED_DIRNAME = 'jtreg'

# 下载产物的子目录名:按JDK版本隔离,避免互相覆盖
JTREG_TOOL_SUBDIR = 'jtreg_tool'
JDK_SRC_SUBDIR = 'jdk_src'

# 单个JDK版本的下载/解压完成标记(放在该版本的工具目录内)
JTREG_DOWNLOAD_MARK = '.osmts_download_complete'



def install_rpm(package_name):
    try:
        subprocess.run(
            f"dnf install -y {package_name}",
            shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        stderr_msg = decode_output(e.stderr) if e.stderr else ''
        raise DnfError(e.returncode, stderr_msg)


def remove_rpm(package_name):
    try:
        subprocess.run(
            f"dnf remove -y {package_name}",
            shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        stderr_msg = decode_output(e.stderr) if e.stderr else ''
        raise DnfError(e.returncode, stderr_msg)


def _build_jdk_tag(major, ver1, ver2, ver3, ver4, ver5):
    if major == 8:
        return f"jdk8u{int(ver4):03d}-b{ver5}"
    else:
        patch = ver4 if ver4 else ver3
        return f"jdk-{ver1}.{ver2}.{patch}+{ver5}"


def detect_java_version(major_ver):
    result = subprocess.run(
        "java -version",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout = decode_output(result.stdout) if result.stdout else ''
    stderr = decode_output(result.stderr) if result.stderr else ''
    output = stdout + stderr
    print(f"[jtreg] java -version 原始输出:\n{output.strip() if output.strip() else '(空)'}")

    line1 = output.splitlines()[0] if output else ''

    ver_match = re.search(r'"(\d+)\.(\d+)\.(\d+)(?:_(\d+))?"', line1)
    if not ver_match:
        print(f"[jtreg] 未从 java -version 第一行解析出版本号，跳过 JDK {major_ver}")
        return None

    ver1, ver2, ver3, ver4 = ver_match.groups()
    if ver1 == '1' and ver2 == '8':
        detected_major = 8
    else:
        detected_major = int(ver1)

    has_underscore = '_' in line1

    b_match = re.search(r'\(build\s+[\d.]+_(\d+)-b(\d+)\)', output)
    if b_match:
        b4, b5 = b_match.groups()
        ver5 = b5
        if ver4 is None:
            ver4 = b4
    else:
        b_match2 = re.search(r'\(build\s+([\d.]+)\+(\d+)\)', output)
        if b_match2:
            b_ver, b5 = b_match2.groups()
            ver5 = b5
            if ver4 is None:
                b_parts = b_ver.split('.')
                if detected_major == 8 and len(b_parts) >= 3:
                    ver4 = b_parts[2]
                else:
                    ver4 = '0'
        else:
            ver5 = '0'
            ver4 = ver4 or '0'

    update = ver4 if ver4 else '0'
    full_version = (f"{ver1}.{ver2}.{ver3}_{update}-b{ver5}"
                    if update != '0'
                    else f"{ver1}.{ver2}.{ver3}-b{ver5}")

    print(f"[jtreg] 解析到版本: {full_version}, 映射为主版本: {detected_major}")

    if detected_major != major_ver:
        print(f"[jtreg] 检测到主版本 {detected_major}，与预期 {major_ver} 不符，跳过")
        return None

    tag_patch = ver3 if ver4 else ver3
    tag_update = update if has_underscore else ver3
    tag = _build_jdk_tag(detected_major, ver1, ver2, tag_patch, tag_update, ver5)
    repo = JDK_GITHUB_REPOS[detected_major]
    src_url = f"https://github.com/{repo}/archive/refs/tags/{tag}.zip"
    print(f"[jtreg] 匹配到 OpenJDK {detected_major} (build: {full_version}), tag: {tag}")
    print(f"[jtreg]   源码下载地址: {src_url}")
    return {
        'full': full_version,
        'tag': tag,
        'src_url': src_url,
        'src_repo': repo,
        'rpm': JDK_RPM_PATTERNS[detected_major],
        'jt_home': None,
        'test_dir': None,
    }


# 在指定目录下查找以 jtreg 开头的子目录
def _find_jtreg_dir(base_path):
    for item in base_path.iterdir():
        if item.is_dir() and item.name.startswith('jtreg'):
            return item
    return None


# 带重试机制地下载 zip 文件并解压到指定目录
def _download_and_extract_zip(url, extract_to, progress_label, timeout, max_retries=3):
    archive_path = extract_to / f".{progress_label.replace(' ', '_').replace('/', '_')}.zip"
    last_error = None

    for attempt in range(1, max_retries + 1):
        if archive_path.exists():
            archive_path.unlink()

        print(f"[jtreg] {progress_label}: {url}")
        if attempt > 1:
            print(f"[jtreg] 第 {attempt}/{max_retries} 次重试下载 {progress_label}")

        try:
            with requests.get(url, headers=headers, timeout=timeout, stream=True) as response:
                response.raise_for_status()
                total = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_pct = -1

                with open(archive_path, 'wb') as archive_file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        archive_file.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded * 100 // total
                            # 按10%粒度打印:每1MB打印一次会把控制台刷满
                            # (板上网速慢,150MB的源码包会输出上百行)
                            if pct >= last_pct + 10:
                                last_pct = pct
                                print(f"[jtreg] {progress_label} 下载进度: {pct}%")

                if total > 0:
                    print(f"[jtreg] {progress_label} 下载进度: 100%")

            if not zipfile.is_zipfile(archive_path):
                raise zipfile.BadZipFile(f"{archive_path} 不是有效的 zip 文件")

            archive_size_kb = archive_path.stat().st_size // 1024
            print(f"[jtreg] {progress_label} 下载完成 ({archive_size_kb} KB), 开始解压...")
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(path=extract_to)
            print(f"[jtreg] {progress_label} 解压完成")
            archive_path.unlink(missing_ok=True)
            return
        except (requests.RequestException, zipfile.BadZipFile, OSError) as e:
            last_error = e
            print(f"[jtreg] {progress_label} 下载失败: {e}")
            archive_path.unlink(missing_ok=True)
            if attempt < max_retries:
                wait_seconds = min(5 * attempt, 15)
                print(f"[jtreg] {wait_seconds} 秒后重试...")
                time.sleep(wait_seconds)

    raise last_error


# 下载并解压指定版本的 JDK 源码
def _download_jdk_source(url, extract_to, major_ver):
    _download_and_extract_zip(
        url=url,
        extract_to=extract_to,
        progress_label=f"下载 JDK {major_ver} 源码",
        timeout=(30, 600),
    )


# 下载并解压指定版本对应的 jtreg 工具包
def _download_jtreg(url, extract_to, major_ver):
    _download_and_extract_zip(
        url=url,
        extract_to=extract_to,
        progress_label=f"下载 jtreg 工具 (JDK {major_ver})",
        timeout=(30, 300),
    )
    _ensure_jtreg_executable(extract_to)


def _ensure_jtreg_executable(extract_to):
    """把解压出来的 jtreg 可执行文件补上执行权限。

    jtreg 的 zip 解压后顶层目录固定叫 jtreg(zip 内不含权限位),
    故要显式 chmod,否则调用时会 Permission denied。
    """
    for root, dirs, files in os.walk(extract_to):
        if Path(root).name == 'bin' and 'jtreg' in files:
            jt_bin = Path(root) / 'jtreg'
            jt_bin.chmod(0o755)
            print(f"[jtreg] 已设置 {jt_bin} 执行权限")
            return jt_bin
    return None


def _detect_java_home():
    """定位刚安装的JDK根目录,返回(Path 或 None, 说明)。

    jtreg 的启动脚本按 JTREG_JAVA/JT_JAVA -> JAVA_HOME -> -jdk -> 裸'java'
    的顺序定位 Java;前三者都没设且 PATH 里没有 java 时,
    会直接打印 "No java executable at java" 并退出 —— 实测症状正是如此,
    因此必须显式给出 JAVA_HOME(或 JT_JAVA)。

    jtreg 还要用 javac 编译测试用例,所以只装JRE不够,这里一并校验 javac。
    """
    java_path = shutil.which('java')
    if not java_path:
        return None, 'PATH中找不到java'

    real = Path(java_path)
    try:
        real = real.resolve()
    except OSError:
        pass

    # java 通常是指向 <JDK根>/bin/java 的 alternatives 符号链接,解析后即得JDK根
    candidate = real.parent.parent
    if (candidate / 'bin' / 'javac').exists():
        return candidate, '经符号链接解析'

    # 否则从 java 所在位置逐级向上找同时含 bin/java 与 bin/javac 的目录
    for parent in real.parents:
        if (parent / 'bin' / 'java').exists() and (parent / 'bin' / 'javac').exists():
            return parent, '向上查找'

    return None, (f'java位于{real},但未找到配套的javac;'
                  f'jtreg需要用javac编译测试用例,请安装对应JDK的开发包'
                  f'(如 java-21-openjdk-devel)')


def _read_log_tail(log_path, lines=20):
    """读取日志末尾若干行(用 os.SEEK_END 从尾部读,避免把整份日志读进内存)。"""
    try:
        with open(log_path, 'rb') as log:
            log.seek(0, os.SEEK_END)
            size = log.tell()
            chunk = min(size, 64 * 1024)
            log.seek(size - chunk)
            data = log.read(chunk)
    except OSError:
        return ''
    text = data.decode('utf-8', errors='replace')
    return '\n'.join(text.splitlines()[-lines:])


def _apply_sheet_style(worksheet):
    """统一表格样式:顶端对齐 + 自动换行(两张表都用,避免只设一半)。"""
    for cells in worksheet.iter_rows():
        for cell in cells:
            cell.alignment = Alignment(vertical='top', wrap_text=True)


class Jtreg:
    """运行 Jtreg 回归测试。

    默认跑全部支持的JDK版本(8/11/17/21);子类把 tools 收窄为单个版本,
    便于把各版本拆开单独跑 —— 每个版本的tier1都很长,合并跑时
    某个版本失败会掩盖其它版本的结果。

    ⚠️ 不要同时配置 jtreg 与 jtreg_<同一版本>:
      两者的工作目录(/root/osmts_tmp/jtreg)与结果目录都相同,
      同一个JDK版本被同时测试时,一方会删除另一方的 jdkN/ 工作目录、
      两者的下载目录会互相清理、日志文件会交错写入,
      产生"看起来跑完了、结果其实是错的"静默故障。
      例如 run_tests = ['jtreg_8', 'jtreg_11'] 是正确的分法;
      run_tests = ['jtreg', 'jtreg_8'] 会让 JDK8 被跑两遍且互相破坏。
    """
    tools = tuple(sorted(JDK_RPM_PATTERNS.keys()))

    def __init__(self, **kwargs):
        self.rpms = {'subversion', 'screen', 'samba', 'samba-client', 'gdb',
                     'automake', 'lrzsz', 'expect', 'libX11*', 'libxt*', 'libXtst*',
                     'libXt*', 'libXrender*', 'cache*', 'cups*', 'freetype*',
                     'mercurial', 'numactl', 'vim', 'tar', 'dejavu-fonts',
                     'unix2dos', 'dos2unix', 'bc', 'lsof', 'net-tools'}
        self.path = Path('/root/osmts_tmp/jtreg')
        self.directory: Path = kwargs.get('saved_directory') / 'jtreg'

    def _tools_to_run(self):
        """要运行的JDK版本列表(按版本号升序),只保留常量表里支持的版本。"""
        return sorted(v for v in self.tools if v in JDK_RPM_PATTERNS)

    def _result_stem(self):
        """结果文件的基础名,由本类覆盖的JDK版本决定。

        多个 jtreg_* 测试项的 directory 都是 saved_directory/jtreg,
        若汇总表用固定名 jtreg.xlsx,jtreg_8 与 jtreg_11 先后运行会互相覆盖,
        最后只剩一份报表。带上版本号后各测试项的产物互不冲突,
        也便于事后判断"这份报表覆盖了哪些JDK版本"。
        """
        versions = self._tools_to_run()
        suffix = '_'.join(str(v) for v in versions) if versions else 'none'
        return f'jtreg_{suffix}'

    def _excel_name(self):
        """汇总报表文件名(含本类覆盖的JDK版本,避免多个 jtreg_* 测试项互相覆盖)。"""
        return f'{self._result_stem()}.xlsx'

    # 返回某个JDK版本专属的工作目录(工具与源码分开放,避免不同版本互相覆盖)
    def _version_dirs(self, major_ver):
        tool_dir = self.path / JTREG_TOOL_SUBDIR / f'jdk{major_ver}'
        src_dir = self.path / JDK_SRC_SUBDIR / f'jdk{major_ver}'
        return tool_dir, src_dir

    # 初始化结果目录和工作目录
    def _setup_workdir(self):
        if not self.directory.exists():
            self.directory.mkdir(parents=True)
        if not self.path.exists():
            self.path.mkdir(parents=True)

    # 确保某个JDK版本所需的 jtreg 与源码已就绪(复用已下载产物)
    def _ensure_downloads(self, info, major_ver):
        tool_dir, src_dir = self._version_dirs(major_ver)
        mark = tool_dir / JTREG_DOWNLOAD_MARK
        if mark.exists() and (src_dir / 'test').exists():
            print(f"[jtreg] 复用已下载的 jtreg {JTREG_VERSION[major_ver]} 与源码: {tool_dir}")
            return
        # 半成品目录清掉重来:中断的解压结果不能直接使用
        for stale in (tool_dir, src_dir):
            if stale.exists():
                shutil.rmtree(stale, ignore_errors=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        src_dir.mkdir(parents=True, exist_ok=True)
        print(f"[jtreg] 第3步: 下载源码和 jtreg (jtreg {JTREG_VERSION[major_ver]})")
        _download_jdk_source(info['src_url'], src_dir, major_ver)
        _download_jtreg(JTREG_SHIPILEV_URL[major_ver], tool_dir, major_ver)
        mark.touch()

    # 在工作目录中定位 jtreg 可执行目录和 JDK 源码目录，填充 info 字典
    def _resolve_paths(self, info, major_ver):
        tool_dir, src_dir = self._version_dirs(major_ver)
        print(f"[jtreg] jtreg 工具目录内容: {list(tool_dir.iterdir())}")

        # zip 解压后顶层目录固定叫 jtreg(不带版本号),故按目录名定位而非版本号
        jt_home = tool_dir / JTREG_EXTRACTED_DIRNAME
        if not (jt_home / 'bin' / 'jtreg').exists():
            found = _find_jtreg_dir(tool_dir)
            if found is None:
                raise FileNotFoundError(
                    f"无法在 {tool_dir} 中找到 jtreg 目录"
                )
            jt_home = found
            print(f"[jtreg] 未找到预期目录 {JTREG_EXTRACTED_DIRNAME}, "
                  f"已找到 jtreg 目录: {jt_home.name}")

        repo_name = info['src_repo'].split('/')[1]
        repo_dir = None
        for item in src_dir.iterdir():
            if item.is_dir() and repo_name in item.name:
                repo_dir = item
                break

        if repo_dir is None:
            raise FileNotFoundError(
                f"无法在 {src_dir} 中找到源码目录 (关键词: {repo_name})"
            )

        if not (repo_dir / 'test').exists():
            raise FileNotFoundError(
                f"源码目录 {repo_dir} 中不存在 test 子目录"
            )

        info['jt_home'] = str(jt_home)
        info['test_dir'] = str(repo_dir)
        info['repo_dir'] = repo_dir
        print(f"[jtreg] JDK {major_ver} 路径解析完成:")
        print(f"  JT_HOME = {jt_home}")
        print(f"  test_dir (repo root) = {repo_dir}")

    # 返回指定 JDK 主版本对应的 jtreg 测试集规格字符串
    def _get_test_spec(self, major_ver):
        specs = {
            8: 'hotspot/test:hotspot_tier1 langtools/test:langtools_tier1 jdk/test:jdk_tier1',
            11: 'test/langtools:tier1 test/hotspot/jtreg:tier1 test/jdk:tier1 test/jaxp:tier1',
            17: 'test/hotspot/jtreg:tier1 test/langtools:tier1 test/jdk:tier1 test/jaxp:tier1 test/lib-test:tier1',
            21: 'test/hotspot/jtreg:tier1 test/langtools:tier1 test/jdk:tier1 test/jaxp:tier1 test/lib-test:tier1',
        }
        return specs.get(major_ver, '')

    # 创建并返回指定 JDK 版本的 JTwork 和 JTreport 输出目录路径
    def _prepare_version_output_dirs(self, major_ver):
        version_root = self.path / f'jdk{major_ver}'
        if version_root.exists():
            shutil.rmtree(version_root)
        version_root.mkdir(parents=True, exist_ok=True)
        return {
            'root': version_root,
            'jtwork': version_root / 'JTwork',
            'jtreport': version_root / 'JTreport',
        }

    # 构造并执行 jtreg 命令，将日志输出到文件，返回退出码
    def _run_jtreg(self, version_info, test_spec, major_ver):
        jt_home = Path(version_info['jt_home'])
        test_dir = Path(version_info['test_dir'])
        output_dirs = self._prepare_version_output_dirs(major_ver)
        log_path = self.directory / f'{self._result_stem()}_OpenJDK{major_ver}.log'
        cmd = [
            str(jt_home / 'bin' / 'jtreg'),
            '-va',
            '-ignore:quiet',
            '-jit',
            '-conc:auto',
            '-timeout:16',
            '-tl:3590',
            f"-w:{output_dirs['jtwork']}",
            f"-r:{output_dirs['jtreport']}",
            *shlex.split(test_spec),
        ]
        # jtreg 启动脚本靠 JT_JAVA/JAVA_HOME/-jdk/PATH 定位Java,四者皆无时
        # 直接报 "No java executable at java" 并退出(实测症状)。
        # 这里显式指向刚安装的JDK:JT_JAVA 优先级最高,JAVA_HOME 同时设置
        # 以兼容老版本jtreg;PATH 里也补上,便于jtreg内部调用javac等工具。
        java_home, java_reason = _detect_java_home()
        if java_home is None:
            raise DefaultError(
                f"jtreg测试出错.OpenJDK {major_ver} 未找到可用的JDK:{java_reason}"
            )
        env = os.environ.copy()
        env['JT_HOME'] = str(jt_home)
        env['JAVA_HOME'] = str(java_home)
        env['JT_JAVA'] = str(java_home / 'bin' / 'java')
        env['PATH'] = f"{java_home / 'bin'}{os.pathsep}{env.get('PATH', '')}"

        print(f"[jtreg] 执行 jtreg 命令:")
        print(f"  JT_HOME = {jt_home}")
        print(f"  JAVA_HOME = {java_home} ({java_reason})")
        print(f"  test_dir = {test_dir}")
        print(f"  test_spec = {test_spec}")
        print(f"  JTreport = {output_dirs['jtreport']}")
        print(f"  JTwork = {output_dirs['jtwork']}")

        with open(log_path, 'w', encoding='utf-8') as log:
            jtreg = subprocess.run(
                cmd,
                cwd=test_dir,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )

        version_info['jt_home'] = jt_home
        version_info['test_dir'] = test_dir
        version_info['jtreport'] = output_dirs['jtreport']
        version_info['jtwork'] = output_dirs['jtwork']
        version_info['log_path'] = log_path
        version_info['returncode'] = jtreg.returncode
        version_info['command'] = ' '.join(shlex.quote(part) for part in cmd)
        version_info['log_tail'] = _read_log_tail(log_path)
        return jtreg.returncode

    # 将 jtreg 生成的 summary.txt 复制到结果目录
    def _copy_summary(self, version_info, major_ver):
        summary_source = version_info['jtreport'] / 'text' / 'summary.txt'
        if not summary_source.exists():
            # 附上日志尾部:真正的根因(jtreg自身的报错,如
            # "No java executable at java")写在日志里,
            # 只说"未生成summary.txt"会逼着人再去翻日志
            tail = version_info.get('log_tail') or '(日志为空)'
            raise DefaultError(
                f"jtreg测试出错.OpenJDK {major_ver} 未生成JTreport/text/summary.txt,"
                f"jtreg返回值:{version_info['returncode']}."
                f"日志{version_info['log_path']}末尾:\n{tail}"
            )

        summary_target = self.directory / f'OpenJDK{major_ver}_summary.txt'
        shutil.copy2(summary_source, summary_target)
        version_info['summary_path'] = summary_target
        print(f"[jtreg] 已保存 summary: {summary_target}")
        return summary_target

    # 将 JTreport 和 JTwork 目录打包为 tar.gz 归档文件
    def _package_output(self, version_info, major_ver):
        jtreport = version_info['jtreport']
        jtwork = version_info['jtwork']
        pkg_name = self.directory / f'OpenJDK{major_ver}_jtreg_output.tar.gz'
        # 必须先置 None:调用方无条件读取 package_path,
        # 若此处提前 return 不赋值,会抛 KeyError 中断后续所有 JDK 版本
        version_info['package_path'] = None

        items_to_pack = []
        if jtreport.exists():
            items_to_pack.append(jtreport)
        if jtwork.exists():
            items_to_pack.append(jtwork)

        if not items_to_pack:
            print(f"[jtreg] 未找到 JTreport 或 JTwork，跳过打包")
            return

        print(f"[jtreg] 正在打包 JTreport/JTwork 到 {pkg_name}")
        with tarfile.open(pkg_name, 'w:gz') as tar:
            for item in items_to_pack:
                tar.add(item, arcname=item.name)
        print(f"[jtreg] 打包完成: {pkg_name}")
        version_info['package_path'] = pkg_name
        return pkg_name

    # 解析 jtreg summary.txt，将每行测试结果转为含状态和详情的字典
    def _parse_summary_file(self, summary_path: Path):
        rows = []
        for raw_line in summary_path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw_line.rstrip()
            if not line:
                continue

            match = re.match(r'^(?P<test_name>.+?)\s{2,}(?P<result_text>.+)$', line)
            if not match:
                rows.append({
                    'test_name': line,
                    'status': 'UNPARSED',
                    'detail': '',
                })
                continue

            test_name = match.group('test_name').strip()
            result_text = match.group('result_text').strip()
            result_match = re.match(r'^(?P<status>[^.]+)\.\s*(?P<detail>.*)$', result_text)
            if result_match:
                status = result_match.group('status').strip()
                detail = result_match.group('detail').strip()
            else:
                status = result_text
                detail = ''

            rows.append({
                'test_name': test_name,
                'status': status,
                'detail': detail,
            })

        return rows

    # 将所有 JDK 版本的 jtreg 测试结果汇总写入 Excel 文件
    def _save_excel(self, version_results):
        wb = Workbook()
        ws_overview = wb.active
        ws_overview.title = 'overview'
        ws_overview.append([
            'JDK',
            'build',
            'jtreg returncode',
            'total',
            'passed',
            'failed',
            'error',
            'other',
            'summary file',
            'log file',
            'artifact',
            'note',
        ])

        for result in version_results:
            counter = Counter(row['status'] for row in result['rows'])
            total = len(result['rows'])
            passed = counter.get('Passed', 0)
            failed = counter.get('Failed', 0)
            error = counter.get('Error', 0)
            other = total - passed - failed - error

            package_path = result.get('package_path')
            note = 'jtreg非0返回值通常表示存在失败/错误用例, 以summary.txt统计为准'
            if not package_path:
                note = '未生成产物归档(JTreport/JTwork均不存在); ' + note
            # 该版本整体失败的记录:摘要/统计都不可得,note里说明原因
            if result.get('error'):
                note = f"该版本测试未完成: {result['error']}"

            ws_overview.append([
                f"OpenJDK{result['major_ver']}",
                result['build'],
                result['returncode'],
                total,
                passed,
                failed,
                error,
                other,
                str(result['summary_path']) if result['summary_path'] else '(未生成)',
                str(result['log_path']) if result['log_path'] else '(未生成)',
                str(package_path) if package_path else '(未生成)',
                note,
            ])

            ws_detail = wb.create_sheet(title=f"OpenJDK{result['major_ver']}")
            ws_detail.append(['test case', 'status', 'detail'])
            for row in result['rows']:
                ws_detail.append([row['test_name'], row['status'], row['detail']])

            # 明细表同样要设列宽:原先只给overview设了,明细表打开是默认列宽、内容挤在一起
            ws_detail.freeze_panes = 'A2'
            for column, width in (('A', 72), ('B', 14), ('C', 52)):
                ws_detail.column_dimensions[column].width = width
            _apply_sheet_style(ws_detail)

        ws_overview.freeze_panes = 'A2'
        for column, width in (('A', 12), ('B', 24), ('C', 16), ('D', 10), ('E', 10),
                              ('F', 10), ('G', 10), ('H', 10), ('I', 34), ('J', 30),
                              ('K', 34), ('L', 44)):
            ws_overview.column_dimensions[column].width = width
        _apply_sheet_style(ws_overview)

        wb.save(self.directory / self._excel_name())

    def run(self):
        print(f'开始进行jtreg测试,测试项:{self.tools}')
        self._setup_workdir()
        version_results = []
        version_errors = []

        for major_ver in self._tools_to_run():
            print(f"[jtreg] ========== JDK {major_ver} 测试开始 ==========")

            rpm = JDK_RPM_PATTERNS[major_ver]
            installed = False
            try:
                print(f"[jtreg] 第1步: 安装 {rpm}")
                install_rpm(rpm)
                installed = True

                print(f"[jtreg] 第2步: 检测 Java 版本")
                info = detect_java_version(major_ver)
                if info is None:
                    print(f"[jtreg] JDK {major_ver} 版本检测失败，跳过")
                    continue

                self._ensure_downloads(info, major_ver)

                print(f"[jtreg] 第4步: 解析路径")
                self._resolve_paths(info, major_ver)

                print(f"  开始进行OpenJDK {major_ver} 测试 (build: {info['full']})")
                self._run_jtreg(info, self._get_test_spec(major_ver), major_ver)
                print(f"  OpenJDK {major_ver} 测试结束")

                self._copy_summary(info, major_ver)
                self._package_output(info, major_ver)

                version_results.append({
                    'major_ver': major_ver,
                    'build': info['full'],
                    'returncode': info['returncode'],
                    'summary_path': info['summary_path'],
                    'log_path': info['log_path'],
                    'package_path': info.get('package_path'),
                    'rows': self._parse_summary_file(info['summary_path']),
                    'error': None,
                })
            except Exception as e:
                # 单个JDK版本失败不得终止其它版本:每个版本的tier1都很贵
                # (源码下载 + 长时间运行),一个版本出问题就让其余版本完全不跑,
                # 会浪费掉整轮测试。此处记录失败并继续下一个版本。
                # 但失败必须最终反映到 osmts 的结果表:否则从 run() 正常返回
                # 会被记为 success,出现"任务失败却显示成功"的错误报告。
                print(f"[jtreg] JDK {major_ver} 测试失败: {e}")
                version_errors.append(e)
                version_results.append({
                    'major_ver': major_ver,
                    'build': '(未完成)',
                    'returncode': '-',
                    'summary_path': None,
                    'log_path': getattr(self, '_current_log', None),
                    'package_path': None,
                    'rows': [],
                    'error': str(e),
                })
            finally:
                if installed:
                    print(f"[jtreg] 第5步: 卸载 {rpm}")
                    try:
                        remove_rpm(rpm)
                    except Exception as cleanup_error:
                        print(f"[jtreg] 卸载 {rpm} 失败: {cleanup_error}")
                # 每轮都落盘:否则后面的版本失败会让前面已完成版本的结果一起丢失
                self._save_excel(version_results)
                print(f"[jtreg] ========== JDK {major_ver} 测试结束 ==========\n")

        print(f"[jtreg] 已生成汇总报表: {self.directory / self._excel_name()}")
        failed = [r['major_ver'] for r in version_results if r.get('error')]
        if failed:
            # 让 osmts 把本测试记为 failed(全部版本的结果已在 Excel 中保留)
            raise version_errors[0]
        print('jtreg测试结束')


class Jtreg8(Jtreg):
    """只运行 OpenJDK 8 的 jtreg 测试"""
    tools = (8,)


class Jtreg11(Jtreg):
    """只运行 OpenJDK 11 的 jtreg 测试"""
    tools = (11,)


class Jtreg17(Jtreg):
    """只运行 OpenJDK 17 的 jtreg 测试"""
    tools = (17,)


class Jtreg21(Jtreg):
    """只运行 OpenJDK 21 的 jtreg 测试"""
    tools = (21,)
