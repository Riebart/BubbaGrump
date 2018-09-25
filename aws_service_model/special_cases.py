"""
In many cases, there are specific transformations that need to be performed at different stages of the processing pipeline. There are a few stages where transformations can take place:

- Shape Construction: When a shape is constructed by extracting it from the body, there may be a transformation to occur before it enters the entity and object logic. Examples are removing an invalid member from the members list, or adding or removing a requirement.

- Entity Manifestation: When a shape is populating a domain after a response is received, there may be a requirement to massage or manipulate the input that is received into the appropriate format. An example is JSON encoding a dict that is passed to an IAM policy document shape.

- Image Construction: When a shape is being rendered into images, there may be some additional constraints or transformations that need to be applied to the resulting images. An example is slicing a list into smaller lists of a maximum length.
"""

import json
from copy import deepcopy
from .util import Mutator


def key_mutate(m, keys, mutator):
    """
    Mutate a list of keys in a dictionary, applying the mutator to the values, and returning the mutated dictionary.

    The modifications are made in-place, but the return of the value is useful semantically.
    """
    if not isinstance(keys, list):
        m[keys] = mutator(m[keys])
    else:
        for key in keys:
            m[key] = mutator(m[key])

    return m


def list_partition(l, k):
    """
    Partition a list into non-overlapping consecutive lists of length k, with a final list of length <k.
    """
    return [l[i:i + k] for i in range(0, len(l), k)]


def apply_shape_member_aliasing(service, shape_name, shape):
    mapping = dict()

    # The mapping we need to use is the union of anything specific to this shape, and the "*" shape mapping.
    mapping.update(
        MEMBER_SHAPE_REPLACEMENTS.get(service, dict()).get("*", dict()))
    mapping.update(
        MEMBER_SHAPE_REPLACEMENTS.get(service, dict()).get(shape_name, dict()))

    for name, member in shape["members"].items():
        if name in mapping:
            member["shape"] = mapping[name]

    return shape


def apply_transform(transform, service, shape_name, value):
    m = transform.get(service, dict()).get(shape_name, None)
    if m is not None:
        return m.apply(deepcopy(value))
    else:
        return deepcopy(value)


def apply_shape_construction_transform(service, shape_name, shape):
    ret = apply_transform(SHAPE_CONSTRUCTION_TRANSFORMS, service, shape_name,
                          shape)
    if shape["type"] == "structure":
        # Now apply any shape member transformations described.
        ret = apply_shape_member_aliasing(service, shape_name, ret)
    return ret


def apply_image_construction_transform(service, shape_name, image):
    return apply_transform(IMAGE_CONSTRUCTION_TRANSFORMS, service, shape_name,
                           image)


def apply_entity_manifestation_transform(service, shape_name, shape):
    return apply_transform(ENTITY_MANIFESTATION_TRANSFORMS, service,
                           shape_name, shape)


def get_shape_alias(service, shape_name):
    ret = SHAPE_ALIASES.get(service, dict()).get(shape_name,
                                                 {"type": "string"})
    if "type" not in ret:
        ret["type"] = "alias"
    return ret


OPERATION_BLACKLIST = {
    "iam": Mutator([
        lambda ops: [op for op in ops if op.name() in ["GetAccountAuthorizationDetails"]]
    ]),
    "apigateway": Mutator([
        lambda ops: [op for op in ops if op.name() not in ["GetExport"]]
    ]),
}

# For aliasing a shape name to something other than teh default of type=string
SHAPE_ALIASES = {}

