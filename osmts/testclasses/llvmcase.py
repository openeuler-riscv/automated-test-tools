from pathlib import Path
import subprocess,shutil

from .errors import GitCloneError,RunError,DefaultError
from .utils import decode_output

# LLVM 构建的内存约束(2026-10-11 板上实测):
# 内核触发全局OOM,dmesg 记录
#   Out of memory: Killed process (cc1plus) anon-rss:1372136kB
# 即单个编译器进程峰值约 1.4GB。该板 8核/7.5GB内存,而 ninja 无 -j 时按核数
# 并发,8×1.4GB≈11.2GB 远超可用内存 ⇒ 编译进程被 OOM killer 杀掉,
# 表现为构建中途失败且报错信息很不直观(只剩cmake阶段的无害提示)。
# 故按可用内存推算并行度:并行度 = 可用内存 / 每任务预留。
# 预留取 1800MB(实测峰值1.4GB + 约30%余量,给链接与页缓存留空间)。
LLVM_MEM_PER_JOB_MB = 1800
# 并行度上限:即使内存很大也不超过核数太多;此值同时防止内存探测异常时放开并行
LLVM_MAX_JOBS = 8
LLVM_UNKNOWN_MEM_JOBS = 1      # 内存探测不到时的保守并行度
# 构建输出完整落盘(放结果目录),失败后可事后分析,不必重跑数小时
LLVM_BUILD_LOG = 'llvm_build.log'
LLVM_BUILD_LOG_TAIL_LINES = 30  # 异常里附带的日志尾部行数
# 构建成功标记:避免中断留下的半成品被误判为可用
LLVM_BUILD_MARK = '.osmts_llvm_build_complete'


