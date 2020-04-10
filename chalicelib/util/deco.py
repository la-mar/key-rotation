import functools
import logging
from timeit import default_timer as timer
from typing import Any, Callable

logger = logging.getLogger(__name__)


def ambiguous(decorator):
    """ Decorator to allow the decorated function to be called with or without
        parenthesis. Should only be used to decorate other decorator defintions"""

    @functools.wraps(decorator)
    def wrapper(*args, **kwargs):
        if len(args) > 0:
            f = args[0]
        else:
            f = None

        if callable(f):
            return decorator()(f)  # pass the function to be decorated
        else:
            return decorator(*args, **kwargs)  # pass the specified params

    return wrapper


@ambiguous
def log_execution_time() -> Callable:
    def deco(func) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            name = kwargs.pop("name", None)
            try:
                ts = timer()
                result = await func(*args, **kwargs)
                te = timer()
                exc_time = round(te - ts, 3)

                logger.info(
                    f"{name or func.__name__} executed in {exc_time}s",
                    extra={"exc_time": exc_time, "name": name or func.__name__},
                )
                return result
            except Exception as e:
                logger.debug(f"{func} failed: {e}")

        return wrapper

    return deco
