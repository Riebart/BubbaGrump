import itertools
from copy import deepcopy


class All(object):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return hash("hashyhashhash")

    def __str__(self):
        return "All"

    def __repr__(self):
        return "All"


class Filter(object):
    def __init__(self, filters):
        self.filters = filters

    def apply(self, val):
        ret = deepcopy(val)
        for f in self.filters:
            ret = f(ret)
        return ret


def labeled_product(iterables, include_empty=False):
    """
    Return a product, maintaining the labeling of keys mapping to the input iterables.
    """
    keys = list(iterables.keys())
    values = [iterables[k] for k in keys]
    for p in itertools.product(*values):
        yield dict(zip(keys, p))
    if include_empty:
        yield dict()


def careful_dict_update(first, second):
    for k, v in second.items():
        if k in first and isinstance(first[k], list) and isinstance(v, list):
            first[k] += v
        else:
            first[k] = v