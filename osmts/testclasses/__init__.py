from testclasses.libmicro import Libmicro
from testclasses.unixbench import Unixbench
from testclasses.stream import Stream
from testclasses.iozone import Iozone
from testclasses.fio import Fio
from testclasses.nmap import Nmap
from testclasses.ltp import Ltp
from testclasses.ltp_cve import Ltp_cve
from testclasses.netperf import Netperf
from testclasses.lmbench import Lmbench
from testclasses.trinity import Trinity
from testclasses.ltp_stress import Ltp_stress
from testclasses.ltp_posix import Ltp_posix
from testclasses.llvmcase import Llvmcase
from testclasses.dejagnu import DejaGnu, DejaGnuGcc, DejaGnuGxx, DejaGnuGfortran
from testclasses.anghabench import AnghaBench
from testclasses.csmith import Csmith
from testclasses.jotai import Jotai
from testclasses.jtreg import Jtreg, Jtreg8, Jtreg11, Jtreg17, Jtreg21
from testclasses.openscap import OpenSCAP
from testclasses.gpgcheck import GpgCheck
from testclasses.yarpgen import Yarpgen
from testclasses.secureguardian import SecureGuardian
from testclasses.mmtests import MMTests
from testclasses.api_sanity_checker import APISanityChecker
from testclasses.wrk import Wrk
from testclasses.ycsb import YCSB
from testclasses.sysbench import sysBench
from testclasses.redis_benchmark import redisBenchMark
from testclasses.benchmarksql import BenchMarkSQL
from testclasses.tpch import TPC_H
from testclasses.sha256sum import Sha256sum


osmts_tests = {
    "unixbench": (
        Unixbench
    ),
    "nmap": (
        Nmap
    ),
    "lmbench": (
        Lmbench
    ),
    "stream": (
        Stream
    ),
    "ltp_stress": (
        Ltp_stress
    ),
    "iozone":(
        Iozone
    ),
    "libmicro":(
        Libmicro
    ),
    "wrk":(
        Wrk
    ),
    "fio":(
        Fio
    ),
    "netperf": (
        Netperf
    ),
    "trinity": (
        Trinity
    ),
    "ltp":(
        Ltp
    ),
    "ltp_cve":(
        Ltp_cve
    ),
    "ltp_posix":(
        Ltp_posix
    ),
    "gpgcheck": (
        GpgCheck
    ),
    "dejagnu":(
        DejaGnu
    ),
    "dejagnu_gcc":(
        DejaGnuGcc
    ),
    "dejagnu_g++":(
        DejaGnuGxx
    ),
    "dejagnu_gfortran":(
        DejaGnuGfortran
    ),
    "yarpgen": (
        Yarpgen
    ),
    "llvmcase": (
        Llvmcase
    ),
    "anghabench":(
        AnghaBench
    ),
    "csmith":(
        Csmith
    ),
    "jotai":(
        Jotai
    ),
    "jtreg":(
        Jtreg
    ),
    "jtreg_8":(
        Jtreg8
    ),
    "jtreg_11":(
        Jtreg11
    ),
    "jtreg_17":(
        Jtreg17
    ),
    "jtreg_21":(
        Jtreg21
    ),
    "openscap":(
        OpenSCAP
    ),
    "secureguardian":(
        SecureGuardian
    ),
    "mmtests":(
        MMTests
    ),
    "api-sanity-checker":(
        APISanityChecker
    ),
    "ycsb":(
        YCSB
    ),
    "redis_benchmark":(
        redisBenchMark
    ),
    "sysbench":(
        sysBench
    ),
    "benchmarksql":(
        BenchMarkSQL
    ),
    "tpch":(
        TPC_H
    ),
    "sha256sum":(
        Sha256sum
    )
}
