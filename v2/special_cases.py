import shapes


class SpecialCase(object):
    def on_build(self, shape):
        """
        Modify the given shape in place, and return more shapes, as necessary to implement the transformation that the special case describes.
        """
        pass


class StructureIdMember(SpecialCase):
    def on_build(self, shape):
        if isinstance(shape, shapes.Structure):
            # For Structure shapes, check to see if there is one of the following:
            # - an 'id' field => Change the shape of that field to be an Alias that wraps the underlying shape type, with the Alias shape name being "${StructureName}Id"
            # - A field ending in "Id" => Wrap it in an Alias shape with the name being "${MemberName}"
            for member_name, member_shape in shape.members.items():
                if member_name.lower() == "id":
                    alias = shapes.Alias()
