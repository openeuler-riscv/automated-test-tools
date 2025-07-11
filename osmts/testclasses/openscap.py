import re
import subprocess
from pathlib import Path
from openpyxl import Workbook



class OpenSCAP:
    def __init__(self, **kwargs):
        self.rpms = {'penscap-scanner','scap-security-guide'}
        self.scap_content = Path("/usr/share/xml/scap/ssg/content/")
        self.scap_files = (
            ""
        )
        self.directory: Path = kwargs.get('saved_directory') / 'OpenSCAP'
        # 当前系统的openEuler release(25,24,23)
        self.current_release:str = ''
        self.test_result:str = ''


    def pre_test(self):
        if not self.directory.exists():
            self.directory.mkdir(parents=True)
        try:
            with open('/etc/openEuler-release','r') as file:
                self.current_release = file.read().rstrip('\n').rsplit(' ')[-1].split('.')[0]
        except FileNotFoundError:
            self.current_release = '24'
        # 目前只支持22.03和24.03
        if self.current_release in ('22','24'):
            self.scap_content = 24


    def run_test(self):
        oscap = subprocess.run(
            f"oscap xccdf eval "
            f"--profile xccdf_org.ssgproject.content_profile_standard "
            f"--results {self.directory}/scan_results.xml "
            f"--report {self.directory}/scan_report.html "
            f"/usr/share/xml/scap/ssg/content/ssg-openeuler{self.current_release}03-ds.xml",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if oscap.returncode != 0:
            print(f"OpenSCAP测试出错.oscap运行失败,报错信息:{oscap.stderr.decode('utf-8')}")
            return
        self.test_result = oscap.stdout.decode('utf-8')


    def result2summary(self):
        wb = Workbook()
        ws = wb.active
        ws.title = 'OpenSCAP'
        ws.append(['Title','Rule','Result'])
        titles = re.findall(r"Title {3}(.+)",self.test_result)
        rules = re.findall(r"Rule {3}(.+)",self.test_result)
        results = re.findall(r"Result {3}(.+)",self.test_result)
        for i in range(len(titles)):
            ws.append([titles[i],rules[i],results[i]])
        wb.save(self.directory / 'openscap.xlsx')


    def run(self):
        print('开始进行OpenSCAP测试')
        self.pre_test()
        self.run_test()
        self.result2summary()
        print('OpenSCAP测试结束')
