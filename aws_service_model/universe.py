from .util import All


class Entity(object):
    def __init__(self, value):
        self.value = value

    def add_child(self, entity):
        pass


class Universe(object):
    """
    A universe of values that different shapes can take.

    Values exist in one, several, or all dimensions.
    """

    def __init__(self):
        self.dimensions = {All: dict()}

    def spawn(self, dimension, species, image, hashable=False):
        if dimension not in self.dimensions:
            self.dimensions[dimension] = dict()
        dim = self.dimensions[dimension]

        if species not in dim:
            dim[species] = set() if hashable else list()

        spec = dim[species]
        if isinstance(spec, set):
            spec.add(image)
        else:
            spec.append(image)

    def images(self, dimension, species):
        ret = list(self.dimensions.get(dimension, dict()).get(species, list()))
        # Now also include those entities in the ALL dimension
        ret += self.dimensions[All].get(species, list())
        return ret

    def __str__(self):
        return str(self.dimensions)
