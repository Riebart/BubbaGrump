import itertools
from copy import deepcopy
import json


class JSONStringEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=E0202
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


def json_repr_dump(obj):
    return json.dumps(obj, cls=JSONStringEncoder)


class All(object):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return hash("hashyhashhash")

    def __str__(self):
        return "All"

    def __repr__(self):
        return "All"


class Mutator(object):
    def __init__(self, lambdas):
        self.lambdas = lambdas

    def apply(self, val):
        try:
            ret = deepcopy(val)
        except TypeError:
            ret = val

        for l in self.lambdas:
            ret = l(ret)
        return ret


def labeled_product(iterables, include_empty=False):
    """
    Return a product, maintaining the labeling of keys mapping to the input iterables.
    """
    keys = list(iterables.keys())
    values = [iterables[k] for k in keys]
    for p in itertools.product(*values):
        yield dict(zip(keys, p))
    if include_empty and len(values) == 0:
        yield dict()


def careful_dict_update(first, second):
    for k, v in second.items():
        if k in first and isinstance(first[k], list) and isinstance(v, list):
            first[k] += v
        else:
            first[k] = v
