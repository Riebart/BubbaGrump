from .exceptions import InsufficientMembersException

# Used when populating a domain, some of the entities need to have their values massaged a bit.
from .special_cases import apply_entity_manifestation_transform as apply_emt
# Used when constructing possible inputs, some of the constructed values need to be massaged into satisfying particular criteria.
from .special_cases import apply_image_construction_transform as apply_ict
from .util import careful_dict_update, labeled_product


class Shape(object):
    def __init__(self, shape_name, service):
        self.service = service
        self.shape = service.raw_get_shape(shape_name)
        self.shape_name = shape_name

    def name(self):
        return self.shape_name

    def service_name(self):
        return self.service.endpoint_prefix()

    def satisfies_leaf_condition(self, condition):
        """
        Determines whether or not every child of this shape terminates in a leaf node that satisfies the given condition. Leaf nodes are those that do not depend on another shape or member.

        Condition is a function that returns True or False, and takes as input the raw shape as available in the service JSON file.
        """
        raise NotImplementedError(
            "satisfies_leaf_condition() is not implementable at the generic Shape type."
        )

    def construct(self, domain):
        """
        Given a domain of options, return a generator that yields every possible way of building this shape. This is recursive, and so will recursively generate all all possible ways of constructing the types that feed into this shape, given the domain.

        At every recursive step, the shapes check to see if there are values valid for use at that shape, and if so will not descend to child shapes. An example is ARNs which, while they are strings, will look for any ARNs in the domain and iterate over those if found instead of descending to the child String shape.
        """
        # Given the service name, the shape name, and the domain, find all options.
        return domain.dimension(self.name()).images()

    def populate(self, image, domain, parent):
        """
        Create a an entity for this shape image in the domain, and a dimension for this shape.
        """
        # Create a dimension for this shape type, implicitly creating an Entity in the dimension() call.
        𝕊 = domain.dimension(self.name())
        # Manifest this entity in the dimension for this shape.
        ent = 𝕊.manifest(image=image,
                         parents=[] if parent is None else [parent])
        # Return the entity for this shape image for use as the parent for future images.
        return ent

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

    def construct(self, domain):
        params = {
            member_name: member_shape.construct(domain)
            for member_name, member_shape in self.member_shapes.items()
        }

        return labeled_product(params)

    def populate(self, image, domain, parent=None):
        """
        Given a response object that conforms to this Shape, derive all entities that now exist in this domain.
        """
        # Structures spawn an entity that is themselves,
        ent = super().populate(image, domain, parent)
        for member_name, member_shape in self.member_shapes.items():
            if member_name in image:
                member_shape.populate(image[member_name], domain, ent)
        return ent


class List(Shape):
    def __init__(self, shape_name, service):
        super().__init__(shape_name, service)
        self.member_shape = service.get_shape(self.shape["member"]["shape"])

    def satisfies_leaf_condition(self, condition):
        return self.member_shape.satisfies_leaf_condition(condition)

    def construct(self, domain):
        """
        When constructing lists, don't attempt to construct every list, just the longest one.
        """
        # Lists will have one member shape, so get that member shape, convert the results to a list and return that. Don't use the super, since we'll want to construct the lists fresh each time.
        return apply_ict(self.service.endpoint_prefix(), self.name(),
                         [list(self.member_shape.construct(domain))])

    def populate(self, image, domain, parent=None):
        ent = super().populate(image, domain, parent)
        for val in image:
            self.member_shape.populate(val, domain, ent)
        return ent


class Map(Shape):
    def __init__(self, shape_name, service):
        super().__init__(shape_name, service)
        self.key_shape = self.service.get_shape(self.shape["key"]["shape"])
        self.val_shape = self.service.get_shape(self.shape["value"]["shape"])

    def satisfies_leaf_condition(self, condition):
        return (self.key_shape.satisfies_leaf_condition(condition)
                and self.val_shape.satisfies_leaf_condition(condition))

    def populate(self, image, domain, parent=None):
        ent = super().populate(image, domain, parent)
        for k, v in image.items():
            key_ent = self.key_shape.populate(k, domain, ent)
            self.val_shape.populate(v, domain, key_ent)
        return ent


class Alias(Shape):
    """
    A shape with only one key ("shape") that points to another shape. This shape is inserted into chains by special-casing code to provide type-hinting around highly generic shapes, such as ARNs.

    Shapes wrapped in an alias will appear in every natural dimension of a domain, as well as the aliased ones.
    """
    def __init__(self, shape_name, service):
        super().__init__(shape_name, service)
        self.child_shape = self.service.get_shape(self.shape["shape"])

    def satisfies_leaf_condition(self, condition):
        return self.child_shape.satisfies_leaf_condition(condition)

    def construct(self, domain):
        s = super().construct(domain)
        if s != []:
            return s
        else:
            return self.child_shape.construct(domain)

    def populate(self, image, domain, parent=None):
        ent = super().populate(image, domain, parent)
        self.child_shape.populate(image, domain, ent)
        return ent


class LeafShape(Shape):
    def satisfies_leaf_condition(self, condition):
        return condition(self.shape)

    def construct(self, domain):
        s = super().construct(domain)
        if s != []:
            return s
        else:
            return []

    def populate(self, image, domain, parent=None):
        ent = super().populate(image, domain, parent)
        return ent


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

    def construct(self, domain):
        s = super().construct(domain)
        if s != []:
            return s
        elif "enum" in self.constraints:
            return self.constraints["enum"]
        else:
            return []

    def populate(self, image, domain, parent=None):
        # When populating, massage the image into a string via JSON
        ent = super().populate(
            apply_emt(self.service.endpoint_prefix(), self.name(), image),
            domain, parent)
        return ent


class Timestamp(LeafShape):
    pass


class EmptyStructure(Structure):
    def __init__(self):
        pass

    def requirements(self):
        return dict()

    def construct(self, domain, included_members=None):
        return [dict()]

    def __str__(self):
        return "EmptyStructure"

    def __repr__(self):
        return self.__str__()


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

    def construct(self, domain, included_members=None):
        if included_members is None:
            included_members = self.members().values()

        params = {
            member_name: member.construct(domain)
            for member_name, member in self.members().items()
            if member in included_members
        }

        # Now throw away anything where the value is None
        params = {k: v for k, v in params.items() if v is not None}
        if not set(self.requirements().keys()).issubset(set(params.keys())):
            raise InsufficientMembersException(
                "Insufficient members exist for required parameters",
                self.service_name(), self.name(),
                list(self.requirements().keys()), list(params.keys()))

        # When producing our product, if the requirements list is empty then also permit an empty kwargs in the cross-product
        return labeled_product(params,
                               include_empty=(len(
                                   self.requirements().keys()) == 0))


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

    def __hash__(self):
        return hash(self.__str__())

    def __eq__(self, other):
        return hash(self) == hash(other)

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
        return self.service.endpoint_prefix()

    def input(self):
        return Request(self.shape["input"]["shape"], self.service,
                       self) if "input" in self.shape else EmptyStructure()

    def output(self):
        return Response(self.shape["output"]["shape"], self.service,
                        self) if "output" in self.shape else EmptyStructure()

    def call(self, kwargs):
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

    def __str__(self):
        return "%s:%s" % (self.service_name(), self.name())

    def __repr__(self):
        return self.__str__()
