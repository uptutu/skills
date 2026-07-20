"""指数退避重试工具。"""
from __future__ import annotations

import time
from typing import Callable, Iterable, TypeVar

from .silence import silence

T = TypeVar("T")


# 默认重试的"非中断"异常集合：网络层 ConnectionError/KeyboardInterrupt 永远不重试，
# 让它们直接冒泡给上层处理（CLI 会转为退出码 3）。
DEFAULT_RETRY_ON: tuple[type[BaseException], ...] = (
    TimeoutError,
    OSError,  # 包含 socket.gaierror、ConnectionRefusedError 等的父类
)


def call_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base: float = 1.0,
    retry_on: Iterable[type[BaseException]] = DEFAULT_RETRY_ON,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """以指数退避策略调用 ``fn``。

    Parameters
    ----------
    fn:
        无参可调用对象。
    attempts:
        总尝试次数，至少 1。
    base:
        第一次重试的等待秒数，后续翻倍（1s, 2s, 4s, ...）。
    retry_on:
        触发重试的异常类型元组；不匹配的异常会立即抛出。
        默认只重试 ``TimeoutError`` / ``OSError``。

    Raises
    ------
    最后一次尝试的异常。
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    retry_types = tuple(retry_on)
    last_exc: BaseException | None = None
    # ``silence()`` 包裹整个重试窗口,避免 akshare 内部 print() /
    # urllib3 连接日志 / pandas FutureWarning 等噪声穿透终端。
    # Rich 的 printer 面板渲染发生在 silence 作用域之外,不受影响。
    with silence():
        for i in range(attempts):
            try:
                return fn()
            except retry_types as exc:  # noqa: PERF203 - 循环内捕获可读
                last_exc = exc
                if i == attempts - 1:
                    break
                sleep(base * (2 ** i))
    assert last_exc is not None
    raise last_exc
