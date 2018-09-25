import os
import sys
import json

import boto3

from .shapes import (Operation, Blob, Boolean, Double, Float, Integer, List,
                     Long, Map, String, Structure, Timestamp, Alias)
from .exceptions import UnknownServiceException

from .special_cases import apply_shape_construction_transform as apply_sct, OPERATION_BLACKLIST, get_shape_alias

NONFATAL_EXCEPTIONS = {
    "iam": {
        "GetCredentialReport": ["CredentialReportNotPresentException"],
        "GetUser": ["ClientError"],
        "ListAccessKeys": ["ClientError"],
        "ListMFADevices": ["ClientError"],
        "ListSigningCertificates": ["ClientError"],
        "ListSSHPublicKeys": ["ClientError"],
        "ListServiceSpecificCredentials": ["ClientError"],
        "GetContextKeysForPrincipalPolicy": ["InvalidInputException"],
        "ListEntitiesForPolicy": ["InvalidInputException"]
    }
}


def func_wrapper(fn, allowed_exceptions):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            for exception_type in allowed_exceptions:
                if isinstance(e, exception_type):
                    print(str(e), file=sys.stderr)
                    return None
            raise e

    return wrapper


def iter_wrapper(it, allowed_exceptions):
    def ret():
        pass

    def wrapper(*args, **kwargs):
        iterator = it.paginate(*args, **kwargs)
        try:
            for i in iterator:
                yield i
        except Exception as e:
            for exception_type in allowed_exceptions:
                if isinstance(e, exception_type):
                    print(str(e), file=sys.stderr)
                    return None
            raise e

    ret.paginate = wrapper
    return ret


class AWSService(object):
    # Built programmatically:
    # find botocore/botocore/data/ -type f | grep service[^/]*json | xargs cat | jq -r '.shapes | to_entries | map(.value.type)[]' 2>/dev/null | sort | uniq | while read type; do echo "\"$type\": `echo $type | sed 's/^./\u&/'`,"; done
    SHAPE_TYPE_MAP = {
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
        "timestamp": Timestamp,
        "alias": Alias
    }

    def __init__(self,
                 service_name,
                 region=None,
                 version=None,
                 botocore_directory=os.path.join(os.getcwd(), "botocore")):
        """
        Load the service and paginator data for a given service name. If no version is provided, the latest is used. If a provided service/version pair does not exist, exceptions are raised.

        This depends on having a local clone of botocore, which is assumed to be in `pwd`/botocore, or rooted at the location provided.
        """
        self.session = boto3.Session({
            "region_name": region
        } if region is not None else dict())

        if service_name not in self.session.get_available_services():
            raise UnknownServiceException(service_name)
        else:
            self.client = self.session.client(service_name)

        service_dir = os.path.join(botocore_directory, "botocore", "data",
                                   service_name)

        versions = sorted(os.listdir(service_dir))
        if version is None:
            version = versions[-1]
        elif version not in version:
            raise ValueError("Provided version not in ")

        version_dir = os.path.join(service_dir, version)
        with open(os.path.join(version_dir, "service-2.json"), "r") as fp:
            service = json.loads(fp.read())

        try:
            with open(os.path.join(version_dir, "paginators-1.json"),
                      "r") as fp:
                paginators = json.loads(fp.read())
        except:
            paginators = None

        self.service = service
        self.paginators = paginators

    def get_method_name(self, operation_name):
        for method, name in self.client.meta.method_to_api_mapping.items():
            if name == operation_name:
                return method
        return None

    def get_method(self, operation_name):
        allowed_exceptions = [
            getattr(self.client.exceptions, exception_name)
            for exception_name in NONFATAL_EXCEPTIONS.get(
                self.endpoint_prefix(), dict()).get(operation_name, [])
        ]
        func = getattr(self.client, self.get_method_name(operation_name))

        return func_wrapper(func, allowed_exceptions)

    def get_paginator(self, operation_name):
        allowed_exceptions = [
            getattr(self.client.exceptions, exception_name)
            for exception_name in NONFATAL_EXCEPTIONS.get(
                self.endpoint_prefix(), dict()).get(operation_name, [])
        ]
        paginator = self.client.get_paginator(
            self.get_method_name(operation_name))

        return iter_wrapper(paginator, allowed_exceptions)

    def endpoint_prefix(self):
        return self.service["metadata"]["endpointPrefix"]

    def id(self):
        return self.service["metadata"]["serviceId"]

    def name(self):
        return self.service["metadata"]["serviceFullName"]

    def region(self):
        return self.session.region_name

    def get_shape(self, shape_name):
        raw_shape = self.raw_get_shape(shape_name)
        return self.SHAPE_TYPE_MAP.get(raw_shape["type"])(shape_name, self)

    def raw_get_shape(self, shape_name):
        shape = self.service["shapes"].get(shape_name)
        if shape is None:
            shape = get_shape_alias(self.endpoint_prefix(), shape_name)
        return apply_sct(self.endpoint_prefix(), shape_name, shape)

    def get_operations(self, op_filter=lambda op: True):
        """
        Return all operations that are part of this service, filtered by the provided filter function.
        """
        ops = [
            Operation(op, self)
            for _, op in self.service["operations"].items()
            if op_filter(op) and op["name"]
        ]

        if self.endpoint_prefix() in OPERATION_BLACKLIST:
            ops = OPERATION_BLACKLIST[self.endpoint_prefix()].apply(ops)

        # Now sort them so that List* come first, Get* come next, and Describe* come last.
        lists = [op for op in ops if op.name().startswith("List")]
        gets = [op for op in ops if op.name().startswith("Get")]
        describes = [op for op in ops if op.name().startswith("Describe")]

        return lists + gets + describes
