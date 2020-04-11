import functools
import hashlib
import itertools
from collections import OrderedDict
from typing import Any, Dict, Generator, Iterable, List, Union


def ensure_list(value: Any) -> List[Any]:
    if not issubclass(type(value), list):
        return [value]
    return value


def reduce(values: List) -> Union[List[Any], Any]:
    """ Reduce a list to a scalar if length == 1 """
    while isinstance(values, list) and len(values) == 1:
        values = values[0]
    return values


def make_hash(data: Union[List, OrderedDict]) -> str:
    return hashlib.md5(str(data).encode()).hexdigest()


def chunks(iterable: Iterable, n: int = 1000, cls=list) -> Generator:
    """ Process an infinitely nested interable in chunks of size n (default=1000) """
    it = iter(iterable)
    while True:
        chunk_it = itertools.islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield cls(itertools.chain((first_el,), chunk_it))


def query(path: str, data: dict, sep: str = "."):
    """ Query any combination of nested lists/dicts, returning the last valid value
        encountered in the query chain.

        Example:
            data = {"a": {"b": {"c": 1}}}

            query(path="a.b.c", data=data) => 1

            query(path="a.b", data=data) => {"c": 1}

         """
    elements = path.split(sep)
    for e in elements:
        if issubclass(type(data), list) and len(data) > 0:
            try:
                data = data[int(e)]
            except ValueError:
                # handle cases where a list of items occurs where a mapping is expected
                data = data[-1]
        elif issubclass(type(data), dict):
            data = data.get(e, {})

    return data if data else None


def query_factory(data: str, sep: str = "."):
    return functools.partial(query, data=data, sep=sep)


def filter_by_prefix(
    d: Dict, prefix: str, tolower: bool = True, strip: bool = True
) -> Dict:
    """ Return all items with keys that begin with the given prefix.

        Example: prefix = "collector"

            Returns:
                {
                    "base_url": "example.com/api",
                    "path": "path/to/data",
                    "endpoints": {...}
                }
    """

    if tolower:
        cast = str.lower
    else:
        cast = str.upper

    if not prefix.endswith("_"):
        prefix = prefix + "_"
    prefix = cast(prefix)

    result: Dict = {}

    for key, value in d.items():
        key = cast(key)
        if key.startswith(prefix):
            if strip:
                key = key.replace(prefix, "")
            result[key] = value

    return result


def distinct_by_key(data: List[Dict], key: str) -> List:
    """ Return distinct records from a list of dictionaries, as determined by the
        provided key. """

    result = {}
    for x in data:
        k = x.get(key)
        if k:
            result[k] = x
    return list(result.values())
