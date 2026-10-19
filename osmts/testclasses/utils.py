"""testclasses 的共享工具模块。

本模块**只依赖标准库**,目的是保持零依赖:
- 不放进 testclasses/errors.py:那里 `from pystemd.dbusexc import *`,
  会把 pystemd 这个系统包依赖传染给所有只想用工具函数的调用方;
- 不放进 testclasses/__init__.py:那里要导入全部测试类,会形成循环导入。

新增工具函数时请遵守同样的零依赖约束。
"""

UNKNOWN_OUTPUT = "(无输出)"

_DEFAULT_ERRORS = "replace"


def decode_output(value, default: str = UNKNOWN_OUTPUT) -> str:
    """把 subprocess 的 stdout/stderr 安全地转成字符串。

    解决两类真实缺陷(原先散落各处的 `x.decode('utf-8')`):

    1. `stderr=DEVNULL` / `stderr=STDOUT` 时 subprocess 给出的是 None,
       裸 `.decode()` 抛 AttributeError,把真实报错覆盖成属性错误;
    2. 命令输出不保证是合法 UTF-8,裸 `.decode('utf-8')` 抛 UnicodeDecodeError,
       同样把真实报错覆盖掉。

    语义区分(重要):
    - 报错信息用途:`decode_output(e.stderr)` —— None 变成 "(无输出)",有诊断价值;
    - 结果数据用途:`decode_output(x, default="")` —— None 保持为空,
      否则哨兵值是真值,会污染 `if x.strip():` 这类判断。

    bytes/bytearray/memoryview -> utf-8 解码,非法字节以 U+FFFD 替换
    str                        -> 原样返回
    None                       -> default
    其他类型                   -> str(value)
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors=_DEFAULT_ERRORS)
    return str(value)
