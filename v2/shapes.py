#!/usr/bin/env python3
"""
Track the structure of the basic shapes that make up the AWS JSON API models. The structure is broken into a few parts:

## Operations

Operations (optionally) take an input and (optionally) produce an output which are one of the other shape types.

## Shapes

### Leaf Shapes

Leaf shapes are those that are not made up of other shapes, and cannot be broken apart any further. All values are, eventually, made up of a collection of leaf shapes. Leaf shapes can have constraints on them (e.g. enum, min, max, pattern/regex)

- Blob (binary blob)
- Boolean
- Double
- Float
- Integer (32-bit integer)
- Long (64-bit integer)
- String
- Timestamp (Unix timestamp)

### Alias Shapes

Alias shapes are shapes that are simply a convenient intermediate name for another shape, and do not represent any structural information for a shape or value, but rather provide semantic context (e.g. an Arn shape that is itself just a string).

### Composite Shapes

Composite shapes can be constructed from any set of values, provided all of the necessary parts of the shape exist within the domain of known values.

- List
  - Lists are _ordered_ lists of other shapes.
- Map
  - Maps are a mapping from one shape to another shape (typically string-string maps, but could map from any hashable shape, probably limited to leaf types).
- Structure
  - Structures are maps from strings to shapes, and typically are used as the inputs and outputs of operations, but are also used in other places.
"""

from util import Any, hashable, labeled_product
from botocore.model import Shape as BotoShape


class Lineage(object):
    """
    Store the history of a given object.
    """
    def __init__(self, *args):
        # Assert that the string keys for all of the args are unique and hashable
        try:
            assert len(set([a[0] for a in args])) == len(args)
        except:
            raise ValueError(
                "The keys for the elements in a lineage must be unique", args)
        self.args = args

    def __call__(self):
        return self.args[-1][1]

    # def __getattribute__(self, attr):
    #     if attr.startswith("__"):
    #         return super().__getattribute__(attr)
    #     else:
    #         return [(i, self.args[i]) for i in range(len(self.args))]

    def __getitem__(self, i):
        ret = self.args[i] if isinstance(i, int) else [
            self.args[j][1] for j in range(len(self.args))
            if self.args[j][0] == i
        ]
        return ret[0]

    def append(self, v):
        return Lineage(*(self.args + (v, )))


class Entity(object):
    def __init__(self, lineage):
        self.lineage = lineage
        self.value = None


class Shape(object):
    HINT_METADATA = ["idempotencyToken"]
    EMPTY = None

    def __init__(self, botoshape, 𝔻, autobuild=True):
        self.𝔻 = 𝔻
        self.botoshape = botoshape
        self.name = botoshape.name
        self.type = botoshape.type_name
        self.metadata = botoshape.metadata

        # There are some metadata elements, though, that do not get observed consistently (I'm looking at you, idempotencyToken on a4b.ClientRequestToken), and so we strip them from the metadata entirely, and transpose them into a non-canonical hint.
        self.hints = dict()
        for hint in Shape.HINT_METADATA:
            if hint in self.metadata:
                self.hints[hint] = self.metadata[hint]
                del self.metadata[hint]

        # OPTDO: Split the entities into the ShapeDomain (passed around) and not embedded in the Shape instance.
        self.𝔼 = list()  # The set of all instances of this shape

        if autobuild:
            self.build()

    def build(self):
        raise NotImplementedError("Unable to build a generic shape")

    def requirements_met(self, params):
        return True

    def reap(self, lineage_filter=lambda l: True, include_empty=False):
        """
        A generator to find all possible ways of constructing this shape, returns a Parameters object for each set of parameters.
        """
        return (𝕖.value for 𝕖 in self.𝔼 if lineage_filter(𝕖.lineage))

    def sow(self, lineage):
        """
        Create instances for this shape, and all child shapes, marked as having a lineage rooted at the specified operator.
        """
        # We can ignore the empty images, since those are always produced during reap()
        if lineage() == self.EMPTY:
            return
        𝕖 = Entity(lineage)
        𝕖.value = lineage()
        self.𝔼.append(𝕖)

    def minimal_canonical_form(self):
        return (("name", self.name), ("type", self.type),
                ("metadata", hashable(self.metadata)))

    def canonical_form(self):
        return self.minimal_canonical_form()

    def is_leaf(self) -> bool:
        return False

    def __str__(self) -> str:
        return str(self.canonical_form())


