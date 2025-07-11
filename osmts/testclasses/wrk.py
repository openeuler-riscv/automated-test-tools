import os
import shutil
from pathlib import Path
import re,subprocess
from openpyxl import Workbook

from .errors import RunError,SummaryError



class Wrk:
    def __init__(self,**kwargs):
        self.rpms = {'wrk'}
        self.directory:Path = kwargs.get('saved_directory') / 'wrk'
        self.wrk_seconds:int = kwargs.get('wrk_second',60)
        self.test_result = ''


    def pre_test(self):
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)


    def run_test(self):
        try:
            wrk = subprocess.run(
                f"wrk -t{os.cpu_count()} -c1023 -d60s --latency http://www.baidu.com",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RunError(e.returncode,'wrk命令运行报错,报错信息:' + e.stderr.decode('utf-8'))

        self.test_result = wrk.stdout.decode('utf-8')
        with open(self.directory / 'wrk.txt','w') as file:
            file.write(self.test_result)


    def result2summary(self):
        wb = Workbook()
        ws = wb.active
        ws.title = 'wrk'
        ws.append(['Thread Stats','Avg(平均值)','Stdev(标准差)','Max(最大值)','+/- Stdev(正负一个标准差所占比例)'])

        # Latency   265.57ms  382.20ms   2.00s    85.56%
        Latency = re.search(r"Latency\s+(\d+\.\d+)ms\s+(\d+\.\d+)ms\s+(\d+\.\d+)s\s+(\d+\.\d+)%",self.test_result).groups()
        ws.append(['Latency(延迟)',Latency[0]+'ms',Latency[1]+'ms',Latency[2]+'s',Latency[3]+'%'])

        # Req/Sec    25.06     22.19   310.00     84.21%
        RS = re.search(r"eq/Sec\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)%",self.test_result).groups()
        ws.append(['Req/Sec(每秒请求数)',RS[0],RS[1],RS[2],RS[3]+'%'])

        ws.append(['-','-','-','-','-'])

        # Latency Distribution
        ws.append(['Latency Distribution(延迟分布)'])
        for LD in ('50%','75%','90%','99%'):
            time = re.search(rf"{LD}\s+(\d+\.\d+)(ms|s)",self.test_result).group(1)
            ws.append([LD,''.join(time)])

        ws.append(['-', '-', '-', '-', '-'])

        # 40387 requests in 1.00m, 1.15GB read
        requests,read = re.search(r"(\d+) requests in 1.00m, (\d+\.\d+..) read",self.test_result).groups()
        ws.append([f"在{self.wrk_seconds}秒 内处理了{requests} 个请求，读取了{read}数据"])

        # Socket errors: connect 3, read 131564, write 0, timeout 1836
        connect,read,write,timeout = re.search(r"Socket errors: connect (\d+), read (\d+), write (\d+), timeout (\d+)",self.test_result).groups()
        ws.append(['发生错误统计','connect','read','write','timeout'])
        ws.append(['',connect,read,write,timeout])

        ws.append(['-', '-', '-', '-', '-'])

        # Requests/sec:    671.87
        requests = re.search(r"Requests/sec:\s+(\d+\.\d+)",self.test_result).group(1)
        ws.append([f'平均每秒处理请求数:',requests])

        # Transfer/sec:     19.57MB
        transfer = re.search(r"Transfer/sec:\s+(\d+\.\d+..)",self.test_result).group(1)
        ws.append([f'平均每秒读取数据:',transfer])

        wb.save(self.directory / 'wrk.xlsx')


    def run(self):
        print('开始进行wrk测试')
        self.pre_test()
        self.run_test()
        try:
            self.result2summary()
        except Exception as e:
            logFile = self.directory / 'wrk_summary_error.log'
            with open(logFile,'w') as log:
                log.write(str(e))
            raise SummaryError(logFile)
        print('wrk测试结束')