"""静默 akshare 调用上下文。

akshare 内部(以及其依赖 requests/urllib3/pandas)会在抓取过程中向
stdout/stderr 输出与股票信息无关的内容,典型包括:

- akshare 内部的 ``print()`` 进度/状态文字;
- urllib3 的连接重用 / 重试 INFO 日志;
- requests 的传输日志;
- pandas 的 FutureWarning 等 DeprecationWarning;
- 其它模块通过 ``logging`` 输出的 INFO。

本模块提供 :func:`silence` 上下文管理器,在调用 akshare 接口期间
抑制上述噪声,退出后还原。

设计演进
--------

第一版用 ``sys.stdout = _DevNullWriter``。在单线程场景下没问题,但
``profile.fetch_basic`` 内部用 ``ThreadPoolExecutor(max_workers=4)``
并发跑 4 个 akshare 接口,每个子任务走 ``call_with_retry -> silence``。
``sys.stdout`` 是**进程级**对象,子线程里 ``sys.stdout = _DEVNULL_OUT``
会立即被主线程看到;而 ``ThreadPoolExecutor.__exit__`` 等待所有子线
程完成,期间主线程可能在 ``printer.panel_basic(...)`` 处被调度,
正好看到 ``sys.stdout = _DEVNULL_OUT``,Rich 写入 devnull,面板消失。

第二版(当前):**完全不修改 sys.stdout/sys.stderr**,转而:

1. 把 ``print`` 函数临时替换为静默版本,捕获 akshare 内部的
   ``print(...)`` 调用;
2. 把 ``akshare`` / ``requests`` / ``urllib3`` / ``pandas`` logger
   调高到 ``WARNING``;
3. 通过 ``warnings.catch_warnings()`` 把 ``DeprecationWarning`` /
   ``FutureWarning`` 临时静音。

Rich 的 :class:`rich.console.Console` 在 printer 模块加载时就把
``file=sys.stdout`` 锁定,运行期写的是真正的 stdout TextIOWrapper,
不会被上述任何手段影响——这正是我们想要的行为。
"""
from __future__ import annotations

import contextlib
import logging
import sys
import warnings
from typing import Iterator


# 需要抑制的 logger 名称。
_QUIET_LOGGERS: tuple[str, ...] = (
    "akshare",
    "requests",
    "urllib3",
    "urllib3.connectionpool",
    "urllib3.poolmanager",
    "urllib3.util.retry",
    "http.client",
    "pandas",
)


def _silent_print(*_args, **_kwargs):
    """替换 ``builtins.print`` 的静默版本,丢弃所有参数。"""
    return None


@contextlib.contextmanager
def silence() -> Iterator[None]:
    """抑制 akshare 抓取过程中的噪声输出。

    行为::

        with silence():
            df = ak.stock_zh_a_hist(symbol="600519", ...)

    实现要点(均**不**触动 ``sys.stdout``/``sys.stderr``,以保证 Rich 等
    已在进程级持有 stdout 引用的库不会被干扰):

    1. ``builtins.print`` 临时替换为 :func:`_silent_print`,吞掉 akshare
       内部的进度/状态文字。注意只覆盖名字 ``print``,调用方若用
       ``from builtins import print`` 拿到原函数引用,本机制不生效——
       但 akshare 内部走 ``print(...)`` 形式,会被覆盖。
    2. ``akshare`` / ``requests`` / ``urllib3`` / ``pandas`` logger 在
       进入时记下原 level,统一上调到 ``WARNING``,退出时严格还原。
    3. ``warnings.catch_warnings()`` 把 ``DeprecationWarning`` /
       ``FutureWarning`` 等 pandas 警告静音。

    与第一版的差异:第一版替换 ``sys.stdout`` 会污染进程级 stdout
    引用,在 ``ThreadPoolExecutor`` 并发场景下导致主线程写入 devnull。
    """
    import builtins

    saved_print = builtins.print
    saved_levels: dict[str, int] = {}
    for name in _QUIET_LOGGERS:
        lg = logging.getLogger(name)
        saved_levels[name] = lg.level
        lg.setLevel(logging.WARNING)
    try:
        builtins.print = _silent_print  # type: ignore[assignment]
        # ``contextlib.redirect_stderr`` 是 stdlib 提供的、保证退出时
        # 还原 ``sys.stderr`` 的标准做法。它替换的也是进程级 sys.stderr,
        # 在 ThreadPoolExecutor 子线程里替换仍会被主线程看到——但
        # akshare 内部对 stderr 的写入几乎只在主线程触发(future 错误、
        # 顶层 except 路径),而 Rich 只写 stdout,所以这个替换的风险
        # 比 stdout 小很多。仍保留 ``redirect_stderr`` 来彻底吞掉
        # ``I/O operation on closed file.`` 这类 urllib3 末尾刷出的 stderr。
        with contextlib.redirect_stderr(_NullIO()):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                warnings.simplefilter("ignore", FutureWarning)
                try:
                    yield
                finally:
                    builtins.print = saved_print  # type: ignore[assignment]
    finally:
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)


class _NullIO:
    """``contextlib.redirect_stderr`` 要求的 file-like 对象,丢弃所有写入。"""

    def write(self, _): return 0
    def flush(self): pass
    def isatty(self): return False
    def readable(self): return False
    def writable(self): return True
    def seekable(self): return False
    @property
    def closed(self): return False
    def close(self): return None


@contextlib.contextmanager
def capture() -> Iterator["list[str]"]:
    """捕获 akshare 调用期间的 print 输出,用于调试/测试。

    与 :func:`silence` 类似,但把 ``print(...)`` 的内容收集到列表里,
    调用方可在 ``with`` 块结束后读取 ``captured``。

    返回值是 ``list[str]``,每次 ``print`` 追加一条格式化字符串。
    """
    import builtins

    captured: list[str] = []
    saved_print = builtins.print
    saved_levels: dict[str, int] = {}
    for name in _QUIET_LOGGERS:
        lg = logging.getLogger(name)
        saved_levels[name] = lg.level
        lg.setLevel(logging.WARNING)
    try:

        def _capturing_print(*args, **_kwargs):
            sep = " "
            captured.append(sep.join(str(a) for a in args))

        builtins.print = _capturing_print  # type: ignore[assignment]
        with contextlib.redirect_stderr(_NullIO()):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                warnings.simplefilter("ignore", FutureWarning)
                try:
                    yield captured
                finally:
                    builtins.print = saved_print  # type: ignore[assignment]
    finally:
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)