class ShapeDomain(object):
    """
    A context in which all shapes are created, ensuring that two shapes
    """
    def __init__(self, lineage: Lineage):
        # The set of all known shapes, mapping from boto shapes to a functional shape.
        self.domain_lineage = lineage
        self.𝕊 = dict()
        self.silhouettes = dict()

    def __getitem__(self, i: BotoShape) -> Shape:
        # Given an input that is a boto Shape, find, or create, a Shape from it and return.
        # If we have already seen this boto Shape, don't create a new Shape instance, return
        # a reference to the existing one.
        #
        # All shapes within a domain are universal to the domain, however entities (i.e. instances of a shape) have a lineage that can be filtered on when reap()-ing.
        𝕤 = SHAPE_TYPE_MAPPING[i.type_name](i, self, autobuild=False)

        # At this point, there is enough about this shape to store a reasonably unique silhouette of this shape, pending shape construction completion.
        # This is important, as SOME shapes (I'm looking at you ce.Expression), have themselves as members, and we can't wait until they are finished construction to cache them.
        𝕤_silhouette = 𝕤.minimal_canonical_form()
        if 𝕤_silhouette in self.silhouettes:
            return self.silhouettes[𝕤_silhouette]
        else:
            self.silhouettes[𝕤_silhouette] = 𝕤

        self.silhouettes[𝕤_silhouette] = 𝕤
        𝕤.build()
        del self.silhouettes[𝕤_silhouette]

        𝕤C = 𝕤.canonical_form()
        if 𝕤C not in self.𝕊:
            self.𝕊[𝕤C] = 𝕤
        return self.𝕊[𝕤C]

    def get_shape_by_name(self, shape_name: str) -> Shape:
        """
        Get a shape by name from the domain. If multiple shapes match the name, they are returned in a list
        """
        return [shape for shape in self.𝕊.values() if shape.name == shape_name]

    def __str__(self):
        return str(self.𝕊)


class Alias(Shape):
    def __init__(self, shape_name, base_shape):
        self.name = shape_name
        self.type = "alias""

        # There are some metadata elements, though, that do not get observed consistently (I'm looking at you, idempotencyToken on a4b.ClientRequestToken), and so we strip them from the metadata entirely, and transpose them into a non-canonical hint.
        self.hints = dict()
        for hint in Shape.HINT_METADATA:
            if hint in self.metadata:
                self.hints[hint] = self.metadata[hint]
                del self.metadata[hint]

        # OPTDO: Split the entities into the ShapeDomain (passed around) and not embedded in the Shape instance.
        self.𝔼 = list()  # The set of all instances of this shape

        if autobuild:
            self.build()

class Structure(Shape):
    EMPTY = dict()

    def build(self):
        # For a structure, only depend on all required members.
        # OPTDO: Structure members can be idempotency tokens to ensure that there is exactly one of a specific WRITE operation that takes place. This gets in the way and mucks up the shape consistency of that member, so is stripped out of the metadata when building shapes, but is otherwise useful when reap()-ing the structure (i.e. should be ignore at the same time as optional members)
        self.members = {
            member_name: self.𝔻[member]
            for member_name, member in self.botoshape.members.items()
        }
        self.required_members = self.botoshape.required_members

    def canonical_form(self):
        return super().canonical_form()
        # return (super().canonical_form(),
        #         ("members",
        #          tuple(((member_name, member.canonical_form())
        #                 for member_name, member in self.members.items()))))

    def requirements_met(self, params):
        return set(params.keys()).issuperset(self.required_members)

    def reap(self, lineage_filter=lambda l: True, include_empty=False):
        params = {
            k: v.reap(lineage_filter)
            for k, v in self.members.items() if k in self.required_members
        }
        return (i for i in labeled_product(params, include_empty)
                if self.requirements_met(i))

    def sow(self, lineage: Lineage):
        if lineage() == self.EMPTY:
            return
        𝕖 = Entity(lineage)
        𝕖.value = dict()
        for key in self.members.keys():
            if key in lineage().keys():
                𝕖.value[key] = lineage()[key]
                self.members[key].sow(
                    lineage.append(
                        ("structure-%s" % self.name, lineage()[key])))
        self.𝔼.append(𝕖)


