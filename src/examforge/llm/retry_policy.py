"""LLM 重试策略与错误处理。"""

import time
from typing import Callable, TypeVar, Any

T = TypeVar("T")


class RetryConfig:
    """重试配置。"""
    def __init__(
        self,
        max_retries: int = 2,
        base_delay: float = 1.0,
        max_delay: float = 8.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def delay_for_attempt(self, attempt: int) -> float:
        """计算指数退避延迟。"""
        return min(self.base_delay * (2 ** attempt), self.max_delay)


def with_retry(
    func: Callable[..., T],
    config: RetryConfig,
    should_retry: Callable[[Exception], bool],
) -> T:
    """通用重试装饰器。

    Args:
        func: 要重试的函数
        config: 重试配置
        should_retry: 判断异常是否应该重试的函数

    Returns:
        函数执行结果

    Raises:
        最后一次异常
    """
    last_err: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_err = e
            if attempt < config.max_retries and should_retry(e):
                time.sleep(config.delay_for_attempt(attempt))
                continue
            raise

    # 不应该到达这里,但为了类型检查
    if last_err:
        raise last_err
    raise RuntimeError("Unexpected retry loop exit")
