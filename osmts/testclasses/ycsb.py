from openpyxl.workbook import Workbook
from pystemd.systemd1 import Unit
from pathlib import Path
import re,time
import subprocess,shutil

from .errors import DefaultError,GitCloneError,RunError,SummaryError



class YCSB: # Yahoo！Cloud Serving Benchmark
    def __init__(self, **kwargs):
        self.rpms = {'redis','java','maven'}
        self.believe_tmp: bool = kwargs.get('believe_tmp')
        self.path = Path('/root/osmts_tmp/YCSB')
        self.directory: Path = kwargs.get('saved_directory') / 'ycsb'
        self.ycsb:Path = self.path / 'bin/ycsb'
        self.workloada:Path = self.path / 'workloads/workloada'
        self.test_result:str = ''


    def pre_test(self):
        self.redis:Unit = Unit(b'redis.service',_autoload=True)
        try:
            self.redis.Unit.Start(b'replace')
        except Exception:
            self.redis.Unit.Start(b'replace')
        time.sleep(5)
        if self.redis.Unit.ActiveState != b'active':
            time.sleep(5)
            if self.redis.Unit.ActiveState != b'active':
                raise DefaultError("redis.service开启失败,退出测试.")

        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)

        if self.path.exists() and self.believe_tmp:
            pass
        else:
            shutil.rmtree(self.path,ignore_errors=True)
            try:
                subprocess.run(
                    "git clone https://gitee.com/zhtianyu/ycsb.git",
                    cwd="/root/osmts_tmp",
                    shell=True,check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as e:
                raise GitCloneError(e.returncode,'https://gitee.com/zhtianyu/ycsb.git',e.stderr.decode('utf-8'))
        try:
            subprocess.run(
                f"mvn -pl site.ycsb:redis -binding -am clean package",
                cwd=self.path,
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"mvn命令运行失败,报错信息:{e.stderr.decode('utf-8')}")


        # 修改配置文件加入redis
        with open(self.workloada,mode='a+') as workloada:
            workloada.writelines(['redis.host=127.0.0.1\n','redis.port=6379\n'])

        # 加载数据
        try:
            subprocess.run(
                f"bin/ycsb load redis -threads 100 -P workloads/workloada",
                cwd=self.path,
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError("ycsb load redis加载数据失败,报错信息:{load.stderr.decode('utf-8')}")


    def run_test(self):
        try:
            run = subprocess.run(
                f"bin/ycsb run redis -threads 100 -P workloads/workloada",
                cwd=self.path,
                shell=True,check=True,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RunError(e.returncode,e.stderr.decode('utf-8'))
        else:
            self.test_result = run.stdout.decode('utf-8')
            with open(self.directory / 'ycsb.log','w') as log:
                log.write(self.test_result)


    def result2summary(self):
        wb = Workbook()
        ws = wb.active
        ws.title = 'ycsb'
        ws.append(['key','value'])

        # 总体指标
        ws.append(['总体指标','---'])
        runtime = re.search(r"\[OVERALL\], RunTime\(ms\), (\d+)",self.test_result)
        ws.append(['测试过程耗时:',runtime.group(1) + 'ms'])

        throughput = re.search(r"\[OVERALL\], Throughput\(ops/sec\), (\d+\.\d+)",self.test_result)
        ws.append(['测试过程中的吞吐量:',throughput.group(1) + 'ops/sec'])

        ws.append(['',''])

        # 垃圾回收(GC机制)指标
        ws.append(['垃圾回收(GC机制)指标','---'])
        gc_count_copy = re.search(r"\[TOTAL_GCS_Copy\], Count, (\d+)",self.test_result)
        ws.append(['发生Copy类型的GC次数:',gc_count_copy.group(1) + '次'])

        gc_time_copy = re.search(r"\[TOTAL_GC_TIME_Copy\], Time\(ms\), (\d+)",self.test_result)
        ws.append(['Copy类型的GC共耗时:',gc_time_copy.group(1) + 'ms'])

        gc_time_copy_percent = re.search(r"\[TOTAL_GC_TIME_%_Copy\], Time\(%\), (\d+\.\d+)",self.test_result)
        ws.append(['Copy类型的GC占程序总耗时的百分比:',gc_time_copy_percent.group(1) + '%'])

        gc_count_marksweepcompact = re.search(r"\[TOTAL_GCS_MarkSweepCompact\], Count, (\d+)",self.test_result)
        ws.append(['发生MarkSweepCompact类型GC次数:',gc_count_marksweepcompact.group(1) + '次'])

        gc_time_marksweepcompact = re.search(r"\[TOTAL_GC_TIME_MarkSweepCompact\], Time\(ms\), (\d+)",self.test_result)
        ws.append(['MarkSweepCompact类型的GC共耗时:',gc_time_marksweepcompact.group(1) + 'ms'])

        gc_time_marksweepcompact_percent = re.search(r"\[TOTAL_GC_TIME_%_MarkSweepCompact]\, Time\(%\), (\d+\.\d+)",self.test_result)
        ws.append(['MarkSweepCompact类型的GC占程序总耗时的百分比:',gc_time_marksweepcompact_percent.group(1) + '%'])

        gc_count = re.search(r"\[TOTAL_GCs\], Count, (\d+)",self.test_result)
        ws.append(['总共发生GC次数:',gc_count.group(1) + '次'])

        gc_time = re.search(r"\[TOTAL_GC_TIME\], Time\(ms\), (\d+)",self.test_result)
        ws.append(['GC总耗时:',gc_time.group(1) + 'ms'])

        gc_percent = re.search(r"\[TOTAL_GC_TIME_%\], Time\(%\), (\d+\.\d+)",self.test_result)
        ws.append(['GC占程序总耗时的百分比:',gc_percent.group(1) + '%'])

        ws.append(['',''])

        # 读(READ)取操作指标
        ws.append(['读取操作(read)指标','---'])

        read_Operations = re.search(r"\[READ\], Operations, (\d+)",self.test_result)
        ws.append(['共执行读操作次数:',read_Operations.group(1) + '次'])

        read_AverageLatency = re.search(r"\[READ\], AverageLatency\(us\), (\d+\.\d+)",self.test_result)
        ws.append(['每次读操作的平均时延:',read_AverageLatency.group(1) + 'us'])

        read_MinLatency = re.search(r"\[READ\], MinLatency\(us\), (\d+)",self.test_result)
        ws.append(['每次读操作的最小时延:',read_MinLatency.group(1) + 'us'])

        read_MaxLatency = re.search(r"\[READ\], MaxLatency\(us\), (\d+)",self.test_result)
        ws.append(['每次读操作的最大时延:',read_MaxLatency.group(1) + 'us'])

        read_PercentileLatency_50 = re.search(r"\[READ\], 50thPercentileLatency\(us\), (\d+)",self.test_result)
        read_PercentileLatency_95 = re.search(r"\[READ\], 95thPercentileLatency\(us\), (\d+)", self.test_result)
        read_PercentileLatency_99 = re.search(r"\[READ\], 99thPercentileLatency\(us\), (\d+)", self.test_result)
        ws.append([f'50% 读操作的时延在{read_PercentileLatency_50.group(1)}us以内',f'95% 读操作的时延在{read_PercentileLatency_95.group(1)}us以内',f'99% 读操作的时延在{read_PercentileLatency_99.group(1)}us以内'])

        read_return_ok = re.search(r"\[READ\], Return=OK, (\d+)",self.test_result)
        ws.append(['read返回成功,操作数:',read_return_ok.group(1)])

        ws.append(['',''])

        # 清理(CLEANUP)操作指标
        ws.append(['清理操作(clean up)指标', '---'])

        cleanup_Operations = re.search(r"\[CLEANUP\], Operations, (\d+)",self.test_result)
        ws.append(['执行了清理操作的次数:',cleanup_Operations.group(1) + '次'])

        cleanup_AverageLatency = re.search(r"\[CLEANUP\], AverageLatency\(us\), (\d+\.\d+)",self.test_result)
        ws.append(['每次清理操作的平均时延:',cleanup_AverageLatency.group(1) + 'us'])

        cleanup_MinLatency = re.search(r"\[CLEANUP\], MinLatency\(us\), (\d+)",self.test_result)
        ws.append(['每次清理操作的最小时延:',cleanup_MinLatency.group(1) + 'us'])

        cleanup_MaxLatency = re.search(r"\[CLEANUP\], MaxLatency\(us\), (\d+)",self.test_result)
        ws.append(['每次清理操作的最小时延:',cleanup_MaxLatency.group(1) + 'us'])

        cleanup_PercentileLatency_50 = re.search(r"\[CLEANUP\], 50thPercentileLatency\(us\), (\d+)",self.test_result)
        cleanup_PercentileLatency_95 = re.search(r"\[CLEANUP\], 95thPercentileLatency\(us\), (\d+)", self.test_result)
        cleanup_PercentileLatency_99 = re.search(r"\[CLEANUP\], 99thPercentileLatency\(us\), (\d+)", self.test_result)
        ws.append([f'50% 清理操作的时延在{cleanup_PercentileLatency_50.group(1)}us以内',f'95% 清理操作的时延在{cleanup_PercentileLatency_95.group(1)}us以内',f'99% 清理操作的时延在{cleanup_PercentileLatency_99.group(1)}us以内'])

        ws.append(['',''])

        # 更新操作指标
        ws.append(['更新操作(update)指标','---'])
        update_Operations = re.search(r"\[UPDATE\], Operations, (\d+)",self.test_result)
        ws.append(['执行了更新操作的次数:',update_Operations.group(1) + '次'])

        update_AverageLatency = re.search(r"\[UPDATE\], AverageLatency\(us\), (\d+\.\d+)",self.test_result)
        ws.append(['每次更新操作的平均时延:',update_AverageLatency.group(1) + 'us'])

        update_MinLatency = re.search(r"\[UPDATE\], MinLatency\(us\), (\d+)",self.test_result)
        ws.append(['每次更新操作的最小时延:',update_MinLatency.group(1) + 'us'])

        update_MaxLatency = re.search(r"\[UPDATE\], MaxLatency\(us\), (\d+)", self.test_result)
        ws.append(['每次更新操作的最小时延:', update_MaxLatency.group(1) + 'us'])

        update_PercentileLatency_50 = re.search(r"\[UPDATE\], 50thPercentileLatency\(us\), (\d+)",self.test_result)
        update_PercentileLatency_95 = re.search(r"\[UPDATE\], 95thPercentileLatency\(us\), (\d+)", self.test_result)
        update_PercentileLatency_99 = re.search(r"\[UPDATE\], 99thPercentileLatency\(us\), (\d+)", self.test_result)
        ws.append([f'50% 更新操作的时延在{update_PercentileLatency_50.group(1)}us以内',f'95% 更新操作的时延在{update_PercentileLatency_95.group(1)}us以内',f'99% 更新操作的时延在{update_PercentileLatency_99.group(1)}us以内'])

        update_return_ok = re.search(r"\[UPDATE\], Return=OK, (\d+)",self.test_result)
        ws.append(['update成功,操作数:',update_return_ok.group(1)])

        wb.save(self.directory / 'ycsb.xlsx')



    def post_test(self):
        self.redis.Unit.Stop(b'replace')
        subprocess.run(
            "dnf remove -y redis",shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
        )


    def run(self):
        print("开始进行ycsb测试")
        self.pre_test()
        self.run_test()
        try:
            self.result2summary()
        except Exception as e:
            logFile = self.directory / 'ycsb_summary_error.log'
            with open(logFile,'w') as log:
                log.write(str(e))
            raise SummaryError(logFile)
        self.post_test()
        print("ycsb测试结束")