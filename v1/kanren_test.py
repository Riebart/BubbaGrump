#/usr/bin/env python3

import kanren
from kanren import Relation, facts, var, conde, run

parent = Relation("parent")
facts(parent, ("Alice", "Bob"), ("Alice", "Carol"), ("Bob", "Diane"),
      ("Bob", "Ed"), ("Carol", "Frankie"), ("Diane", "Gerry"),
      ("Diane", "Heather"), ("Carol", "Indy"), ("Indy", "Jackie"))


def ancestor(a, b):
    x = var()
    return conde([(parent, a, b)], [(parent, a, x), (ancestor, x, b)])


x = var()
print(run(0, x, ancestor("Bob", x)))
