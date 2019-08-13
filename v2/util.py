#!/usr/bin/env python3

import json
import itertools


class Any(object):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 1  # == hash(True)

    def __str__(self) -> str:
        return "Any()"


class JSONStringEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=E0202
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


def json_str_dumps(obj):
    return json.dumps(obj, cls=JSONStringEncoder)


def hashable(v):
    if isinstance(v, (set, list)):
        return tuple((hashable(i) for i in v))
    elif isinstance(v, dict):
        return tuple(
            sorted(((k, hashable(i), hash(k), hash(hashable(i)))
                    for k, i in v.items()),
                   key=lambda j: j[0]))
    else:
        return v


def labeled_product(iterables, include_empty=False):
    """
    Return a product, maintaining the labeling of keys mapping to the input iterables.
    """
    keys = list(iterables.keys())
    values = [iterables[k] for k in keys]
    for p in itertools.product(*values):
        yield dict(zip(keys, p))
    if include_empty and iterables != dict():
        yield dict()