class List(Shape):
    EMPTY = list()

    def build(self):
        # For a structure, only depend on all required members.
        self.member_shape = self.𝔻[self.botoshape.member]

    def canonical_form(self):
        return (super().canonical_form(), ("member",
                                           self.member_shape.canonical_form()))

    def reap(self, lineage_filter=lambda l: True, include_empty=False):
        # For lists, don't create every possible list, just the longest one including all entities of the member shape.
        return [list(self.member_shape.reap(lineage_filter))
                ] + ([list()] if include_empty else [])

    def sow(self, lineage):
        if lineage() == self.EMPTY:
            return
        for i in lineage():
            self.member_shape.sow(lineage.append(("list-%s" % self.name, i)))


class Map(Shape):
    EMPTY = dict()

    def build(self):
        # For a structure, only depend on all required members.
        self.key_shape = self.𝔻[self.botoshape.key]
        self.value_shape = self.𝔻[self.botoshape.value]

    def canonical_form(self):
        return (super().canonical_form(), ("key",
                                           self.key_shape.canonical_form()),
                ("value", self.value_shape.canonical_form()))


class LeafShape(Shape):
    def is_leaf(self):
        return True

    def build(self):
        pass


class Blob(LeafShape):
    pass


class Boolean(LeafShape):
    pass


class NumericShape(LeafShape):
    def build(self):
        # Check for any constraints from the metadata. Specifically, min and max.
        self.min = float(self.metadata.get("min", "-Infinity"))
        self.max = float(self.metadata.get("max", "Infinity"))

    def canonical_form(self):
        return (super().canonical_form(), ("min", self.min), ("max", self.max))


class Double(NumericShape):
    pass


class Float(NumericShape):
    pass


class Integer(NumericShape):
    pass


class Long(NumericShape):
    pass


class String(LeafShape):
    EMPTY = ""

    def build(self):
        self.min_length = float(self.metadata.get("min", "0"))
        self.max_length = float(self.metadata.get("max", "Infinity"))
        self.enum = tuple(
            self.metadata["enum"]) if "enum" in self.metadata else None
        # The pattern constraint for strings is not exposed by the boto Shape, and is instead squirreled away in the _shape_model.
        self.pattern = self.botoshape._shape_model.get("pattern", r"^.*")

    def canonical_form(self):
        return (super().canonical_form(), ("min_length", self.min_length),
                ("max_length", self.max_length), ("enum", self.enum),
                ("pattern", self.pattern))

    def reap(self, lineage_filter=lambda l: True, include_empty=False):
        # For strings, if there is an enum, only return those values
        if self.enum is not None:
            return self.enum
        else:
            # Otherwise, behave the same as other leaf shapes.
            return super().reap(lineage_filter)


class Timestamp(LeafShape):
    def build(self):
        # Like the pattern for strings, the timestamp format (specified by some newer API endpoints like API Gateway v2) is provided only in the _shape_model
        # Known formats: unixTimestamp, iso8601
        self.format_name = self.botoshape._shape_model.get(
            "timestampFormat", "unixTimestamp")

    def canonical_form(self):
        return (super().canonical_form(), ("timestampFormat",
                                           self.format_name))


SHAPE_TYPE_MAPPING = {
    "blob": Blob,
    "boolean": Boolean,
    "double": Double,
    "float": Float,
    "integer": Integer,
    "list": List,
    "long": Long,
    "map": Map,
    "string": String,
    "structure": Structure,
    "timestamp": Timestamp
}
