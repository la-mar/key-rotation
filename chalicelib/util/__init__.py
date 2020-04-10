import math
from typing import Any, List, Union


def ensure_list(value: Any) -> List[Any]:
    if not issubclass(type(value), list):
        return [value]
    return value


def reduce(values: List) -> Union[List[Any], Any]:
    """ Reduce a list to a scalar if length == 1 """
    while isinstance(values, list) and len(values) == 1:
        values = values[0]
    return values


def hf_size(size_bytes: Union[str, int]) -> str:
    """Human friendly string representation of a size in bytes.

    Source: https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python

    Arguments:
        size_bytes {Union[str, int]} -- size of object in number of bytes

    Returns:
        str -- string representation of object size. Ex: 299553704 -> "285.68 MB"
    """  # noqa
    if size_bytes == 0:
        return "0B"

    suffixes = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

    if isinstance(size_bytes, str):
        size_bytes = int(size_bytes)

    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {suffixes[i]}"