class Llvmcase():
    # RVA20U64 / RVA23U64 是RISC-V Profiles规范里的配置档,不是硬件上报字段:
    # uname与gcc -dumpmachine在两档机器上完全相同(都是riscv64),
    # 唯一可靠依据是ISA扩展集合 —— RVA23U64强制含向量(v),RVA20U64无此要求。
    BASE_EXTENSIONS = frozenset("imafdc")
    RVA23_MARKER = "v"
    RVA23_PROFILE = "rva23u64"
    RVA20_PROFILE = "rva20u64"
    # 校验出来的"RVA23参数是否生效"结论,是否直接判定测试失败。
    # 目前为False(只记录):LLVM_RISCV_DEFAULT_EXTENSIONS并非上游LLVM参数,
    # 在未确认其来源/有效性的LLVM源码树上,该参数会被CMake静默忽略,
    # 此时判失败会让所有RVA23机器变红 —— 那是参数来源问题,不是真实缺陷。
    # 确认参数有效(或改用其他能让默认档生效的手段)后,把这里改成 True 即可。
    STRICT_PROFILE_CHECK = False

    def __init__(self, **kwargs):
        self.rpms = {'gcc', 'gcc-g++', 'gcc-gfortran', 'cmake', 'ninja-build'}
        self.believe_tmp: bool = kwargs.get('believe_tmp')
        self.path = Path('/root/osmts_tmp/llvm-project')
        self.directory: Path = kwargs.get('saved_directory') / 'llvmcase'
        self.riscv_profile = self.RVA20_PROFILE
        self.profile_reason = '未探测'
        self.profile_effective = None       # None=未校验/无法判断,True/False=校验结论
        self.profile_check_reason = '未校验'


    @staticmethod
    def _parse_isa_extensions(isa_string:str) -> set:
        """把 'rv64imafdcvh_zicsr_zifencei' 解析成 {'i','m','a','f','d','c','v','h','zicsr',...}。

        规则(依据内核实际输出格式):
        - 首个下划线之前是基础+单字母扩展,逐字符拆;
        - 之后每段是 z*/s* 多字母扩展,版本号(如 zbb2p0 的 2p0)需要剥掉。
        """
        isa_string = (isa_string or '').strip().lower()
        start = isa_string.find('rv64')
        if start < 0:
            start = isa_string.find('rv32')
        if start < 0:
            return set()
        rest = isa_string[start + 4:]
        parts = rest.split('_')

        extensions = {char for char in parts[0] if char.isalpha()}
        for part in parts[1:]:
            index = 0
            while index < len(part) and part[index].isalpha():
                index += 1
            if index:
                extensions.add(part[:index])
        return extensions


    def _isa_string_from_cpuinfo(self):
        """从 /proc/cpuinfo 读取ISA串,取第一个非空 isa 行。"""
        try:
            with open('/proc/cpuinfo', 'r', encoding='utf-8', errors='replace') as cpuinfo:
                for line in cpuinfo:
                    key, _, value = line.partition(':')
                    if key.strip() == 'isa' and value.strip():
                        return value.strip()
        except OSError:
            return ''
        return ''


    def detect_riscv_profile(self) -> tuple:
        """探测当前系统的RISC-V配置档,返回(profile, 判定理由)。

        探测不到或看不出档位时一律回退 RVA20,保证与改动前的构建行为一致:
        宁可保持旧行为,也不在不确定的情况下套用RVA23参数。
        """
        isa_string = self._isa_string_from_cpuinfo()
        if not isa_string:
            return self.RVA20_PROFILE, '未在/proc/cpuinfo中找到isa字段,回退RVA20'

        extensions = self._parse_isa_extensions(isa_string)
        missing_base = sorted(self.BASE_EXTENSIONS - extensions)
        if missing_base:
            return (self.RVA20_PROFILE,
                    f"ISA串缺少基础扩展{''.join(missing_base)},无法判定档位,回退RVA20")

        if self.RVA23_MARKER in extensions:
            return self.RVA23_PROFILE, f"ISA串含向量扩展({self.RVA23_MARKER}),判定为RVA23"
        return self.RVA20_PROFILE, f"ISA串不含向量扩展({self.RVA23_MARKER}),判定为RVA20"


    @staticmethod
    def _mem_available_mb() -> int:
        """读取 /proc/meminfo 的 MemAvailable(单位MB);读不到返回0。

        用 MemAvailable 而不是 MemFree:前者包含可回收的页缓存,
        后者在编译过程中会长期偏低,据此算并行度会过度保守。
        """
        try:
            with open('/proc/meminfo', 'r', encoding='utf-8', errors='replace') as meminfo:
                for line in meminfo:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) // 1024
        except (OSError, ValueError, IndexError):
            return 0
        return 0

    @classmethod
    def _safe_jobs(cls) -> int:
        """按可用内存推算安全的并行编译任务数。

        LLVM 单个编译进程峰值约 1.4GB(实测),故 并行度 = 可用内存 / 每任务预留。
        上限取 min(CPU核数, LLVM_MAX_JOBS):并行度超过核数没有收益。
        """
        import os
        cpu_jobs = os.cpu_count() or 1
        mem_mb = cls._mem_available_mb()
        if mem_mb <= 0:
            return max(1, min(cpu_jobs, LLVM_UNKNOWN_MEM_JOBS))
        mem_jobs = max(1, mem_mb // LLVM_MEM_PER_JOB_MB)
        return max(1, min(cpu_jobs, mem_jobs, LLVM_MAX_JOBS))

    def _build_args(self) -> str:
        """按探测到的配置档拼装构建命令。

        RVA20 与原命令逐字一致(零回归);仅 RVA23 追加默认扩展参数。
        注意:LLVM_RISCV_DEFAULT_EXTENSIONS 并非上游参数,是否需要取决于
        所用的LLVM源码树,详见 README/提交说明。
        并行度按可用内存推算(而非ninja默认的CPU核数),避免板上OOM。
        """
        jobs = self._safe_jobs()
        args = (f'cmake -S llvm -B build -DLLVM_PARALLEL_LINK_JOBS={jobs} '
                f'-DLLVM_PARALLEL_COMPILE_JOBS={jobs} '
                '-DLLVM_ENABLE_PROJECTS="clang" -DLLVM_TARGETS_TO_BUILD="RISCV" '
                '-DCMAKE_BUILD_TYPE="Release" -G Ninja')
        if self.riscv_profile == self.RVA23_PROFILE:
            args += f' -DLLVM_RISCV_DEFAULT_EXTENSIONS="{self.riscv_profile}"'
        return f'{args} && ninja -C build -j {jobs}'


    def _clang_target_features(self, extra_args:str = ''):
        """用构建出的clang做一次"只打印驱动参数"的探测,返回(输出文本, 返回值)。

        用 -### 而不是真实编译:驱动会打印将要传给cc1的 -target-feature 列表,
        既能看出默认档启用了哪些扩展,又不依赖完整的sysroot/交叉链接器。
        探测失败一律返回(文本, 非0),由调用方决定如何处理,绝不抛出。
        """
        probe = self.path / 'build' / '_osmts_profile_probe.c'
        try:
            probe.write_text("int main(void){return 0;}\n", encoding='utf-8')
            # 注意 extra_args 前后的空格:用 ' '.join 拼装,避免参数粘连
            clang_args = ' '.join(part for part in ('./bin/clang', extra_args, '-###') if part)
            completed = subprocess.run(
                f'{clang_args} -c {probe.name} -o /dev/null',
                cwd=self.path / 'build',
                shell=True, check=False,          # 校验失败不应让测试失败
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError as e:
            return f'无法执行探测编译:{e}', 1
        finally:
            probe.unlink(missing_ok=True)         # 不留临时文件
        return decode_output(completed.stdout), completed.returncode


    @staticmethod
    def _vector_enabled(driver_output:str) -> bool:
        """从驱动输出里判断向量扩展是否为开启状态。

        驱动以成对引号打印每个特性,形如 "-target-feature" "+v"(开启)
        或 "-target-feature" "-v"(关闭)。因此要找的字面量是 "+v"(加号在引号内)。
        """
        return '"+v"' in driver_output.replace(' ', '')


    def check_profile_effective(self) -> tuple:
        """校验RVA23构建参数是否真的生效,返回(结论, 说明)。

        两条探针:
        1. 默认档(不加-march)—— 构建出的clang默认是否已开向量?
           开了说明默认扩展参数生效;没开说明参数被忽略(上游LLVM的预期情况)。
        2. -march=rva23u64 —— 这个clang是否支持按RVA23档编译?
           用来区分"参数没生效"与"这版clang根本不支持rva23u64"。
        """
        default_output, default_rc = self._clang_target_features()
        if default_rc != 0:
            return None, f"默认档探测失败(返回值{default_rc}),无法判断参数是否生效"

        default_vector = self._vector_enabled(default_output)
        support_output, support_rc = self._clang_target_features('-march=rva23u64')
        supports_rva23 = (support_rc == 0) and self._vector_enabled(support_output)

        if default_vector:
            return True, "构建出的clang默认已开启向量(v),RVA23参数生效"
        if supports_rva23:
            return (False,
                    "构建出的clang默认未开启向量(v),RVA23参数未生效;"
                    "但该clang支持-march=rva23u64,说明是参数被忽略而非工具链不支持")
        return (False,
                "构建出的clang默认未开启向量(v),且不支持-march=rva23u64,"
                "该clang无法按RVA23档编译")


    def verify_profile(self):
        """校验并输出结论。RVA20档不传参数,无需校验。"""
        if self.riscv_profile != self.RVA23_PROFILE:
            self.profile_effective = None
            self.profile_check_reason = f"{self.riscv_profile}档未传默认扩展参数,无需校验"
            print(f"RVA23参数校验:跳过({self.profile_check_reason})")
            return

        self.profile_effective, self.profile_check_reason = self.check_profile_effective()
        print(f"RVA23参数校验:{self.profile_check_reason}")
        if self.STRICT_PROFILE_CHECK and self.profile_effective is not True:
            raise DefaultError(
                f"llvmcase测试出错.RVA23默认扩展参数未生效:{self.profile_check_reason}"
            )


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(parents=True,exist_ok=True)
        if self.path.exists() and self.believe_tmp:
            pass
        else:
            shutil.rmtree(self.path, ignore_errors=True)
            # 拉取源码
            try:
                subprocess.run(
                    "GIT_TERMINAL_PROMPT=0 git clone https://github.com/llvm/llvm-project.git",
                    cwd="/root/osmts_tmp",
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise GitCloneError(e.returncode,'https://github.com/llvm/llvm-project.git',decode_output(e.stderr))

        # 按本机架构档决定构建参数
        self.riscv_profile, self.profile_reason = self.detect_riscv_profile()
        build_args = self._build_args()
        print(f"检测到RISC-V配置档:{self.riscv_profile}({self.profile_reason})")
        print(f"可用内存:{self._mem_available_mb()}MB,"
              f"按每个编译进程{LLVM_MEM_PER_JOB_MB}MB推算并行度:{self._safe_jobs()}")
        print(f"llvm构建命令:{build_args}")

        # 构建耗时以小时计:已有完整构建成果时直接复用,避免中断后从零重来
        build_mark = self.path / 'build' / LLVM_BUILD_MARK
        if build_mark.exists():
            print(f"复用上次已完成的llvm构建:{self.path / 'build'}")
            return

        # 编译llvm。stdout+stderr 全部落盘:
        # LLVM 构建的报错大多走 stdout,只收 stderr 会丢失真正的失败原因;
        # 且数小时的构建输出不可能全靠异常携带,必须留完整日志供事后分析。
        self.build_log = self.directory / LLVM_BUILD_LOG
        print(f"开始构建llvm,完整日志:{self.build_log}")
        try:
            # stdout与stderr都捕获:LLVM构建的报错大多走stdout,
            # 只收 stderr 会丢失真正的失败原因(实测只收到cmake阶段的无害提示)。
            # 用 PIPE 而非直接写文件对象:run() 会读完全部输出才返回,
            # 不存在管道写满阻塞;这样失败时才能把输出写盘并取出尾部。
            completed = subprocess.run(
                args=build_args,
                cwd=self.path,
                shell=True,check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as e:
            self._save_build_log(decode_output(e.stdout))
            raise DefaultError(
                f"llvmcase测试出错.编译llvm失败(返回码{e.returncode})."
                f"完整日志见{self.build_log}.日志末尾:\n{self._build_log_tail()}"
            )
        self._save_build_log(decode_output(completed.stdout))
        build_mark.touch()

    def _save_build_log(self, content:str):
        """把构建输出完整落盘,供失败后事后分析(数小时的输出不可能全靠异常携带)。"""
        try:
            self.build_log.write_text(content, encoding='utf-8', errors='replace')
        except OSError as e:
            print(f"[llvmcase] 警告:写入构建日志失败:{e}")

    def _build_log_tail(self) -> str:
        """取构建日志尾部若干行,用于异常信息中给出足够定位的上下文。"""
        log_path = getattr(self, 'build_log', None)
        if log_path is None or not log_path.exists():
            return '(未找到构建日志)'
        try:
            lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError as e:
            return f'(读取构建日志失败:{e})'
        tail = lines[-LLVM_BUILD_LOG_TAIL_LINES:]
        omitted = len(lines) - len(tail)
        prefix = f'(共{len(lines)}行,省略前{omitted}行)\n' if omitted > 0 else ''
        return prefix + '\n'.join(tail)

        # 编译完成后校验RVA23参数是否真的生效(构建成功不代表参数被接受)
        self.verify_profile()


    def run_test(self):
        try:
            run_clang = subprocess.run(
                "bin/clang -v",
                cwd=self.path / "build",
                shell=True,check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            # stderr=STDOUT,e.stderr 恒为 None;诊断信息已合并进 e.stdout
            raise RunError(e.returncode,decode_output(e.stdout) or decode_output(e.stderr))
        else:
            with open(self.directory / 'llvmcase.log', 'w', encoding='utf-8') as file:
                # 把探测与校验结论写进报告:否则事后无法判断本次构建用的是哪个档、
                # 以及RVA23参数到底有没有生效
                file.write(f"RISC-V配置档: {self.riscv_profile}\n")
                file.write(f"判定依据: {self.profile_reason}\n")
                file.write(f"构建命令: {self._build_args()}\n")
                file.write(f"参数有效性: {self.profile_check_reason}\n")
                file.write("-" * 60 + "\n")
                file.write(decode_output(run_clang.stdout))


    def run(self):
        print('开始进行llvmcase测试')
        self.pre_test()
        self.run_test()
        print('llvm测试结束')
