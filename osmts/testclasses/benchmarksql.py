from openpyxl.workbook import Workbook
from pystemd.systemd1 import Unit
from pathlib import Path
import re,os,time
import requests,tarfile
import pymysql,psycopg2
import subprocess,shutil
from io import BytesIO

from .errors import DefaultError,RunError


headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0',
    'referer': 'https://gitee.com/April_Zhao/osmts',
}


class BenchMarkSQL:
    def __init__(self, **kwargs):
        self.rpms = {'postgresql-server','mysql-server','java'}
        self.directory: Path = kwargs.get('saved_directory') / 'benchmarksql'
        self.path:Path = Path('/root/osmts_tmp/benchmarksql')
        self.mysql_path: Path = self.path / 'mysql'
        self.postgresql_path: Path = self.path / 'postgresql'

        self.mysql_test_result:str = ''
        self.postgres_test_result:str = ''


    def pre_test(self):
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)

        # 初始化MySQL
        self.mysqld:Unit = Unit('mysqld.service',_autoload=True)
        try:
            self.mysqld.Unit.Start(b'replace')
        except:
            time.sleep(5)
            self.mysqld.load(force=True)
            self.mysqld.Unit.Start(b'replace')
        time.sleep(5)
        if self.mysqld.Unit.ActiveState != b'active':
            time.sleep(5)
            if self.mysqld.Unit.ActiveState != b'active':
                raise DefaultError(f"benchmarksql测试出错.开启mysqld.service失败,退出测试.")

        try:
            self.mysql_conn = pymysql.connect(
                host='localhost',
                port=3306,
                user='root',
                passwd='',
            )
        except Exception as e:
            self.mysql_conn = pymysql.connect(
                host='localhost',
                port=3306,
                user='root',
                passwd='123456',
            )
        cursor = self.mysql_conn.cursor()
        cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY '123456';")
        cursor.execute("DROP DATABASE IF EXISTS tpcc;")
        cursor.execute("CREATE DATABASE IF NOT EXISTS tpcc;")
        cursor.close()

        # 获取benchmark for mysql
        response = requests.get(
            url="https://gitee.com/April_Zhao/osmts/releases/download/v1.0/mysql.tar.xz",
            headers=headers,
        )
        with tarfile.open(fileobj=BytesIO(response.content)) as tar:
            tar.extractall(self.path)

        # -------------------------------------------------------

        # 初始化postgresql
        try:
            subprocess.run(
                "/usr/bin/postgresql-setup initdb",
                shell=True,check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise DefaultError(f"benchmarksql测试出错.初始化postgresql数据库失败,报错信息:{e.stderr.decode('utf-8')}")

        self.postgresql:Unit = Unit('postgresql.service',_autoload=True)
        try:
            self.postgresql.Unit.Start(b'replace')
        except Exception:
            time.sleep(5)
            self.postgresql.load(force=True)
            self.postgresql.Unit.Start(b'replace')
        time.sleep(5)
        if self.postgresql.Unit.ActiveState != b'active':
            time.sleep(5)
            if self.postgresql.Unit.ActiveState != b'active':
                raise DefaultError("benchmarksql测试出错.开启postgresql.service失败.")

        try:
            self.postgresql_conn = pymysql.connect(
                host='localhost',
                port=5432,
                user='root',
                passwd='',
            )
        except Exception as e:
            try:
                self.postgresql_conn = pymysql.connect(
                    host='localhost',
                    port=5432,
                    user='postgres',
                    passwd='123456',
                )
            except Exception as e:
                self.postgresql_conn = pymysql.connect(
                    host='localhost',
                    port=5432,
                    user='postgres',
                    passwd='postgres',
                )
        cursor = self.postgresql_conn.cursor()
        cursor.execute("ALTER USER postgres WITH PASSWORD '123456';")
        cursor.execute("DROP DATABASE IF EXISTS tpcc;")
        cursor.execute("CREATE DATABASE IF NOT EXISTS tpcc;")

        # 获取benchmark for postgresql
        response = requests.get(
            url="https://gitee.com/April_Zhao/osmts/releases/download/v1.0/postgresql.tar.xz",
            headers=headers,
        )
        with tarfile.open(fileobj=BytesIO(response.content)) as tar:
            tar.extractall(self.path)



    def run_test(self):
        try:
            mysql = subprocess.run(
                f"./runDatabaseBuild.sh mysql.properties",
                cwd=self.mysql_path / 'run',
                shell=True,check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RunError(e.returncode,e.stderr.decode('utf-8'))
        self.mysql_test_result = mysql.stdout.decode('utf-8')
        with open(self.directory / 'mysql.log', 'w') as log:
            log.write(self.mysql_test_result)

        try:
            postgresql = subprocess.run(
                f"./runDatabaseBuild.sh postgresql.properties",
                cwd=self.postgresql_path / 'run',
                shell=True,check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RunError(e.returncode, e.stderr.decode('utf-8'))
        self.postgres_test_result = postgresql.stdout.decode('utf-8')
        with open(self.directory / 'postgresql.log', 'w') as log:
            log.write(self.postgres_test_result)


    def result2summary(self):
        wb = Workbook()
        ws1 = wb.active
        ws1.title = 'mysql'

        ws2 = wb.create_sheet(title='postgresql')


        wb.save(self.directory / 'benchmarksql.log')


    def post_test(self):
        self.mysqld.Unit.Stop(b'replace')
        subprocess.run(
            "dnf remove -y mysql-server postgresql-server",shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
        )


    def run(self):
        print('开始进行benchmarksql测试')
        self.pre_test()
        self.run_test()
        self.result2summary()
        self.post_test()
        print('benchmarksql测试结束')