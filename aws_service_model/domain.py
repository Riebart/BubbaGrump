import json

from .util import All


class Entity(object):
    """
    A hashable tree node that can have multiple parent links. Useful for tracing the lineage of a given entity backwards, but not forwards.
    """

    def __init__(self, image, parents):
        self.image = image
        self.parents = parents
        self.__hash = hash(Entity.hash(image))

    @staticmethod
    def hash(val):
        """
        Generate a hash of a nested structure of dicts and lists by tuplifying a deep as necessary to the nearest hashable type.
        """
        try:
            if isinstance(val, tuple):
                return (hash(val), )
            else:
                return hash(val)
        except TypeError:
            if isinstance(val, dict):
                return tuple(
                    sorted((k, Entity.hash(v)) for k, v in val.items()))
            elif isinstance(val, list):
                # Normally we would sort this, but we can't always.
                return tuple((Entity.hash(v) for v in val))
            else:
                raise TypeError("Unsupported type for hashing", type(val))

    def __hash__(self):
        return self.__hash

    def __str__(self):
        return str(self.image)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return hash(self) == hash(other)


class Domain(object):
    """
    Domains contain two types of items:
    - Entities
    - Domains

    Entities have an image (i.e. value), and optionally a lineage. The lineage of an entity is a tree of entities that are/were required to construct the given entity. Lineages are implicit structures and are created iteratively by specifying a list of parent entities when manifesting an entity in a domain.

    Domains are disjoint structures that encode namespaces for the existence of entities. Domains are rooted at an entity that exists in the enclosing domain. Searching a domain for entities will not return entities in another domain, even those that are sub-dimensions of the searched domain. An entity, however, can have a lineage that traces across arbitrary domains. This makes it possible to encode how a domain was spawned by finding the entities in that domain that trace their lineage outside of the given domain.
    """

    def __init__(self, entity=None):
        self.root_entity = entity
        self.dimensions = dict()
        self.entities = set()
        self.facts = set()

    def dimension(self, entity):
        """
        Spawn a new Domain that exists at a specific entity in the current domain
        """
        if not isinstance(entity, Entity):
            entity = Entity(entity, None)

        if entity not in self.dimensions:
            self.dimensions[entity] = Domain(entity)

        return self.dimensions[entity]

    def manifest(self, image, parents=None):
        """
        Create an entity in this domain from a given image
        """
        if not isinstance(image, Entity):
            ent = Entity(image, parents)
        else:
            ent = image

        self.entities.add(ent)
        return ent

    def images(self):
        return [ent.image for ent in self.entities]

    def __str__(self):
        return str({
            "dimensions": str(self.dimensions),
            "entities": str(self.entities)
        })

    def __repr__(self):
        return self.__str__()