MEMBER_SHAPE_REPLACEMENTS = {
    "apigateway": {
        # For every structure in the API Gateway model, replace any member named restApiId
        "*": {
            "restApiId": "RestApiIdType",
            "authorizerId": "AuthorizerApiIdType",
            "basePath": "BasePathType",
            "domainName": "DomainNameType",
            "clientCertificateId": "ClientCertificateType",
            "deploymentId": "DeploymentIdType",
            "documentationPartId": "DocumentationPartIdType",
            "documentationVersion": "DocumentationVersionType",
            "resourceId": "ResourceIdType",
            "modelName": "ModelNameType",
            "requestValidatorId": "RequestValidatorIdType",
            "stageName": "StageNameType",
            "sdkType": "SdkTypeType",
            "usagePlanId": "UsagePlanIdType",
            "keyId": "UsageKeyIdType",
            "vpcLinkId": "VpcLinkIdType"
        },
        "RestApi": {
            "id": "RestApiIdType"
        },
        "Authorizer": {
            "id": "AuthorizerApiIdType"
        },
        "GetSdkTypeRequest": {
            "id": "SdkTypeType"
        }
    }
}

IMAGE_CONSTRUCTION_TRANSFORMS = {
    "iam": {
        "SimulationPolicyListType":
        Mutator([
            # The list should be in groups of at most 10 items, this is enforced by the API.
            lambda val: list_partition(val[0], 10)
        ])
    }
}

ENTITY_MANIFESTATION_TRANSFORMS = {
    "iam": {
        "policyDocumentType":
        Mutator([
            # The policies provided are actually a dictionary, not a JSON string as described in the model.
            lambda v: json.dumps(v)
        ])
    }
}

SHAPE_CONSTRUCTION_TRANSFORMS = {
    "acm": {
        "ExtendedKeyUsageName": Mutator([
            # The CUSTOM value in this enum is not allowed in at least one operation.
            lambda shape: key_mutate(
                shape,
                "enum",
                lambda enums: [e for e in enums if e != "CUSTOM"]
            )
        ])
    },
    "iam": {
        "ListPoliciesRequest": Mutator([
            # The models describe a few extra members in this structure, but the API enforces that the members only be one of this list.
            lambda shape: key_mutate(
                shape,
                "members",
                lambda members: {
                    k: v for k, v in members.items() if
                    k in [
                        "Scope", "OnlyAttached", "PathPrefix",
                        "Marker", "MaxItems"
                    ]
                }
            )
        ]),
        "ListEntitiesForPolicyRequest": Mutator([
            lambda shape: key_mutate(
                shape,
                "members",
                lambda members: {
                    k: v for k, v in members.items() if
                    k in [
                        "PolicyArn", "EntityFilter", "PathPrefix",
                        "Marker", "MaxItems"
                    ]
                }
            )
        ]),
        "policyScopeType": Mutator([
            # Don't enumerate all AWS managed policies
            lambda shape: key_mutate(
                shape,
                "enum",
                lambda enums: [e for e in enums if e not in ["All", "AWS"]]
            )
        ]),
        "EntityType": Mutator([
            # Don't enumerate all AWS managed policies
            lambda shape: key_mutate(
                shape,
                "enum",
                lambda enums: [e for e in enums if e not in ["AWSManagedPolicy"]]
            )
        ]),
    }
}

# def member_filter(shape, filter_set):
#     shape["members"] = {
#         k: v
#         for k, v in shape["members"].items() if k in filter_set
#     }
#     return shape

# SHAPE_MODIFIERS =

# def special_case(service_prefix, shape_name):
#     return __SPECIAL_CASES.get(service_prefix, dict()).get(
#         shape_name, lambda v: v)

# def blacklist(self, kwargs):
#     bl = BLACKLIST.get(self.endpoint_prefix(), dict())
#     # For each blacklist rule/pattern
#     for k, v in bl.items():
#         if isinstance(v, Mutator):
#             kwargs[k] = v.apply(kwargs[k])
#         elif k in kwargs:
#             kwargs[k] = self.__rblacklist(v, kwargs[k])
#     return kwargs

# def __rblacklist(self, bl, kw):
#     if isinstance(bl, Mutator):
#         kw = bl.apply(kw)
#     else:
#         for k, v in bl.items():
#             if k in kw:
#                 kw[k] = self.__rblacklist(v, kw[k])

#     return kw

# def transform(self, shape_name, image):
#     f = IMAGE_TRANSFORMS.get(self.endpoint_prefix(), dict()).get(
#         shape_name, None)
#     if f is not None:
#         image = f.apply(image)
#     return image
