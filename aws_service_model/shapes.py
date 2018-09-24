from .util import labeled_product, careful_dict_update
from .exceptions import InsufficientMembersException


class Shape(object):
    def __init__(self, shape_name, service):
        self.service = service
        self.shape = service.raw_get_shape(shape_name)
        self.shape_name = shape_name

    def name(self):
        return self.shape_name

    def service_name(self):
        return self.service.abbreviation()

    def satisfies_leaf_condition(self, condition):
        """
        Determines whether or not every child of this shape terminates in a leaf node that satisfies the given condition. Leaf nodes are those that do not depend on another shape or member.

        Condition is a function that returns True or False, and takes as input the raw shape as available in the service JSON file.
        """
        raise NotImplementedError(
            "satisfies_leaf_condition() is not implementable at the generic Shape type."
        )

    def construct(self, universe):
        """
        Given a universe of options, return a generator that yields every possible way of building this shape. This is recursive, and so will recursively generate all all possible ways of constructing the types that feed into this shape, given the universe.

        At every recursive step, the shapes check to see if there are values valid for use at that shape, and if so will not descend to child shapes. An example is ARNs which, while they are strings, will look for any ARNs in the universe and iterate over those if found instead of descending to the child String shape.
        """
        # Given the service name, the shape name, and the universe, find all options.
        return universe.images(self.service.name(), self.name())

    def __str__(self):
        return "%s:%s" % (self.service_name(), self.name())

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return (self.name() == other.name()) and (
            self.service_name() == other.service_name())


class Structure(Shape):
    def __init__(self, shape_name, service):
        super().__init__(shape_name, service)
        self.member_shapes = {
            member_name: service.get_shape(member["shape"])
            for member_name, member in self.shape["members"].items()
        }

    def members(self):
        ret = dict()
        ret.update(self.member_shapes)
        return ret

    def satisfies_leaf_condition(self, condition):
        for _, member_shape in self.member_shapes.items():
            if not member_shape.satisfies_leaf_condition(condition):
                return False

        return True

    def construct(self, universe):
        params = {
            member_name: member_shape.construct(universe)
            for member_name, member_shape in self.member_shapes.items()
        }

        return labeled_product(params)

    def populate(self, image, universe):
        """
        Given a response object that conforms to this Shape, derive all entities that now exist in this universe.
        """
        universe.spawn(
            dimension=self.service.name(), species=self.name(), image=image)
        for member_name, member_shape in self.member_shapes.items():
            if member_name in image:
                member_shape.populate(image[member_name], universe)


class List(Shape):
    def __init__(self, shape_name, service):
        super().__init__(shape_name, service)
        self.member_shape = service.get_shape(self.shape["member"]["shape"])

    def satisfies_leaf_condition(self, condition):
        return self.member_shape.satisfies_leaf_condition(condition)

    def construct(self, universe):
        """
        When constructing lists, don't attempt to construct every list, just the longest one.
        """
        # Lists will have one member shape, so get that member shape, convert the results to a list and return that
        return [list(self.member_shape.construct(universe))]

    def populate(self, image, universe):
        universe.spawn(
            dimension=self.service.name(), species=self.name(), image=image)
        for val in image:
            self.member_shape.populate(val, universe)


class Map(Shape):
    def satisfies_leaf_condition(self, condition):
        return (self.service.get_shape(
            self.shape["key"]["shape"]).satisfies_leaf_condition(condition)
                and self.service.get_shape(self.shape["value"]["shape"]).
                satisfies_leaf_condition(condition))


class LeafShape(Shape):
    def satisfies_leaf_condition(self, condition):
        return condition(self.shape)

    def construct(self, universe):
        s = super().construct(universe)
        if s != []:
            return s
        else:
            return []

    def populate(self, image, universe):
        universe.spawn(
            dimension=self.service.name(),
            species=self.name(),
            image=image,
            hashable=True)


class Blob(LeafShape):
    pass


class Boolean(LeafShape):
    pass


class Double(LeafShape):
    pass


class Float(LeafShape):
    pass


class Integer(LeafShape):
    pass


class Long(LeafShape):
    pass


class String(LeafShape):
    CONSTRAINTS = ["enum", "max", "min", "pattern"]

    def __init__(self, shape_name, service):
        super().__init__(shape_name, service)

        # Strings can have a few constraints
        self.constraints = {
            c: self.shape.get(c, None)
            for c in self.CONSTRAINTS
        }

    def construct(self, universe):
        s = super().construct(universe)
        if s != []:
            return s
        elif "enum" in self.constraints:
            return self.constraints["enum"]
        else:
            return []


class Timestamp(LeafShape):
    pass


class Request(Structure):
    def __init__(self, shape_name, service, op):
        super().__init__(shape_name, service)
        self.op = op

    def requirements(self):
        return {
            req: self.service.get_shape(self.shape["members"][req]["shape"])
            for req in self.shape.get("required", [])
        }

    def members(self):
        members = super().members()
        # Request members shouldn't count anything required for pagination
        return {
            name: member
            for name, member in members.items()
            if name not in self.op.pagination_inputs()
        }

    def construct(self, universe, included_members=None):
        if included_members is None:
            included_members = self.members().values()

        params = {
            member_name: member.construct(universe)
            for member_name, member in self.members().items()
            if member in included_members
        }

        # Now throw away anything where the value is None
        params = {k: v for k, v in params.items() if v is not None}
        if not set(self.requirements().keys()).issubset(set(params.keys())):
            raise InsufficientMembersException(
                "Insufficient members exist for required parameters",
                self.name(), list(self.requirements().keys()),
                list(params.keys()))

        # When producing our product, if the requirements list is empty then also permit an empty kwargs in the cross-product
        return labeled_product(
            params, include_empty=(len(self.requirements().keys()) == 0))


class Response(Structure):
    def __init__(self, shape_name, service, op):
        super().__init__(shape_name, service)
        self.op = op

    def members(self):
        members = super().members()
        # Request members shouldn't count anything required for pagination
        return {
            name: member
            for name, member in members.items()
            if name not in self.op.pagination_outputs()
        }


class Operation(object):
    def __init__(self, op, service):
        self.service = service
        self.shape = op

    def is_paginated(self):
        return self.shape["name"] in self.service.paginators["pagination"]

    def pagination_inputs(self):
        if self.is_paginated():
            return [
                self.service.paginators["pagination"][self.shape["name"]][k]
                for k in ["input_token", "limit_key"]
            ]
        else:
            return []

    def pagination_outputs(self):
        if self.is_paginated():
            return [
                self.service.paginators["pagination"][self.shape["name"]][k]
                for k in ["output_token"]
            ]
        else:
            return []

    def name(self):
        return self.shape["name"]

    def service_name(self):
        return self.service.abbreviation()

    def input(self):
        return Request(self.shape["input"]["shape"], self.service,
                       self) if "input" in self.shape else None

    def output(self):
        return Response(self.shape["output"]["shape"], self.service,
                        self) if "output" in self.shape else None

    def call(self, kwargs):
        kwargs = self.service.blacklist(kwargs)
        if self.is_paginated():
            paginator = self.service.get_paginator(self.shape["name"])
            ret = dict()
            pages = paginator.paginate(**kwargs)
            for page in pages:
                careful_dict_update(ret, page)
            return ret
        else:
            func = self.service.get_method(self.shape["name"])
            return func(**kwargs)

    def __eq__(self, other):
        return (self.name() == other.name()) and (
            self.service_name() == other.service_name())

    def __str__(self):
        return "%s:%s" % (self.service_name(), self.name())

    def __repr__(self):
        return self.__str__()
