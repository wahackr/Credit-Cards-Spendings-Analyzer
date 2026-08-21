import ssl
import time
from typing import Callable, TypeVar


_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_TRANSIENT_EXCEPTION_NAMES = {
    "apiconnectionerror",
    "connecterror",
    "connecttimeout",
    "modelapierror",
    "modelconnectionerror",
    "modelratelimiterror",
    "modeltimeouterror",
    "networkerror",
    "protocolerror",
    "ratelimiterror",
    "readerror",
    "readtimeout",
    "remoteprotocolerror",
    "resourceexhausted",
    "serviceunavailable",
    "timeouterror",
    "toomanyrequests",
    "writeerror",
    "writetimeout",
}
T = TypeVar("T")


def _status_code(error: BaseException) -> int | None:
    for attribute in ("status_code", "status", "code"):
        value = getattr(error, attribute, None)
        if callable(value):
            try:
                value = value()
            except TypeError:
                continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def is_transient_error(error: BaseException) -> bool:
    """Recognize retryable transport, timeout, rate-limit, and server errors."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ssl.SSLError, TimeoutError, ConnectionError)):
            return True
        if getattr(current, "is_retryable", False) is True:
            return True
        if _status_code(current) in _TRANSIENT_STATUS_CODES:
            return True
        if current.__class__.__name__.lower() in _TRANSIENT_EXCEPTION_NAMES:
            return True
        current = current.__cause__ or current.__context__
    return False


def retry_transient(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Retry only transient failures with bounded exponential backoff."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    for attempt in range(max_attempts):
        try:
            return operation()
        except Exception as exc:
            if attempt == max_attempts - 1 or not is_transient_error(exc):
                raise
            delay = initial_delay * (2**attempt)
            if on_retry is not None:
                on_retry(attempt + 1, exc, delay)
            sleep(delay)
    raise AssertionError("unreachable")
